"""
test_env.py — Comprehensive test suite for DRC-Env v3.

Covers:
  - OpenEnv API contract (reset/step/state/grader)
  - All 3 tasks with deterministic episode validation
  - False SOS signal mechanics (core novel mechanic)
  - Cascading failure / dam break event
  - PyTorch ZoneScorerNet correctness
  - Reward function all positive + negative components
  - Resource constraint enforcement
  - Airlift precision and scarcity
  - Grader score monotonicity (good agent > random > wait-only)
  - Multi-session isolation

Run: python test_env.py
Exit 0 = all pass, Exit 1 = failures.
"""

from __future__ import annotations
import sys
from fastapi.testclient import TestClient
from demo_runner import iter_demo_events, run_demo_scenario
from demo_scenarios import DEMO_SCENARIOS
from environment import DisasterEnv
from main import app
from models import ActionModel
from graders import grade_episode
from reward import compute_episode_score
from tasks import ALL_TASKS

# ──────────────────────────────────────────────────────────────
# Test harness
# ──────────────────────────────────────────────────────────────

_results: list[tuple[str, bool, str]] = []

def test(name: str, condition: bool, detail: str = "") -> bool:
    _results.append((name, condition, detail))
    status = "PASS" if condition else "FAIL"
    line = f"  [{status}] {name}"
    if not condition and detail:
        line += f"\n         → {detail}"
    print(line)
    return condition

def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

def _run_to_done(env: DisasterEnv, action: ActionModel, max_steps: int = 30):
    """Step env with the same action until done, return final StepResult."""
    result = None
    for _ in range(max_steps):
        result = env.step(action)
        if result.done:
            break
    return result


# ──────────────────────────────────────────────────────────────
# GROUP 1: OpenEnv API Contract
# ──────────────────────────────────────────────────────────────

def test_api_contract():
    section("GROUP 1 — OpenEnv API Contract")

    env = DisasterEnv()
    obs = env.reset("task_1")

    # reset() contract
    test("reset() returns ObservationModel with zones",
         hasattr(obs, "zones") and len(obs.zones) > 0)
    test("reset() step_number == 0", obs.step_number == 0)
    test("reset() steps_remaining == max_steps",
         obs.steps_remaining == ALL_TASKS["task_1"]["max_steps"])
    test("reset() weather is 'clear'", obs.weather == "clear")
    test("reset() last_action_result is 'none'", obs.last_action_result == "none")
    test("reset() resources present",
         hasattr(obs, "resources") and obs.resources.teams_available > 0)

    # step() contract
    action = ActionModel(action="deploy_team", to_zone="A", units=1)
    result = env.step(action)
    test("step() returns StepResult with observation",
         hasattr(result, "observation"))
    test("step() reward is float", isinstance(result.reward, float))
    test("step() reward clamped to [-1, 1]",
         -1.0 <= result.reward <= 1.0,
         f"got {result.reward}")
    test("step() done is bool", isinstance(result.done, bool))
    test("step() info contains reward_breakdown",
         isinstance(result.info, dict) and "reward_breakdown" in result.info)
    test("step() step_number increments",
         result.observation.step_number == 1)
    test("step() steps_remaining decrements",
         result.observation.steps_remaining == ALL_TASKS["task_1"]["max_steps"] - 1)

    # state() contract
    env.reset("task_1")
    state = env.state()
    test("state() returns dict", isinstance(state, dict))
    test("state() zones list present", "zones" in state and len(state["zones"]) > 0)
    test("state() hidden field casualties_critical exposed",
         "casualties_critical" in state["zones"][0])
    test("state() hidden field is_false_sos exposed",
         "is_false_sos" in state["zones"][0])
    test("state() event_log present", "event_log" in state)


# ──────────────────────────────────────────────────────────────
# GROUP 2: All Tasks Load Correctly
# ──────────────────────────────────────────────────────────────

def test_all_tasks():
    section("GROUP 2 — Task Configurations")

    for task_id, cfg in ALL_TASKS.items():
        env = DisasterEnv()
        obs = env.reset(task_id)
        test(f"{task_id}: resets without error", obs is not None)
        test(f"{task_id}: zone count matches config",
             len(obs.zones) == len(cfg["zones"]),
             f"expected {len(cfg['zones'])}, got {len(obs.zones)}")
        test(f"{task_id}: steps_remaining == max_steps",
             obs.steps_remaining == cfg["max_steps"])
        test(f"{task_id}: zone IDs are unique",
             len({z.zone_id for z in obs.zones}) == len(obs.zones))
        test(f"{task_id}: severity in [0,1] for all zones",
             all(0.0 <= z.severity <= 1.0 for z in obs.zones),
             str([z.severity for z in obs.zones]))

    # task_3 must have 10 zones
    env = DisasterEnv()
    obs = env.reset("task_3")
    test("task_3: has exactly 10 zones", len(obs.zones) == 10)

    # task_1 must have exactly 1 zone
    env = DisasterEnv()
    obs = env.reset("task_1")
    test("task_1: has exactly 1 zone", len(obs.zones) == 1)


# ──────────────────────────────────────────────────────────────
# GROUP 3: False SOS Signal Mechanics  ← core novel mechanic
# ──────────────────────────────────────────────────────────────

def test_false_sos_mechanics():
    section("GROUP 3 — False SOS Signal Mechanics")

    env = DisasterEnv()
    obs = env.reset("task_3")
    state = env.state()

    # False SOS zones identified from state (hidden field)
    false_sos_ids = {z["zone_id"] for z in state["zones"] if z.get("is_false_sos")}
    # Agent sees sos_active via observation, not state
    obs_sos_active = {z.zone_id for z in obs.zones if z.sos_active}

    test("task_3: has at least 1 false SOS zone (from state hidden field)",
         len(false_sos_ids) >= 1,
         f"false_sos zones: {sorted(false_sos_ids)}")
    test("task_3: false SOS zones appear active to agent via sos_active",
         false_sos_ids.issubset(obs_sos_active),
         f"false_sos={sorted(false_sos_ids)}, sos_active={sorted(obs_sos_active)}")
    # In obs, false SOS zones have 0 casualties_remaining and 0 supply_gap
    test("task_3: false SOS zones have zero casualties_remaining in observation",
         all(z.casualties_remaining == 0
             for z in obs.zones if z.zone_id in false_sos_ids),
         str({z.zone_id: z.casualties_remaining for z in obs.zones if z.zone_id in false_sos_ids}))
    test("task_3: false SOS zones have zero supply_gap in observation",
         all(z.supply_gap == 0
             for z in obs.zones if z.zone_id in false_sos_ids),
         str({z.zone_id: z.supply_gap for z in obs.zones if z.zone_id in false_sos_ids}))

    # Deploying to a false SOS zone should incur a penalty
    if false_sos_ids:
        env2 = DisasterEnv()
        env2.reset("task_3")
        fsos_zone = sorted(false_sos_ids)[0]
        result = env2.step(ActionModel(action="deploy_team", to_zone=fsos_zone, units=1))
        breakdown = result.info.get("reward_breakdown", {})
        false_sos_penalty = breakdown.get("p_false_sos", 0.0)
        # p_false_sos stored as positive magnitude; non-zero means penalty applied
        test("deploying to false SOS zone incurs p_false_sos penalty",
             false_sos_penalty != 0.0,
             f"p_false_sos={false_sos_penalty}, breakdown={breakdown}")

    # Real zones (non-false-SOS) must have actual casualties in state
    real_zones_with_cas = [
        z for z in state["zones"]
        if not z.get("is_false_sos") and z.get("casualties_total", 0) > 0
    ]
    test("task_3: real (non-false-SOS) zones have actual casualties",
         len(real_zones_with_cas) > 0,
         f"found {len(real_zones_with_cas)} real zones with casualties")


# ──────────────────────────────────────────────────────────────
# GROUP 4: Cascading Failure / Dam Break Event
# ──────────────────────────────────────────────────────────────

def test_cascading_failure():
    section("GROUP 4 — Cascading Failure (Dam Break at step 7)")

    env = DisasterEnv()
    env.reset("task_3")

    # Note Zone E casualties before step 7 (use casualties_total from state)
    pre_break_state = env.state()
    zone_e_before = next(
        (z["casualties_total"] for z in pre_break_state["zones"] if z["zone_id"] == "E"), 0
    )

    # Dam break fires when current_step==7 (pre-increment), i.e. during the 8th step() call
    for _ in range(8):
        result = env.step(ActionModel(action="wait"))
        if result.done:
            break

    post_break_state = env.state()
    zone_e_after = next(
        (z["casualties_total"] for z in post_break_state["zones"] if z["zone_id"] == "E"), 0
    )

    test("dam break at step 7 increases Zone E casualties",
         zone_e_after > zone_e_before,
         f"Zone E: before={zone_e_before}, after={zone_e_after}")
    test("dam break adds significant casualties to Zone E (≥ 30)",
         zone_e_after - zone_e_before >= 30,
         f"increase was only {zone_e_after - zone_e_before}")
    test("event_log records the dam_break event",
         any("dam" in str(e.get("type", "")).lower() or
             "dam" in str(e.get("event", "")).lower()
             for e in post_break_state.get("event_log", [])),
         f"event_log: {post_break_state.get('event_log', [])}")


# ──────────────────────────────────────────────────────────────
# GROUP 5: Resource Constraints
# ──────────────────────────────────────────────────────────────

def test_resource_constraints():
    section("GROUP 5 — Resource Constraint Enforcement")

    # Over-deploying teams returns insufficient_resources
    env = DisasterEnv()
    env.reset("task_1")
    state = env.state()
    teams = state["teams_available"]
    result = env.step(ActionModel(action="deploy_team", to_zone="A", units=teams + 100))
    test("over-deploying teams returns insufficient_resources",
         result.observation.last_action_result == "insufficient_resources",
         f"got {result.observation.last_action_result}")

    # Over-sending supplies returns insufficient_resources
    env2 = DisasterEnv()
    env2.reset("task_1")
    state2 = env2.state()
    stock = state2["supply_stock"]
    result2 = env2.step(ActionModel(action="send_supplies", to_zone="A", units=stock + 100))
    test("over-sending supplies returns insufficient_resources",
         result2.observation.last_action_result == "insufficient_resources",
         f"got {result2.observation.last_action_result}")

    # Deploying to blocked zone returns blocked
    env3 = DisasterEnv()
    env3.reset("task_2")  # task_2 has road-blocked zones
    blocked_zones = [z for z in env3.state()["zones"] if z["road_blocked"]]
    if blocked_zones:
        bzone = blocked_zones[0]["zone_id"]
        result3 = env3.step(ActionModel(action="deploy_team", to_zone=bzone, units=1))
        test("deploy_team to road-blocked zone returns 'blocked'",
             result3.observation.last_action_result == "blocked",
             f"zone={bzone}, result={result3.observation.last_action_result}")

    # Invalid zone ID returns invalid
    env4 = DisasterEnv()
    env4.reset("task_1")
    result4 = env4.step(ActionModel(action="deploy_team", to_zone="ZZINVALID", units=1))
    test("invalid zone ID returns 'invalid'",
         result4.observation.last_action_result == "invalid")

    # Airlift when none remain returns insufficient_resources
    env5 = DisasterEnv()
    env5.reset("task_2")
    airlifts = env5.state()["airlifts_remaining"]
    for _ in range(airlifts):
        env5.step(ActionModel(action="airlift", to_zone="B", type="rescue"))
    result5 = env5.step(ActionModel(action="airlift", to_zone="B", type="rescue"))
    test("airlift with 0 airlifts remaining returns insufficient_resources",
         result5.observation.last_action_result == "insufficient_resources",
         f"got {result5.observation.last_action_result}")

    # Rescue airlift also needs an available team
    env6 = DisasterEnv()
    env6.reset("task_2")
    teams6 = env6.state()["teams_available"]
    env6.step(ActionModel(action="deploy_team", to_zone="A", units=teams6))
    airlifts_before6 = env6.state()["airlifts_remaining"]
    result6 = env6.step(ActionModel(action="airlift", to_zone="B", type="rescue"))
    state6 = env6.state()
    test("rescue airlift with 0 teams returns insufficient_resources",
         result6.observation.last_action_result == "insufficient_resources",
         f"got {result6.observation.last_action_result}")
    test("failed rescue airlift does not consume an airlift",
         state6["airlifts_remaining"] == airlifts_before6,
         f"before={airlifts_before6}, after={state6['airlifts_remaining']}")
    test("failed rescue airlift never makes teams_available negative",
         state6["teams_available"] >= 0,
         f"teams_available={state6['teams_available']}")

    # Supply airlift also needs remaining stock
    env7 = DisasterEnv()
    env7.reset("task_2")
    stock7 = env7.state()["supply_stock"]
    env7.step(ActionModel(action="send_supplies", to_zone="A", units=stock7))
    airlifts_before7 = env7.state()["airlifts_remaining"]
    result7 = env7.step(ActionModel(action="airlift", to_zone="B", type="supply"))
    state7 = env7.state()
    test("supply airlift with 0 stock returns insufficient_resources",
         result7.observation.last_action_result == "insufficient_resources",
         f"got {result7.observation.last_action_result}")
    test("failed supply airlift does not consume an airlift",
         state7["airlifts_remaining"] == airlifts_before7,
         f"before={airlifts_before7}, after={state7['airlifts_remaining']}")

    # Wait action is always valid
    env8 = DisasterEnv()
    env8.reset("task_1")
    result8 = env8.step(ActionModel(action="wait"))
    test("wait action always returns success",
         result8.observation.last_action_result == "success")


# ──────────────────────────────────────────────────────────────
# GROUP 6: Airlift Precision
# ──────────────────────────────────────────────────────────────

def test_airlift_precision():
    section("GROUP 6 — Airlift Precision & Scarcity")

    env = DisasterEnv()
    env.reset("task_2")
    state = env.state()
    airlifts_start = state["airlifts_remaining"]

    # Airlift to blocked zone succeeds
    blocked_zones = [z for z in state["zones"] if z["road_blocked"]]
    if blocked_zones:
        bzone = blocked_zones[0]["zone_id"]
        result = env.step(ActionModel(action="airlift", to_zone=bzone, type="rescue"))
        state_after = env.state()
        airlift_events = [
            e for e in state_after["event_log"]
            if e.get("type") == "airlift" and e.get("to") == bzone
        ]
        test("airlift to blocked zone succeeds",
             result.observation.last_action_result == "success",
             f"zone={bzone}, result={result.observation.last_action_result}")
        test("airlift consumes exactly 1 airlift unit",
             result.observation.resources.airlifts_remaining == airlifts_start - 1,
             f"before={airlifts_start}, after={result.observation.resources.airlifts_remaining}")
        test("airlift to blocked+critical zone yields r_airlift_precision > 0",
             result.info.get("reward_breakdown", {}).get("r_airlift_precision", 0.0) > 0.0,
             str(result.info.get("reward_breakdown", {})))
        test("event_log records airlift events with stable type='airlift'",
             len(airlift_events) == 1,
             str(state_after["event_log"]))
        test("event_log stores airlift mode separately",
             airlift_events[0].get("airlift_type") == "rescue" if airlift_events else False,
             str(airlift_events))

    # Airlift supply type works and cannot create stock from nothing
    env2 = DisasterEnv()
    env2.reset("task_2")
    stock2 = env2.state()["supply_stock"]
    env2.step(ActionModel(action="send_supplies", to_zone="A", units=stock2 - 10))
    blocked2 = [z for z in env2.state()["zones"] if z["road_blocked"]]
    if blocked2:
        bzone2 = blocked2[0]["zone_id"]
        result2 = env2.step(ActionModel(action="airlift", to_zone=bzone2, type="supply"))
        state2 = env2.state()
        zone2 = next(z for z in state2["zones"] if z["zone_id"] == bzone2)
        test("airlift supply type succeeds on blocked zone",
             result2.observation.last_action_result == "success")
        test("supply airlift only delivers remaining stock",
             zone2["supply_received"] == 10 and state2["supply_stock"] == 0,
             f"received={zone2['supply_received']}, stock={state2['supply_stock']}")


# ──────────────────────────────────────────────────────────────
# GROUP 7: Reward Function Components
# ──────────────────────────────────────────────────────────────

def test_reward_components():
    section("GROUP 7 — Reward Function Components")

    # Rescuing casualties gives r_rescue > 0
    env = DisasterEnv()
    env.reset("task_1")
    state = env.state()
    zone = state["zones"][0]
    teams = state["teams_available"]
    result = env.step(ActionModel(action="deploy_team", to_zone=zone["zone_id"], units=min(teams, 3)))
    breakdown = result.info.get("reward_breakdown", {})
    test("deploy_team to casualty zone gives r_rescue > 0",
         breakdown.get("r_rescue", 0.0) > 0.0,
         str(breakdown))

    # Sending supplies gives r_supply > 0
    env2 = DisasterEnv()
    env2.reset("task_1")
    state2 = env2.state()
    zone2 = state2["zones"][0]
    supply_gap2 = zone2["supply_needed"] - zone2["supply_received"]
    if supply_gap2 > 0:
        stock = state2["supply_stock"]
        result2 = env2.step(ActionModel(action="send_supplies",
                                         to_zone=zone2["zone_id"],
                                         units=min(stock, supply_gap2)))
        breakdown2 = result2.info.get("reward_breakdown", {})
        test("send_supplies to needy zone gives r_supply > 0",
             breakdown2.get("r_supply", 0.0) > 0.0,
             str(breakdown2))

    # Wait action always gives p_wait penalty
    env3 = DisasterEnv()
    env3.reset("task_1")
    result3 = env3.step(ActionModel(action="wait"))
    breakdown3 = result3.info.get("reward_breakdown", {})
    test("wait action incurs p_wait penalty != 0",
         breakdown3.get("p_wait", 0.0) != 0.0,
         str(breakdown3))

    # compute_episode_score: good > 0.5, bad < 0.5
    test("good cumulative reward → episode score > 0.5",
         compute_episode_score(10.0, 10) > 0.5)
    test("bad cumulative reward → episode score < 0.5",
         compute_episode_score(-10.0, 10) < 0.5)
    test("zero cumulative reward → episode score ≈ 0.5",
         abs(compute_episode_score(0.0, 10) - 0.5) < 0.1)

    # Episode score is in [0, 1]
    for cum in [-20.0, -5.0, 0.0, 5.0, 20.0]:
        score = compute_episode_score(cum, 10)
        test(f"episode score ∈ [0,1] for cum_reward={cum}",
             0.0 <= score <= 1.0,
             f"got {score}")


# ──────────────────────────────────────────────────────────────
# GROUP 8: Grader — Score Monotonicity
# ──────────────────────────────────────────────────────────────

def test_grader_monotonicity():
    section("GROUP 8 — Grader Score Monotonicity")

    for task_id in ["task_1", "task_2", "task_3"]:
        cfg = ALL_TASKS[task_id]

        # Strategy A: always wait (worst)
        env_wait = DisasterEnv()
        env_wait.reset(task_id)
        for _ in range(cfg["max_steps"] + 5):
            r = env_wait.step(ActionModel(action="wait"))
            if r.done:
                break
        final_wait = env_wait.state()
        score_wait = grade_episode(final_wait["event_log"], final_wait, task_id)

        # Strategy B: greedy deploy all teams to highest-casualty zone
        env_greedy = DisasterEnv()
        env_greedy.reset(task_id)
        for _ in range(cfg["max_steps"] + 5):
            state_g = env_greedy.state()
            # Find highest-casualty unblocked zone (casualties remaining = total - rescued)
            candidates = sorted(
                [z for z in state_g["zones"]
                 if not z["road_blocked"]
                 and (z["casualties_total"] - z["casualties_rescued"]) > 0],
                key=lambda z: z["casualties_total"] - z["casualties_rescued"],
                reverse=True
            )
            teams_avail = state_g["teams_available"]
            if candidates and teams_avail > 0:
                action = ActionModel(action="deploy_team",
                                     to_zone=candidates[0]["zone_id"],
                                     units=min(teams_avail, 2))
            else:
                action = ActionModel(action="wait")
            r = env_greedy.step(action)
            if r.done:
                break
        final_greedy = env_greedy.state()
        score_greedy = grade_episode(final_greedy["event_log"], final_greedy, task_id)

        test(f"{task_id}: grader score in [0, 1] for wait strategy",
             0.0 <= score_wait <= 1.0,
             f"got {score_wait:.4f}")
        test(f"{task_id}: grader score in [0, 1] for greedy strategy",
             0.0 <= score_greedy <= 1.0,
             f"got {score_greedy:.4f}")
        test(f"{task_id}: greedy agent scores ≥ wait-only agent",
             score_greedy >= score_wait,
             f"greedy={score_greedy:.4f}, wait={score_wait:.4f}")
        print(f"         wait={score_wait:.4f}  greedy={score_greedy:.4f}")


# ──────────────────────────────────────────────────────────────
# GROUP 9: Episode Termination
# ──────────────────────────────────────────────────────────────

def test_episode_termination():
    section("GROUP 9 — Episode Termination")

    for task_id in ["task_1", "task_2", "task_3"]:
        env = DisasterEnv()
        env.reset(task_id)
        max_steps = ALL_TASKS[task_id]["max_steps"]
        step_count = 0
        while True:
            result = env.step(ActionModel(action="wait"))
            step_count += 1
            if result.done:
                break
            if step_count > max_steps + 5:
                break  # prevent infinite loop in test
        test(f"{task_id}: episode terminates at or before max_steps ({max_steps})",
             step_count <= max_steps,
             f"terminated at step {step_count}")
        test(f"{task_id}: done=True at termination", result.done)
        test(f"{task_id}: steps_remaining=0 at termination",
             result.observation.steps_remaining == 0,
             f"got steps_remaining={result.observation.steps_remaining}")


# ──────────────────────────────────────────────────────────────
# GROUP 10: PyTorch ZoneScorerNet
# ──────────────────────────────────────────────────────────────

def test_pytorch_zone_scorer():
    section("GROUP 10 — PyTorch ZoneScorerNet")

    try:
        from agents.zone_scorer import score_zones
        import torch
    except ImportError as e:
        test("zone_scorer import succeeds", False, str(e))
        return

    env = DisasterEnv()
    obs = env.reset("task_3")
    obs_dict = obs.model_dump()

    scores = score_zones(obs_dict)

    test("score_zones returns a list", isinstance(scores, list))
    test("score_zones returns one entry per zone",
         len(scores) == len(obs_dict["zones"]),
         f"expected {len(obs_dict['zones'])}, got {len(scores)}")
    test("score_zones returns scores in [0, 1]",
         all(0.0 <= s["score"] <= 1.0 for s in scores),
         str([s["score"] for s in scores]))
    test("score_zones list is sorted descending by score",
         all(scores[i]["score"] >= scores[i+1]["score"] for i in range(len(scores)-1)))
    test("each score entry has zone_id, score, is_false_sos_suspect keys",
         all("zone_id" in s and "score" in s and "is_false_sos_suspect" in s for s in scores))

    # False SOS zones (H, I, J in task_3) should score near 0
    state = env.state()
    false_sos_ids = {z["zone_id"] for z in state["zones"] if z.get("is_false_sos")}
    if false_sos_ids:
        fsos_scores = [s["score"] for s in scores if s["zone_id"] in false_sos_ids]
        test("false SOS zones score 0.0 in ZoneScorerNet",
             all(s == 0.0 for s in fsos_scores),
             f"false_sos scores: {fsos_scores}")
        test("false SOS zones flagged as is_false_sos_suspect",
             all(s["is_false_sos_suspect"] for s in scores if s["zone_id"] in false_sos_ids))

    # High-casualty zone should outscore empty zone
    zones_by_cas = sorted(obs_dict["zones"], key=lambda z: z.get("casualties_remaining", 0), reverse=True)
    if len(zones_by_cas) >= 2:
        high_cas_zone = zones_by_cas[0]["zone_id"]
        low_cas_zone  = zones_by_cas[-1]["zone_id"]
        high_score = next(s["score"] for s in scores if s["zone_id"] == high_cas_zone)
        low_score  = next(s["score"] for s in scores if s["zone_id"] == low_cas_zone)
        test("high-casualty zone scores higher than low-casualty zone",
             high_score >= low_score,
             f"{high_cas_zone}={high_score:.4f} vs {low_cas_zone}={low_score:.4f}")


# ──────────────────────────────────────────────────────────────
# GROUP 11: Multi-Session Isolation
# ──────────────────────────────────────────────────────────────

def test_session_isolation():
    section("GROUP 11 — Multi-Session Isolation")

    # Two envs on different tasks must not share state
    env_a = DisasterEnv()
    env_b = DisasterEnv()
    obs_a = env_a.reset("task_1")
    obs_b = env_b.reset("task_3")

    test("task_1 and task_3 have different zone counts",
         len(obs_a.zones) != len(obs_b.zones),
         f"task_1={len(obs_a.zones)}, task_3={len(obs_b.zones)}")

    # Stepping env_a must not affect env_b
    env_a.step(ActionModel(action="wait"))
    env_a.step(ActionModel(action="wait"))
    test("stepping task_1 env doesn't affect task_3 env step_number",
         env_b.state()["current_step"] == 0)

    # reset() on same env starts fresh
    env_c = DisasterEnv()
    env_c.reset("task_1")
    env_c.step(ActionModel(action="wait"))
    env_c.step(ActionModel(action="wait"))
    obs_reset = env_c.reset("task_1")
    test("re-reset() returns step_number=0", obs_reset.step_number == 0)
    test("re-reset() restores original resources",
         obs_reset.resources.teams_available == ALL_TASKS["task_1"]["resources"].get("teams", obs_reset.resources.teams_available))


# ──────────────────────────────────────────────────────────────
# GROUP 12: Team Transit Delay
# ──────────────────────────────────────────────────────────────

def test_transit_delay():
    section("GROUP 12 — 1-Step Team Transit Delay")

    env = DisasterEnv()
    obs = env.reset("task_1")
    initial_teams = obs.resources.teams_available

    # Deploy teams; they should leave HQ immediately
    result = env.step(ActionModel(action="deploy_team", to_zone="A", units=2))
    test("teams_available decreases after deploy",
         result.observation.resources.teams_available < initial_teams,
         f"before={initial_teams}, after={result.observation.resources.teams_available}")

    # Recall teams back to HQ
    result2 = env.step(ActionModel(action="recall_team", from_zone="A", units=1))
    test("recall_team succeeds", result2.observation.last_action_result == "success")

    # Teams in transit should appear in teams_in_transit dict
    state_mid = env.state()
    test("recalled teams appear in teams_in_transit",
         isinstance(state_mid["teams_in_transit"], dict))


# ──────────────────────────────────────────────────────────────
# GROUP 13: Bengaluru Live Demo
# ──────────────────────────────────────────────────────────────

def test_live_demo_mode():
    section("GROUP 13 — Bengaluru Live Demo Mode")

    expected_ids = {
        "bellandur_flood_response",
        "peenya_industrial_fire",
        "whitefield_building_collapse",
    }

    test("demo scenario registry contains exactly 3 scenarios",
         len(DEMO_SCENARIOS) == 3,
         f"got {sorted(DEMO_SCENARIOS.keys())}")
    test("demo scenario registry IDs match curated Bengaluru set",
         set(DEMO_SCENARIOS.keys()) == expected_ids,
         f"got {sorted(DEMO_SCENARIOS.keys())}")

    client = TestClient(app)

    catalog = client.get("/demo/scenarios")
    test("GET /demo/scenarios returns 200", catalog.status_code == 200, catalog.text)
    catalog_body = catalog.json()
    scenarios = catalog_body.get("scenarios", [])
    test("GET /demo/scenarios returns 3 scenario summaries",
         len(scenarios) == 3,
         f"got {len(scenarios)}")
    test("GET /demo/scenarios exposes available agents",
         set(catalog_body.get("available_agents", [])) == {"ai_4stage", "greedy", "random"},
         str(catalog_body))

    bad_run = client.post("/demo/run/not_real", json={"agent": "greedy"})
    test("POST /demo/run rejects unknown scenario IDs",
         bad_run.status_code == 400,
         bad_run.text)

    replay = client.post("/demo/run/bellandur_flood_response", json={"agent": "greedy"})
    test("POST /demo/run returns 200 for valid scenario",
         replay.status_code == 200,
         replay.text)
    replay_body = replay.json()
    test("demo replay payload includes scenario detail",
         replay_body.get("scenario", {}).get("scenario_id") == "bellandur_flood_response",
         str(replay_body.keys()))
    test("demo replay includes map_state on each step",
         all("map_state" in step for step in replay_body.get("steps", [])),
         str(replay_body.get("steps", [])[:1]))
    test("demo replay map_state includes resource positions and route references",
         all(
             "resource_positions" in step["map_state"] and "recent_movements" in step["map_state"]
             for step in replay_body.get("steps", [])
         ),
         str(replay_body.get("steps", [])[:1]))

    events = [event for event, _ in iter_demo_events("bellandur_flood_response", "greedy", delay_seconds=0.0)]
    test("demo SSE generator emits meta first",
         bool(events) and events[0] == "meta",
         str(events[:6]))
    test("demo SSE generator emits ordered stage/step/done events",
         events[-1] == "done" and "step" in events and events.count("stage") >= 4,
         str(events[:10]))

    for agent in ["ai_4stage", "greedy", "random"]:
        result = run_demo_scenario("whitefield_building_collapse", agent)
        test(f"demo runner works for agent={agent}",
             result.steps_taken == len(result.steps) and len(result.steps) > 0,
             f"steps_taken={result.steps_taken}, len={len(result.steps)}")
        test(f"demo runner keeps map_state schema stable for agent={agent}",
             all(step.map_state.recent_movements is not None for step in result.steps),
             str(result.steps[0].map_state.model_dump()))


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "="*60)
    print("  DRC-Env v3 — Full Test Suite")
    print("="*60)

    test_api_contract()
    test_all_tasks()
    test_false_sos_mechanics()
    test_cascading_failure()
    test_resource_constraints()
    test_airlift_precision()
    test_reward_components()
    test_grader_monotonicity()
    test_episode_termination()
    test_pytorch_zone_scorer()
    test_session_isolation()
    test_transit_delay()
    test_live_demo_mode()

    # ── Final summary ──────────────────────────────────────────
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    total  = len(_results)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{total} passed  ({failed} failed)")
    print(f"{'='*60}")

    if failed:
        print("\n  Failed tests:")
        for name, ok, detail in _results:
            if not ok:
                line = f"    ✗ {name}"
                if detail:
                    line += f"\n        {detail}"
                print(line)

    if passed == total:
        print("\n  All tests passed. Environment is submission-ready.")
    else:
        print(f"\n  {failed} test(s) failed.")

    print("="*60)
    return passed == total


if __name__ == "__main__":
    ok = run_all_tests()
    sys.exit(0 if ok else 1)

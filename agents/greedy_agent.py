"""
greedy_agent.py — Deterministic greedy baseline for DisasterMan comparison.

Priority order at each step:
  1. Recall teams from fully-completed zones (free up resources)
  2. Airlift to highest-severity blocked zone (if airlift available)
  3. Deploy teams to highest-severity accessible zone with casualties
  4. Send supplies to zone with largest supply gap
  5. Wait

No LLM calls. Uses PyTorch zone scores for zone ranking.
Serves as the mid-range baseline in the Compare Agents view.
"""

from __future__ import annotations
from models import ActionModel


def get_greedy_action(obs: dict, zone_scores: list[dict]) -> tuple[ActionModel, str]:
    """
    Return a greedy action + rationale string.

    Args:
        obs: Current observation dict
        zone_scores: Sorted list from zone_scorer.score_zones() (highest score first)

    Returns:
        (ActionModel, rationale_string)
    """
    res = obs["resources"]
    teams_available: int = res["teams_available"]
    supply_stock: int = res["supply_stock"]
    airlifts_remaining: int = res["airlifts_remaining"]

    zone_map = {z["zone_id"]: z for z in obs["zones"]}
    false_sos_ids = {
        zs["zone_id"] for zs in zone_scores if zs["is_false_sos_suspect"]
    }

    # Rule 1: Recall from completed zones to free teams
    for z in obs["zones"]:
        if z["zone_id"] in false_sos_ids:
            continue
        if z["teams_present"] > 0 and z["casualties_remaining"] == 0 and z["supply_gap"] == 0:
            return (
                ActionModel(action="recall_team", from_zone=z["zone_id"], units=z["teams_present"]),
                f"Recalling {z['teams_present']} teams from completed zone {z['zone_id']}",
            )

    # Rule 2: Airlift to highest-priority blocked zone
    if airlifts_remaining > 0:
        for zs in zone_scores:
            if zs["is_false_sos_suspect"]:
                continue
            z = zone_map.get(zs["zone_id"])
            if z and z["road_blocked"] and z["casualties_remaining"] > 0 and z["severity"] >= 0.75:
                return (
                    ActionModel(action="airlift", to_zone=z["zone_id"], type="rescue"),
                    f"Airlifting to blocked zone {z['zone_id']} (severity={z['severity']:.2f}, PyTorch score={zs['score']:.3f})",
                )

    # Rule 3: Deploy teams to highest-priority accessible zone
    if teams_available > 0:
        for zs in zone_scores:
            if zs["is_false_sos_suspect"]:
                continue
            z = zone_map.get(zs["zone_id"])
            if z and not z["road_blocked"] and z["casualties_remaining"] > 0 and z["teams_present"] == 0:
                units = min(2 if z["severity"] >= 0.75 else 1, teams_available)
                return (
                    ActionModel(action="deploy_team", to_zone=z["zone_id"], units=units),
                    f"Deploying {units} team(s) to zone {z['zone_id']} (severity={z['severity']:.2f}, PyTorch score={zs['score']:.3f})",
                )

    # Rule 4: Send supplies to zone with largest supply gap
    if supply_stock > 0:
        supply_targets = [
            z for z in obs["zones"]
            if z["zone_id"] not in false_sos_ids
            and not z["road_blocked"]
            and z["supply_gap"] > 0
        ]
        if supply_targets:
            target = max(supply_targets, key=lambda z: z["supply_gap"])
            units = min(target["supply_gap"], supply_stock)
            return (
                ActionModel(action="send_supplies", to_zone=target["zone_id"], units=units),
                f"Sending {units} supply units to zone {target['zone_id']} (supply gap={target['supply_gap']})",
            )

    return ActionModel(action="wait"), "No valid greedy action — waiting (penalty incurred)"


def run_greedy_task(task_id: str) -> dict:
    """
    Run a full episode using the greedy agent. Returns step-by-step data.

    Returns:
        {task_id, agent, final_score, cumulative_reward, steps_taken, steps: [...]}
    """
    from environment import DisasterEnv
    from graders import grade_episode
    from agents.zone_scorer import score_zones

    env = DisasterEnv()
    obs = env.reset(task_id)
    total_reward = 0.0
    steps_data: list[dict] = []

    while True:
        obs_dict = obs.model_dump()
        zone_scores = score_zones(obs_dict)
        action, rationale = get_greedy_action(obs_dict, zone_scores)
        result = env.step(action)
        total_reward += result.reward

        steps_data.append({
            "step": obs_dict["step_number"],
            "observation": obs_dict,
            "action": action.model_dump(),
            "reward": round(result.reward, 4),
            "reasoning": {
                "pytorch_scores": zone_scores,
                "triage_summary": "Greedy agent — priority: recall → airlift → deploy → supply",
                "plan_decision": "Execute highest-priority greedy rule",
                "action_rationale": rationale,
            },
        })

        obs = result.observation
        if result.done:
            break

    final_state = env.state()
    score = grade_episode(final_state["event_log"], final_state, task_id)

    return {
        "task_id": task_id,
        "agent": "greedy",
        "final_score": round(score, 4),
        "cumulative_reward": round(total_reward, 4),
        "steps_taken": len(steps_data),
        "steps": steps_data,
    }

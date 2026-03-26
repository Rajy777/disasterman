"""
test_env.py — Integration test suite for DisasterEnv.
Owner: Raj Yadav
Run after merge: python test_env.py
All tests must pass before Day 3 begins.
"""

from __future__ import annotations
import sys
from environment import DisasterEnv
from models import ActionModel
from graders import grade_episode
from reward import compute_episode_score


def test(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    msg = f"[{status}] {name}"
    if not condition and detail:
        msg += f"\n       → {detail}"
    print(msg)
    return condition


def run_all_tests():
    print("\n" + "="*60)
    print("DisasterEnv Integration Tests")
    print("="*60)
    passed = 0
    total = 0

    env = DisasterEnv()

    # ------------------------------------------------------------------
    # Test 1: reset() returns valid ObservationModel
    # ------------------------------------------------------------------
    obs = env.reset("task_1")
    total += 1
    passed += test(
        "reset() returns observation with zones",
        len(obs.zones) > 0,
        f"got {len(obs.zones)} zones"
    )

    total += 1
    passed += test(
        "reset() step_number is 0",
        obs.step_number == 0
    )

    total += 1
    passed += test(
        "reset() weather is clear",
        obs.weather == "clear"
    )

    total += 1
    passed += test(
        "reset() last_action_result is none",
        obs.last_action_result == "none"
    )

    # ------------------------------------------------------------------
    # Test 2: step() with valid action returns StepResult
    # ------------------------------------------------------------------
    action = ActionModel(action="deploy_team", to_zone="A", units=2)
    result = env.step(action)
    total += 1
    passed += test(
        "step() returns done=False on first action",
        not result.done
    )

    total += 1
    passed += test(
        "step() reward is float in [-1, 1]",
        isinstance(result.reward, float) and -1.0 <= result.reward <= 1.0,
        f"got reward={result.reward}"
    )

    total += 1
    passed += test(
        "step() observation is valid",
        result.observation.step_number == 1
    )

    total += 1
    passed += test(
        "step() info contains reward_breakdown",
        "reward_breakdown" in result.info
    )

    # ------------------------------------------------------------------
    # Test 3: Invalid action gets penalized, not crashed
    # ------------------------------------------------------------------
    env.reset("task_1")
    bad_action = ActionModel(action="deploy_team", to_zone="NONEXISTENT", units=1)
    result = env.step(bad_action)
    total += 1
    passed += test(
        "invalid action returns 'invalid' result without crash",
        result.observation.last_action_result == "invalid"
    )

    # ------------------------------------------------------------------
    # Test 4: state() returns full dict with hidden fields
    # ------------------------------------------------------------------
    env.reset("task_1")
    state = env.state()
    total += 1
    passed += test(
        "state() contains zones list",
        "zones" in state and len(state["zones"]) > 0
    )

    total += 1
    passed += test(
        "state() zones have hidden field is_false_sos",
        "is_false_sos" in state["zones"][0]
    )

    total += 1
    passed += test(
        "state() zones have hidden field casualties_critical",
        "casualties_critical" in state["zones"][0]
    )

    # ------------------------------------------------------------------
    # Test 5: Episode completes correctly at max_steps
    # ------------------------------------------------------------------
    env.reset("task_1")
    wait_action = ActionModel(action="wait")
    final_result = None
    for _ in range(20):   # task_1 max_steps=10, so episode must end by step 10
        final_result = env.step(wait_action)
        if final_result.done:
            break

    total += 1
    passed += test(
        "episode terminates at or before max_steps",
        final_result is not None and final_result.done
    )

    # ------------------------------------------------------------------
    # Test 6: Graders return float in [0, 1]
    # ------------------------------------------------------------------
    for task_id in ["task_1", "task_2", "task_3"]:
        env2 = DisasterEnv()
        env2.reset(task_id)
        for _ in range(30):
            r = env2.step(ActionModel(action="wait"))
            if r.done:
                break
        final = env2.state()
        score = grade_episode(final["event_log"], final, task_id)
        total += 1
        passed += test(
            f"grader {task_id} returns float in [0, 1]",
            isinstance(score, float) and 0.0 <= score <= 1.0,
            f"got {score}"
        )

    # ------------------------------------------------------------------
    # Test 7: compute_episode_score maps correctly
    # ------------------------------------------------------------------
    score_bad = compute_episode_score(-10.0, 10)
    score_good = compute_episode_score(10.0, 10)
    total += 1
    passed += test(
        "compute_episode_score: bad agent scores < 0.5",
        score_bad < 0.5,
        f"got {score_bad:.4f}"
    )
    total += 1
    passed += test(
        "compute_episode_score: good agent scores > 0.5",
        score_good > 0.5,
        f"got {score_good:.4f}"
    )

    # ------------------------------------------------------------------
    # Test 8: Blocked zone returns 'blocked' result
    # ------------------------------------------------------------------
    env3 = DisasterEnv()
    env3.reset("task_2")  # task_2 has blocked zones B and C
    block_action = ActionModel(action="deploy_team", to_zone="B", units=1)
    result = env3.step(block_action)
    total += 1
    passed += test(
        "deploying to blocked zone returns 'blocked'",
        result.observation.last_action_result == "blocked"
    )

    # ------------------------------------------------------------------
    # Test 9: Airlift bypasses road block
    # ------------------------------------------------------------------
    env4 = DisasterEnv()
    env4.reset("task_2")
    airlift_action = ActionModel(action="airlift", to_zone="B", type="rescue")
    result = env4.step(airlift_action)
    total += 1
    passed += test(
        "airlift bypasses blocked zone (returns success)",
        result.observation.last_action_result == "success"
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("All tests passed. Ready for Day 3.")
    else:
        print(f"{total - passed} test(s) failed. Fix before proceeding.")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    ok = run_all_tests()
    sys.exit(0 if ok else 1)
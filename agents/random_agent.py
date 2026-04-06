"""
random_agent.py — Random baseline agent for DisasterMan comparison.

Picks a random valid action at each step using observation constraints.
Serves as the lower-bound baseline in the Compare Agents view.
"""

from __future__ import annotations
import random
from models import ActionModel


def get_random_action(obs: dict) -> ActionModel:
    """
    Return a random valid action given the current observation.

    Constraints respected:
    - Never deploys/supplies to blocked zones
    - Never exceeds available teams or supply stock
    - Never airlifts when airlifts_remaining = 0
    - Never sends 0 units
    """
    res = obs["resources"]
    teams_available: int = res["teams_available"]
    supply_stock: int = res["supply_stock"]
    airlifts_remaining: int = res["airlifts_remaining"]

    zones = obs["zones"]

    # Build pools of valid targets for each action type
    accessible = [z for z in zones if not z["road_blocked"] and z["casualties_remaining"] > 0]
    supply_zones = [z for z in zones if not z["road_blocked"] and z["supply_gap"] > 0]
    blocked_with_cas = [z for z in zones if z["road_blocked"] and z["casualties_remaining"] > 0]
    teams_on_site = [z for z in zones if z["teams_present"] > 0]

    # Build candidate action list (only include what's actually possible)
    candidates: list[str] = ["wait"]
    if teams_available > 0 and accessible:
        candidates.append("deploy_team")
    if supply_stock > 0 and supply_zones:
        candidates.append("send_supplies")
    if airlifts_remaining > 0 and (blocked_with_cas or accessible):
        candidates.append("airlift")
    if teams_on_site:
        candidates.append("recall_team")

    choice = random.choice(candidates)

    if choice == "deploy_team" and accessible:
        target = random.choice(accessible)
        units = random.randint(1, min(teams_available, 3))
        return ActionModel(action="deploy_team", to_zone=target["zone_id"], units=units)

    if choice == "send_supplies" and supply_zones:
        target = random.choice(supply_zones)
        max_units = min(target["supply_gap"], supply_stock)
        units = random.randint(1, max(1, max_units))
        return ActionModel(action="send_supplies", to_zone=target["zone_id"], units=units)

    if choice == "airlift":
        pool = blocked_with_cas if blocked_with_cas else accessible
        if pool:
            target = random.choice(pool)
            return ActionModel(action="airlift", to_zone=target["zone_id"], type="rescue")

    if choice == "recall_team" and teams_on_site:
        target = random.choice(teams_on_site)
        units = random.randint(1, target["teams_present"])
        return ActionModel(action="recall_team", from_zone=target["zone_id"], units=units)

    return ActionModel(action="wait")


def run_random_task(task_id: str) -> dict:
    """
    Run a full episode using random actions. Returns step-by-step data.

    Returns:
        {task_id, final_score, cumulative_reward, steps_taken, steps: [...]}
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
        action = get_random_action(obs_dict)
        result = env.step(action)
        total_reward += result.reward

        steps_data.append({
            "step": obs_dict["step_number"],
            "observation": obs_dict,
            "action": action.model_dump(),
            "reward": round(result.reward, 4),
            "reasoning": {
                "pytorch_scores": zone_scores,
                "triage_summary": "Random agent — no triage analysis",
                "plan_decision": "Random valid action selected",
                "action_rationale": f"Randomly chose: {action.action}"
                    + (f" → zone {action.to_zone or action.from_zone}" if (action.to_zone or action.from_zone) else ""),
            },
        })

        obs = result.observation
        if result.done:
            break

    final_state = env.state()
    score = grade_episode(final_state["event_log"], final_state, task_id)

    return {
        "task_id": task_id,
        "agent": "random",
        "final_score": round(score, 4),
        "cumulative_reward": round(total_reward, 4),
        "steps_taken": len(steps_data),
        "steps": steps_data,
    }

"""
inference.py — Baseline agent using OpenAI API client against DisasterEnv.
Owner: Raj Yadav
Reads OPENAI_API_KEY from environment variables.
Produces reproducible baseline scores on all 3 tasks.
Run: python inference.py
"""

from __future__ import annotations
import os
import json
import time
from openai import OpenAI

from environment import DisasterEnv
from models import ActionModel
from graders import grade_episode

# Switched to Groq API (High rate limits, 100% free Llama 3)
# Requires GROQ_API_KEY in environment variables
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY", "")
)

SYSTEM_PROMPT = """You are an AI disaster relief coordinator.
You control rescue teams, supply trucks, and airlifts to respond to a disaster.

WORLD:
- Multiple zones have casualties and supply needs.
- Rescue teams stationed at a zone rescue casualties each step.
- Supplies close the supply gap in a zone.
- Airlifts are rare — they bypass road blocks. Use them wisely.
- Critical deadline: some zones have time-sensitive casualties. Prioritize high-severity zones.
- False SOS: some SOS signals are communication errors with no real casualties. Do not waste resources on low-severity zones that receive no benefit.

YOUR GOAL:
- Maximize casualties rescued
- Close supply gaps efficiently
- Avoid wasting resources on false SOS zones
- Respond quickly to high-severity zones

VALID ACTIONS (respond with EXACTLY ONE JSON object, nothing else):
{"action": "deploy_team", "to_zone": "<zone_id>", "units": <int>}
{"action": "send_supplies", "to_zone": "<zone_id>", "units": <int>}
{"action": "airlift", "to_zone": "<zone_id>", "type": "rescue" | "supply"}
{"action": "recall_team", "from_zone": "<zone_id>", "units": <int>}
{"action": "wait"}

RULES:
- You cannot deploy to road-blocked zones (use airlift to bypass).
- You cannot use more teams/supplies than available.
- Respond ONLY with valid JSON. No explanation, no markdown, no extra text.
"""


def obs_to_prompt(obs: dict) -> str:
    """Format observation as a clear prompt string for the LLM."""
    lines = [
        f"STEP {obs['step_number']} of {obs['step_number'] + obs['steps_remaining']} | "
        f"Weather: {obs['weather']} | Last action: {obs['last_action_result']}",
        "",
        f"RESOURCES: {obs['resources']['teams_available']} teams available | "
        f"{obs['resources']['supply_stock']} supply units | "
        f"{obs['resources']['airlifts_remaining']} airlifts | "
        f"In transit: {obs['resources']['teams_in_transit']}",
        "",
        "ZONES:",
    ]
    for z in obs["zones"]:
        status = "BLOCKED" if z["road_blocked"] else "accessible"
        sos = " [SOS]" if z["sos_active"] else ""
        lines.append(
            f"  Zone {z['zone_id']}{sos}: {z['casualties_remaining']} casualties | "
            f"supply gap {z['supply_gap']} | severity {z['severity']:.2f} | "
            f"{z['teams_present']} teams | {status}"
        )
    lines.append("")
    lines.append("What is your next action? Respond with JSON only.")
    return "\n".join(lines)


def get_agent_action(obs: dict, history: list[dict]) -> ActionModel:
    """Call Meta Llama 3 via Groq API with current observation, parse and return ActionModel."""
    history.append({"role": "user", "content": obs_to_prompt(obs)})

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        temperature=0.1,          # deterministic — reproducible scores
        max_tokens=100,
        response_format={"type": "json_object"},  # Groq fully supports strict JSON mode!
    )
    raw = response.choices[0].message.content.strip()
    history.append({"role": "assistant", "content": raw})

    # Strip markdown JSON fences often produced by Llama
    parsed_raw = raw
    if parsed_raw.startswith("```json"):
        parsed_raw = parsed_raw[7:]
    elif parsed_raw.startswith("```"):
        parsed_raw = parsed_raw[3:]
    if parsed_raw.endswith("```"):
        parsed_raw = parsed_raw[:-3]
    parsed_raw = parsed_raw.strip()

    try:
        data = json.loads(parsed_raw)
        # Fix common Llama 3 hallucination where it outputs 'Zone A' instead of 'A'
        if isinstance(data.get("to_zone"), str) and data["to_zone"].startswith("Zone "):
            data["to_zone"] = data["to_zone"][5:]
        if isinstance(data.get("from_zone"), str) and data["from_zone"].startswith("Zone "):
            data["from_zone"] = data["from_zone"][5:]
        return ActionModel(**data)
    except Exception as e:
        print(f"\n[DEBUG] Action parse/validation error: {e}\nRaw Llama output was: {raw}\n")
        return ActionModel(action="wait")


def run_task(task_id: str, verbose: bool = True) -> dict:
    """
    Run the baseline agent on one task. Returns result dict with score.
    """
    env = DisasterEnv()
    obs = env.reset(task_id)
    history: list[dict] = []
    total_reward = 0.0
    step = 0

    if verbose:
        print(f"\n{'='*60}")
        print(f"Task: {task_id}")
        print(f"{'='*60}")

    while True:
        obs_dict = obs.model_dump()
        action = get_agent_action(obs_dict, history)

        result = env.step(action)
        total_reward += result.reward
        step += 1

        if verbose:
            print(
                f"Step {step:02d} | action={action.action:15s} to={action.to_zone} units={action.units} result={result.observation.last_action_result} | "
                f"reward={result.reward:+.3f} | cumulative={total_reward:+.3f}"
            )

        obs = result.observation
        if result.done:
            break

        time.sleep(0.3)  # rate limit buffer

    # Grade the episode
    final_state = env.state()
    from graders import grade_episode
    score = grade_episode(final_state["event_log"], final_state, task_id)

    if verbose:
        print(f"\nFinal grader score: {score:.4f}")
        print(f"Cumulative reward:  {total_reward:.4f}")

    return {
        "task_id": task_id,
        "grader_score": score,
        "cumulative_reward": total_reward,
        "steps_taken": step,
    }


def run_baseline() -> dict:
    """
    Run baseline agent on all 3 tasks. Entry point for /baseline endpoint.
    Returns all scores — reproducible with temperature=0.
    """
    results = {}
    for task_id in ["task_1", "task_2", "task_3"]:
        try:
            result = run_task(task_id, verbose=True)
            results[task_id] = result
        except Exception as e:
            results[task_id] = {"error": str(e), "grader_score": 0.0}
    return results


if __name__ == "__main__":
    scores = run_baseline()
    print("\n" + "="*60)
    print("BASELINE SCORES SUMMARY")
    print("="*60)
    for task_id, r in scores.items():
        score = r.get("grader_score", 0.0)
        print(f"{task_id}: {score:.4f}")
"""
planner_agent.py — Strategic Multi-Step Planner for DisasterMan v3.

Stage 3 of the 4-stage pipeline:
  PyTorch ZoneScorer → Triage Agent → [Planner Agent] → Action Agent

The Planner receives the observation, triage report, and PyTorch zone scores,
then outputs a 3-step lookahead allocation plan. This transforms the agent from
reactive (one step at a time) to strategic (sequence-aware resource allocation).

Always uses llama-3.3-70b-versatile for maximum planning quality on all tasks.
"""

from __future__ import annotations
import json
from openai import OpenAI

PLANNER_SYSTEM = """You are a strategic disaster relief RESOURCE PLANNER with 3-step lookahead.
You receive the current situation, a triage report, and PyTorch-computed zone priority scores.
Output a forward-looking resource allocation plan.

Output EXACTLY this JSON structure (no extra fields, no markdown, no explanation):
{
  "step_plan": [
    {"step_offset": 1, "action": "deploy_team|send_supplies|airlift|recall_team|wait", "zone": "X", "units": N, "reason": "one sentence"},
    {"step_offset": 2, "action": "...", "zone": "X_or_null", "units": N_or_null, "reason": "one sentence"},
    {"step_offset": 3, "action": "...", "zone": "X_or_null", "units": N_or_null, "reason": "one sentence"}
  ],
  "primary_zone": "zone_id of highest priority zone to act on NOW",
  "primary_action_type": "deploy_team|send_supplies|airlift|recall_team|wait",
  "recall_candidates": ["zone_id with teams but completed or low-value"],
  "critical_decision": "the single most important allocation decision this turn in one sentence",
  "airlift_target": "zone_id to use next airlift on, or null if not needed"
}

PLANNING RULES (apply strictly):
1. NEVER include a false SOS zone (score=0.0) in any planned action. They are traps.
2. NEVER plan deploy_team or send_supplies to a road_blocked zone — only airlift works.
3. NEVER plan more units than available: check teams_available, supply_stock, airlifts_remaining.
4. Zones with teams_present=0 AND casualties > 0 are your top priority — they burn time every step.
5. Airlift = rare resource. Only use it for: blocked zone AND severity >= 0.75.
6. If a zone is completed (casualties=0 AND supply_gap=0), add it to recall_candidates.
7. Supply rule: send exactly supply_gap units — no more (waste), no less (undershoot).
8. Team rule: 2 teams for high severity (>=0.75), 1 team for lower severity. Scale up for large zones.
9. Sequence logic: if a team needs to recall before redeploying, plan recall in step_offset 1.
10. If steps_remaining <= 3, abandon low-priority zones. All-in on highest score zone only.
"""


def run_planner(
    obs: dict,
    triage: dict,
    zone_scores: list[dict],
    client: OpenAI,
) -> dict:
    """
    Run strategic 3-step planner using Llama 3.3 70B.

    Args:
        obs: Current observation dict (from env.step())
        triage: Triage report from triage_agent.run_triage()
        zone_scores: Sorted list from zone_scorer.score_zones()
        client: OpenAI-compatible Groq client

    Returns:
        Plan dict with step_plan, primary_zone, primary_action_type, etc.
        Falls back to a safe heuristic plan on any parsing error.
    """
    step = obs["step_number"]
    total_steps = step + obs["steps_remaining"]
    res = obs["resources"]

    # Build zone score lookup
    score_by_id = {z["zone_id"]: z for z in zone_scores}

    # Format PyTorch scores block
    score_lines: list[str] = []
    for zs in zone_scores:
        if zs["is_false_sos_suspect"]:
            score_lines.append(f"  Zone {zs['zone_id']}: score=0.000 [FALSE SOS — DO NOT PLAN]")
        else:
            score_lines.append(f"  Zone {zs['zone_id']}: score={zs['score']:.3f}")

    # Format triage info
    deadlines = triage.get("deadline_alerts", [])
    reserve_airlift = triage.get("reserve_airlift_for")
    weather_warn = triage.get("weather_warning", "")
    deadline_labels = [
        f"{d['zone_id']}({d.get('steps_until_deadline', '?')} steps)"
        for d in deadlines
    ]

    # Build prompt
    lines = [
        f"Step {step} of {total_steps} | Weather: {obs['weather']} | Steps left: {obs['steps_remaining']}",
        f"Resources: {res['teams_available']} teams available | {res['supply_stock']} supply | {res['airlifts_remaining']} airlifts",
        f"Teams in transit (arriving next step): {res.get('teams_in_transit', {})}",
        "",
        "=== PyTorch Zone Priority Scores (highest urgency first) ===",
        *score_lines,
        "",
        "=== Triage Report ===",
        f"Deadline alerts (CRITICAL): {deadline_labels}",
        f"Airlift reserved for: {reserve_airlift or 'none'}",
    ]
    if weather_warn:
        lines.append(f"Weather warning: {weather_warn}")

    lines += ["", "=== Zone Details ==="]
    for z in obs["zones"]:
        zs = score_by_id.get(z["zone_id"])
        if zs and zs["is_false_sos_suspect"]:
            lines.append(f"  Zone {z['zone_id']}: [FALSE SOS — SKIP]")
            continue

        blocked_tag = " [BLOCKED]" if z["road_blocked"] else ""
        teams_tag = " [NO TEAMS]" if z["teams_present"] == 0 and z["casualties_remaining"] > 0 else ""
        done_tag = " [DONE]" if z["casualties_remaining"] == 0 and z["supply_gap"] == 0 else ""
        lines.append(
            f"  Zone {z['zone_id']}{blocked_tag}{teams_tag}{done_tag}: "
            f"casualties={z['casualties_remaining']} supply_gap={z['supply_gap']} "
            f"severity={z['severity']:.2f} teams_present={z['teams_present']}"
        )

    lines.append("\nCreate your 3-step allocation plan. Output JSON only:")

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM},
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.0,
            max_tokens=700,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        plan = json.loads(raw)
        return plan

    except Exception as e:
        print(f"[PLANNER ERROR] {e}")
        return _fallback_plan(zone_scores, obs)


def _fallback_plan(zone_scores: list[dict], obs: dict) -> dict:
    """Deterministic fallback plan when LLM fails. Uses PyTorch scores directly."""
    top_real = next((z for z in zone_scores if not z["is_false_sos_suspect"]), None)
    top_id = top_real["zone_id"] if top_real else None

    # Find a recall candidate: zone with teams but completed
    recall_candidates = [
        z["zone_id"] for z in obs["zones"]
        if z["teams_present"] > 0 and z["casualties_remaining"] == 0 and z["supply_gap"] == 0
    ]

    # Determine best action for top zone
    top_zone_obs = next((z for z in obs["zones"] if z["zone_id"] == top_id), None)
    action_type = "wait"
    if top_zone_obs:
        if top_zone_obs["road_blocked"] and obs["resources"]["airlifts_remaining"] > 0:
            action_type = "airlift"
        elif not top_zone_obs["road_blocked"] and obs["resources"]["teams_available"] > 0:
            action_type = "deploy_team"
        elif not top_zone_obs["road_blocked"] and top_zone_obs["supply_gap"] > 0:
            action_type = "send_supplies"

    return {
        "step_plan": [
            {"step_offset": 1, "action": action_type, "zone": top_id, "units": 2, "reason": "fallback heuristic"},
        ],
        "primary_zone": top_id,
        "primary_action_type": action_type,
        "recall_candidates": recall_candidates,
        "critical_decision": f"Fallback: act on highest PyTorch score zone ({top_id})",
        "airlift_target": None,
    }

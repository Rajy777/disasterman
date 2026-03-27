"""
action_agent.py — Action Coordinator Agent for DisasterMan v2.
Receives observation + triage report, returns a single ActionModel.
"""
from __future__ import annotations
import json
from openai import OpenAI
from models import ActionModel

ACTION_SYSTEM = """You are a disaster relief ACTION COORDINATOR.
You receive the current situation AND a triage analyst report.
Your job: choose exactly ONE optimal action.

VALID ACTIONS (respond with EXACTLY ONE JSON object, nothing else):
{"action": "deploy_team", "to_zone": "<zone_id>", "units": <int>}
{"action": "send_supplies", "to_zone": "<zone_id>", "units": <int>}
{"action": "airlift", "to_zone": "<zone_id>", "type": "rescue"}
{"action": "airlift", "to_zone": "<zone_id>", "type": "supply"}
{"action": "recall_team", "from_zone": "<zone_id>", "units": <int>}
{"action": "wait"}

STRICT DECISION RULES (apply in order):
1. NEVER send ANY resource to a zone listed in FALSE_SOS — it wastes resources.
2. NEVER deploy_team or send_supplies to a BLOCKED zone — use airlift instead.
3. NEVER exceed available teams or supply stock.
4. If a deadline_alert zone has NO teams → deploy_team there immediately (top priority).
5. If a blocked high-severity zone has NO teams → use airlift rescue (if available).
6. If a zone has teams but large supply_gap → send_supplies.
7. If a zone is fully rescued and supplied → recall_team from it.
8. If you have spare teams → deploy to the next priority zone.
9. Use "wait" ONLY when all viable zones are attended and no better option exists.
10. "units" for deploy_team: start with 2, scale up for high-severity or large casualty zones.
11. "units" for send_supplies: send enough to close the gap (supply_gap value), don't overshoot.
"""


def get_action(
    obs: dict,
    triage: dict,
    history: list[dict],
    client: OpenAI,
    model: str,
) -> ActionModel:
    """
    Get single action from Action Agent.
    Uses rolling 3-exchange history (6 messages max) to prevent context bloat.
    """
    false_sos = triage.get("false_sos_suspects", [])
    priorities = triage.get("priority_zones", [])[:4]
    deadlines = triage.get("deadline_alerts", [])
    reserve = triage.get("reserve_airlift_for")
    weather_warn = triage.get("weather_warning", "")

    lines = [
        f"STEP {obs['step_number']} | Weather: {obs['weather']} | Last result: {obs['last_action_result']}",
        f"RESOURCES: {obs['resources']['teams_available']} teams | "
        f"{obs['resources']['supply_stock']} supply | "
        f"{obs['resources']['airlifts_remaining']} airlifts",
        "",
        "=== TRIAGE REPORT ===",
        f"Priority zones: {[p['zone_id'] + ' -> ' + p.get('action_type', '?') for p in priorities]}",
        f"FALSE SOS (NEVER touch): {false_sos}",
        f"DEADLINE ALERTS: {[d['zone_id'] + ' (' + str(d.get('steps_until_deadline', '?')) + ' steps)' for d in deadlines]}",
        f"Reserve airlift for: {reserve}",
    ]
    if weather_warn:
        lines.append(f"Weather warning: {weather_warn}")

    lines += ["", "=== ALL ZONES ==="]
    for z in obs["zones"]:
        if z["zone_id"] in false_sos:
            lines.append(f"  Zone {z['zone_id']}: [FALSE SOS — SKIP]")
        else:
            blocked = "BLOCKED" if z["road_blocked"] else "ok"
            lines.append(
                f"  Zone {z['zone_id']}: cas={z['casualties_remaining']} "
                f"gap={z['supply_gap']} sev={z['severity']:.2f} "
                f"teams={z['teams_present']} [{blocked}]"
            )

    lines.append("\nChoose ONE action. Output JSON only:")
    user_msg = "\n".join(lines)

    # Rolling history: keep last 3 exchanges (6 messages) to limit context
    history.append({"role": "user", "content": user_msg})
    if len(history) > 6:
        history[:] = history[-6:]

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": ACTION_SYSTEM}] + history,
            temperature=0.0,
            max_tokens=120,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": raw})

        data = json.loads(raw)
        # Fix common Llama hallucination: "Zone A" → "A"
        for field in ("to_zone", "from_zone"):
            if isinstance(data.get(field), str) and data[field].startswith("Zone "):
                data[field] = data[field][5:]

        return ActionModel(**data)

    except Exception as e:
        print(f"[ACTION ERROR] {e}")
        return ActionModel(action="wait")

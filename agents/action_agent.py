"""
action_agent.py — Action Coordinator Agent for DisasterMan v3.

Stage 4 of the 4-stage pipeline:
  PyTorch ZoneScorer → Triage Agent → Planner Agent → [Action Agent]

Key v3 improvements:
  - Receives planner's step_plan as structured input (sequence-aware)
  - Hard constraint validator: eliminates hallucinations BEFORE returning ActionModel
  - Deterministic fallback heuristic when LLM produces invalid actions
  - Explicit resource constraint injection in every prompt
"""

from __future__ import annotations
import json
from openai import OpenAI
from models import ActionModel

ACTION_SYSTEM = """You are a disaster relief ACTION COORDINATOR.
You receive the situation, triage report, planner's allocation plan, and zone scores.
Choose exactly ONE action to execute RIGHT NOW (step_offset=1 from the plan).

VALID ACTIONS — respond with EXACTLY ONE JSON object, nothing else:
{"action": "deploy_team", "to_zone": "<zone_id>", "units": <int>}
{"action": "send_supplies", "to_zone": "<zone_id>", "units": <int>}
{"action": "airlift", "to_zone": "<zone_id>", "type": "rescue"}
{"action": "airlift", "to_zone": "<zone_id>", "type": "supply"}
{"action": "recall_team", "from_zone": "<zone_id>", "units": <int>}
{"action": "wait"}

HARD CONSTRAINTS (violating these causes immediate failure):
- NEVER use a zone_id not in the VALID ZONES list below.
- NEVER deploy_team or send_supplies to a BLOCKED zone (road_blocked=True).
- NEVER use more teams than TEAMS_AVAILABLE.
- NEVER use more supply than SUPPLY_STOCK.
- NEVER spend resources on FALSE_SOS zones.
- NEVER use airlift if AIRLIFTS_REMAINING = 0.

DECISION PRIORITY (apply in order):
1. Execute planner's step_offset=1 action if it satisfies all hard constraints.
2. If plan action violates a constraint, pick the next best action from planner.
3. Deadline zone with no teams and accessible → deploy_team immediately.
4. Blocked high-severity zone + airlift available → airlift rescue.
5. Zone with teams but large supply_gap → send_supplies (cap at supply_gap exactly).
6. Completed zone with teams still present → recall_team.
7. Spare teams + unattended accessible zone → deploy_team.
8. wait is ONLY acceptable when every zone is attended or completed.
"""


def _fix_zone_id(value: object) -> str | None:
    """Strip 'Zone ' prefix hallucinated by some Llama variants."""
    if not isinstance(value, str):
        return None
    return value[5:] if value.startswith("Zone ") else value


def _validate_and_fix(
    data: dict,
    obs: dict,
    false_sos: list[str],
    zone_scores: "list[dict] | None",
) -> "ActionModel | None":
    """
    Hard constraint validator. Returns a valid ActionModel or None if irrecoverable.
    All hallucination fixes and constraint checks live here — not in the LLM prompt alone.
    """
    # Fix zone ID hallucinations first
    for field in ("to_zone", "from_zone"):
        data[field] = _fix_zone_id(data.get(field))

    valid_zone_ids = {z["zone_id"] for z in obs["zones"]}
    blocked_zone_ids = {z["zone_id"] for z in obs["zones"] if z["road_blocked"]}
    teams_available = obs["resources"]["teams_available"]
    supply_stock = obs["resources"]["supply_stock"]
    airlifts_remaining = obs["resources"]["airlifts_remaining"]

    action = data.get("action", "wait")

    if action == "deploy_team":
        zone = data.get("to_zone")
        units = data.get("units", 1)
        if not isinstance(units, int) or units < 1:
            units = 1
        if zone not in valid_zone_ids:
            return None
        if zone in false_sos:
            return None
        if zone in blocked_zone_ids:
            return None  # can't deploy to blocked zone
        units = min(units, teams_available)
        if units < 1:
            return None  # no teams available
        return ActionModel(action="deploy_team", to_zone=zone, units=units)

    if action == "send_supplies":
        zone = data.get("to_zone")
        units = data.get("units", 1)
        if not isinstance(units, int) or units < 1:
            units = 1
        if zone not in valid_zone_ids:
            return None
        if zone in false_sos:
            return None
        if zone in blocked_zone_ids:
            return None
        zone_obs = next((z for z in obs["zones"] if z["zone_id"] == zone), None)
        if zone_obs:
            units = min(units, zone_obs["supply_gap"])  # never overshoot
        units = min(units, supply_stock)
        if units < 1:
            return None
        return ActionModel(action="send_supplies", to_zone=zone, units=units)

    if action == "airlift":
        zone = data.get("to_zone")
        airlift_type = data.get("type", "rescue")
        if zone not in valid_zone_ids:
            return None
        if zone in false_sos:
            return None
        if airlifts_remaining < 1:
            return None
        if airlift_type not in ("rescue", "supply"):
            airlift_type = "rescue"
        return ActionModel(action="airlift", to_zone=zone, type=airlift_type)

    if action == "recall_team":
        zone = data.get("from_zone")
        units = data.get("units", 1)
        if not isinstance(units, int) or units < 1:
            units = 1
        if zone not in valid_zone_ids:
            return None
        zone_obs = next((z for z in obs["zones"] if z["zone_id"] == zone), None)
        if zone_obs:
            units = min(units, zone_obs["teams_present"])
        if units < 1:
            return None
        return ActionModel(action="recall_team", from_zone=zone, units=units)

    if action == "wait":
        return ActionModel(action="wait")

    return None


def _deterministic_fallback(
    obs: dict,
    triage: dict,
    zone_scores: "list[dict] | None",
    false_sos: list[str],
) -> ActionModel:
    """
    Pure-logic fallback when LLM output is unusable.
    Applies the same priority rules as the LLM system prompt but deterministically.
    """
    teams_available = obs["resources"]["teams_available"]
    supply_stock = obs["resources"]["supply_stock"]
    airlifts_remaining = obs["resources"]["airlifts_remaining"]

    # Build zone lookup
    zone_map = {z["zone_id"]: z for z in obs["zones"]}

    # Rule 1: Recall from completed zones to free teams
    for z in obs["zones"]:
        if z["zone_id"] in false_sos:
            continue
        if z["teams_present"] > 0 and z["casualties_remaining"] == 0 and z["supply_gap"] == 0:
            return ActionModel(action="recall_team", from_zone=z["zone_id"], units=z["teams_present"])

    # Rule 2: Deadline zone with no teams + accessible
    for alert in triage.get("deadline_alerts", []):
        zid = alert.get("zone_id")
        if zid in false_sos or zid not in zone_map:
            continue
        z = zone_map[zid]
        if z["teams_present"] == 0 and not z["road_blocked"] and teams_available > 0:
            return ActionModel(action="deploy_team", to_zone=zid, units=min(2, teams_available))

    # Rule 3: Blocked high-severity zone + airlift available
    reserve = triage.get("reserve_airlift_for")
    if reserve and reserve not in false_sos and airlifts_remaining > 0:
        z = zone_map.get(reserve)
        if z and z["road_blocked"] and z["casualties_remaining"] > 0:
            return ActionModel(action="airlift", to_zone=reserve, type="rescue")

    # Rule 4: Use PyTorch scores — highest priority zone with unmet needs
    ordered_zones = zone_scores if zone_scores else []
    for zs in ordered_zones:
        zid = zs["zone_id"]
        if zs["is_false_sos_suspect"] or zid in false_sos:
            continue
        z = zone_map.get(zid)
        if not z:
            continue
        # Send supplies if team is present but supply gap remains
        if z["teams_present"] > 0 and z["supply_gap"] > 0 and not z["road_blocked"]:
            amt = min(z["supply_gap"], supply_stock)
            if amt > 0:
                return ActionModel(action="send_supplies", to_zone=zid, units=amt)
        # Deploy team if accessible and unattended
        if z["teams_present"] == 0 and not z["road_blocked"] and teams_available > 0 and z["casualties_remaining"] > 0:
            return ActionModel(action="deploy_team", to_zone=zid, units=min(2, teams_available))
        # Airlift if blocked + high severity
        if z["road_blocked"] and z["severity"] >= 0.75 and airlifts_remaining > 0 and z["casualties_remaining"] > 0:
            return ActionModel(action="airlift", to_zone=zid, type="rescue")

    return ActionModel(action="wait")


def get_action(
    obs: dict,
    triage: dict,
    history: list[dict],
    client: OpenAI,
    model: str,
    zone_scores: "list[dict] | None" = None,
    plan: "dict | None" = None,
) -> ActionModel:
    """
    Get single validated action. Uses rolling 3-exchange history to prevent context bloat.

    Args:
        obs: Current observation dict
        triage: Triage report from triage_agent
        history: Mutable rolling history list (modified in place)
        client: Groq/OpenAI client
        model: LLM model name
        zone_scores: Optional PyTorch zone scores for deterministic fallback
        plan: Optional planner output from planner_agent

    Returns:
        Always a valid, constraint-satisfying ActionModel.
    """
    false_sos: list[str] = triage.get("false_sos_suspects", [])
    priorities = triage.get("priority_zones", [])[:4]
    deadlines = triage.get("deadline_alerts", [])
    reserve = triage.get("reserve_airlift_for")
    weather_warn = triage.get("weather_warning", "")

    # Explicit constraint injection — LLM must see exact numbers
    res = obs["resources"]
    valid_ids = sorted(
        z["zone_id"] for z in obs["zones"] if z["zone_id"] not in false_sos
    )
    blocked_ids = [z["zone_id"] for z in obs["zones"] if z["road_blocked"]]

    lines = [
        f"STEP {obs['step_number']} | Weather: {obs['weather']} | Last: {obs['last_action_result']}",
        f"TEAMS_AVAILABLE={res['teams_available']} SUPPLY_STOCK={res['supply_stock']} AIRLIFTS_REMAINING={res['airlifts_remaining']}",
        f"VALID_ZONES: {valid_ids}",
        f"BLOCKED_ZONES (no deploy/supply): {blocked_ids}",
        f"FALSE_SOS (NEVER touch): {false_sos}",
        "",
        "=== TRIAGE ===",
        f"Priorities: {[p['zone_id'] + '->' + p.get('action_type', '?') for p in priorities]}",
        f"Deadlines: {[d['zone_id'] + '(' + str(d.get('steps_until_deadline', '?')) + 'steps)' for d in deadlines]}",
        f"Reserve airlift: {reserve}",
    ]
    if weather_warn:
        lines.append(f"Weather: {weather_warn}")

    # Include planner's step 1 recommendation
    if plan:
        step_plan = plan.get("step_plan", [])
        step1 = next((s for s in step_plan if s.get("step_offset") == 1), None)
        lines.append("")
        lines.append("=== PLANNER RECOMMENDS ===")
        if step1:
            lines.append(
                f"Step 1: {step1.get('action')} zone={step1.get('zone')} "
                f"units={step1.get('units')} | {step1.get('reason', '')}"
            )
        lines.append(f"Primary zone: {plan.get('primary_zone')} | Action: {plan.get('primary_action_type')}")
        lines.append(f"Critical decision: {plan.get('critical_decision', '')}")
        recall_cands = plan.get("recall_candidates", [])
        if recall_cands:
            lines.append(f"Recall candidates (completed zones with teams): {recall_cands}")

    lines += ["", "=== ALL ZONES ==="]
    for z in obs["zones"]:
        if z["zone_id"] in false_sos:
            lines.append(f"  {z['zone_id']}: [FALSE SOS — SKIP]")
        else:
            blocked_tag = " [BLOCKED]" if z["road_blocked"] else ""
            lines.append(
                f"  {z['zone_id']}{blocked_tag}: cas={z['casualties_remaining']} "
                f"gap={z['supply_gap']} sev={z['severity']:.2f} teams={z['teams_present']}"
            )

    lines.append("\nChoose ONE action. Output JSON only:")
    user_msg = "\n".join(lines)

    # Rolling history: keep last 3 exchanges to limit context
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
        validated = _validate_and_fix(data, obs, false_sos, zone_scores)
        if validated is not None:
            return validated

        print(f"[ACTION] LLM output failed constraint check: {data} — using fallback")

    except Exception as e:
        print(f"[ACTION ERROR] {e}")
        if history and history[-1]["role"] == "user":
            # Don't pollute history with failed exchange
            history.pop()

    return _deterministic_fallback(obs, triage, zone_scores, false_sos)

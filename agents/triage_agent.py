"""
triage_agent.py — Triage Analyst Agent for DisasterMan v2.
Analyzes observation, ranks zones by urgency, flags false SOS, warns of deadlines.
Output is structured JSON consumed by action_agent.py.
"""
from __future__ import annotations
import json
from openai import OpenAI

TRIAGE_SYSTEM = """You are a disaster relief TRIAGE ANALYST.
Analyze the current situation and output a structured JSON triage report.

Output EXACTLY this JSON structure (no extra fields, no extra text):
{
  "priority_zones": [
    {"zone_id": "X", "reason": "short reason", "action_type": "rescue|supply|airlift|recall"}
  ],
  "false_sos_suspects": ["zone_id", ...],
  "deadline_alerts": [
    {"zone_id": "X", "steps_until_deadline": N}
  ],
  "reserve_airlift_for": "zone_id or null",
  "weather_warning": "brief note or empty string"
}

ANALYSIS RULES:
1. FALSE SOS: A zone with sos_active=true but casualties_remaining=0 AND supply_gap=0
   is a false SOS signal. Add it to false_sos_suspects. Do NOT recommend resources for it.
2. DEADLINES: Flag any zone where deadline is within 2 steps as a deadline_alert.
3. BLOCKED ZONES: Road-blocked zones with severity >= 0.75 need airlift — set reserve_airlift_for.
4. PRIORITY ORDER: (a) deadline zones, (b) high-severity accessible zones, (c) blocked zones.
5. WEATHER: If storm/flood, warn that certain zones may become blocked.
6. Sort priority_zones highest urgency first (max 5 zones).
"""


def run_triage(obs: dict, client: OpenAI, model: str) -> dict:
    """
    Run triage analysis on current observation.
    Returns structured dict with zone priorities, false SOS flags, deadline alerts.
    """
    # Pre-processing: detect obvious false SOS before LLM call (heuristic)
    heuristic_false_sos = [
        z["zone_id"]
        for z in obs["zones"]
        if z["sos_active"] and z["casualties_remaining"] == 0 and z["supply_gap"] == 0
    ]

    step = obs["step_number"]
    max_step = step + obs["steps_remaining"]

    prompt_lines = [
        f"Step {step} of {max_step} | Weather: {obs['weather']}",
        f"Resources: {obs['resources']['teams_available']} teams available | "
        f"{obs['resources']['supply_stock']} supply | "
        f"{obs['resources']['airlifts_remaining']} airlifts",
        "",
        "ZONES:",
    ]

    for z in obs["zones"]:
        status = "BLOCKED" if z["road_blocked"] else "accessible"
        sos_tag = " [SOS]" if z["sos_active"] else ""
        false_tag = " *** LIKELY FALSE SOS ***" if z["zone_id"] in heuristic_false_sos else ""
        prompt_lines.append(
            f"  Zone {z['zone_id']}{sos_tag}{false_tag}: "
            f"casualties={z['casualties_remaining']} supply_gap={z['supply_gap']} "
            f"severity={z['severity']:.2f} teams_present={z['teams_present']} [{status}]"
        )

    if heuristic_false_sos:
        prompt_lines.append(
            f"\nPRE-ANALYSIS: Zones {heuristic_false_sos} have SOS active but ZERO "
            f"casualties and ZERO supply gap — almost certainly false SOS signals."
        )

    prompt_lines.append("\nProduce the triage JSON report:")
    prompt = "\n".join(prompt_lines)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TRIAGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        result = json.loads(raw)
        # Merge heuristic false SOS with LLM result
        llm_false_sos = result.get("false_sos_suspects", [])
        merged = list(set(heuristic_false_sos + llm_false_sos))
        result["false_sos_suspects"] = merged
        return result
    except Exception as e:
        print(f"[TRIAGE ERROR] {e}")
        return {
            "priority_zones": [],
            "false_sos_suspects": heuristic_false_sos,
            "deadline_alerts": [],
            "reserve_airlift_for": None,
            "weather_warning": "",
        }

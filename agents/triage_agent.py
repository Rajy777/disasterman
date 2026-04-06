"""
triage_agent.py — Triage Analyst Agent for DisasterMan v3.

Stage 2 of the 4-stage pipeline:
  PyTorch ZoneScorer → [Triage Agent] → Planner Agent → Action Agent

Enhanced v3: now accepts pre-computed PyTorch zone scores and incorporates them
into the triage analysis prompt for richer, more grounded reasoning.
"""

from __future__ import annotations
import json
from openai import OpenAI

TRIAGE_SYSTEM = """You are a disaster relief TRIAGE ANALYST.
You receive the current situation PLUS pre-computed PyTorch neural-net zone priority scores.
Output a structured triage JSON report.

Output EXACTLY this JSON (no extra fields, no markdown, no explanation):
{
  "priority_zones": [
    {"zone_id": "X", "reason": "one short reason", "action_type": "rescue|supply|airlift|recall"}
  ],
  "false_sos_suspects": ["zone_id", ...],
  "deadline_alerts": [
    {"zone_id": "X", "steps_until_deadline": N}
  ],
  "reserve_airlift_for": "zone_id or null",
  "weather_warning": "brief note or empty string"
}

TRIAGE RULES:
1. FALSE SOS: zone with sos_active=true AND casualties_remaining=0 AND supply_gap=0 → add to false_sos_suspects. NEVER recommend resources for it.
2. If PyTorch score = 0.0 for a zone → it is flagged as false SOS. Include in false_sos_suspects.
3. DEADLINES: Flag zones with high severity and no teams as deadline_alerts when steps_remaining is low.
4. BLOCKED + severity >= 0.75 → set reserve_airlift_for to that zone (if airlifts > 0).
5. PRIORITY ORDER: (a) deadline zones with no teams, (b) PyTorch top-scored unattended zones, (c) blocked high-severity zones.
6. Sort priority_zones highest urgency first. Max 5 zones.
7. WEATHER: if storm or flood, warn which zones may get blocked.
"""


def run_triage(
    obs: dict,
    client: OpenAI,
    model: str,
    zone_scores: "list[dict] | None" = None,
) -> dict:
    """
    Run triage analysis on the current observation.

    Args:
        obs: Current observation dict
        client: Groq/OpenAI-compatible client
        model: LLM model name
        zone_scores: Optional pre-computed PyTorch scores from zone_scorer.score_zones()

    Returns:
        Triage dict with priority_zones, false_sos_suspects, deadline_alerts, etc.
    """
    # Heuristic false SOS detection (zero-cost, runs before any LLM call)
    heuristic_false_sos: list[str] = [
        z["zone_id"]
        for z in obs["zones"]
        if z.get("sos_active", False)
        and z["casualties_remaining"] == 0
        and z["supply_gap"] == 0
    ]

    # Also absorb any score=0.0 zones from PyTorch scorer
    if zone_scores:
        for zs in zone_scores:
            if zs["score"] == 0.0 and zs["zone_id"] not in heuristic_false_sos:
                heuristic_false_sos.append(zs["zone_id"])

    step = obs["step_number"]
    total_steps = step + obs["steps_remaining"]
    res = obs["resources"]

    prompt_lines = [
        f"Step {step}/{total_steps} | Weather: {obs['weather']} | Steps remaining: {obs['steps_remaining']}",
        f"Resources: {res['teams_available']} teams | {res['supply_stock']} supply | {res['airlifts_remaining']} airlifts",
        "",
    ]

    # Include PyTorch scores in prompt when available
    if zone_scores:
        prompt_lines.append("=== PyTorch Zone Priority Scores (highest urgency first) ===")
        for zs in zone_scores:
            false_tag = "  *** LIKELY FALSE SOS ***" if (
                zs["is_false_sos_suspect"] or zs["zone_id"] in heuristic_false_sos
            ) else ""
            prompt_lines.append(f"  Zone {zs['zone_id']}: score={zs['score']:.3f}{false_tag}")
        prompt_lines.append("")

    prompt_lines.append("=== Zone Details ===")
    for z in obs["zones"]:
        status = "BLOCKED" if z["road_blocked"] else "accessible"
        sos_tag = " [SOS]" if z.get("sos_active") else ""
        false_tag = " *** LIKELY FALSE SOS ***" if z["zone_id"] in heuristic_false_sos else ""
        prompt_lines.append(
            f"  Zone {z['zone_id']}{sos_tag}{false_tag}: "
            f"casualties={z['casualties_remaining']} supply_gap={z['supply_gap']} "
            f"severity={z['severity']:.2f} teams_present={z['teams_present']} [{status}]"
        )

    if heuristic_false_sos:
        prompt_lines.append(
            f"\nPRE-ANALYSIS: Zones {heuristic_false_sos} have zero casualties AND zero supply gap "
            "despite active SOS — almost certainly false SOS signals."
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
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        result = json.loads(raw)

        # Union of heuristic + LLM false SOS detections
        llm_false_sos: list[str] = result.get("false_sos_suspects", [])
        result["false_sos_suspects"] = list(set(heuristic_false_sos + llm_false_sos))
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

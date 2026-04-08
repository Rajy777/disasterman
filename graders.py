"""
graders.py — Episode graders for all 3 tasks.
Owner: Krish Potanwar
All graders are pure functions: (event_log, final_state) → float in strict (0, 1).
Deterministic — same input always produces same score.

Scaler Phase 2 validator requires scores strictly between 0 and 1 (not 0.0, not 1.0),
so we clamp to (SCORE_MIN, SCORE_MAX) below.
"""

from __future__ import annotations
import math
from reward import compute_episode_score

# Scaler Phase 2 requires scores strictly in (0, 1). Never hit the endpoints.
SCORE_MIN = 1e-3   # 0.001
SCORE_MAX = 1.0 - 1e-3   # 0.999


def _strict_clamp(score: float) -> float:
    """Clamp to strictly (0, 1). Handles NaN/inf by falling back to 0.5."""
    if not math.isfinite(score):
        return 0.5
    return round(max(SCORE_MIN, min(SCORE_MAX, score)), 4)


def _base_scores(final_state: dict) -> dict:
    """Extract common scoring metrics from final state."""
    zones = [z for z in final_state["zones"] if not z["is_false_sos"]]
    total_casualties = sum(z["casualties_total"] for z in zones)
    total_rescued = sum(z["casualties_rescued"] for z in zones)
    total_supply_needed = sum(z["supply_needed"] for z in zones)
    total_supply_received = sum(min(z["supply_received"], z["supply_needed"]) for z in zones)
    total_wasted = sum(z["supply_wasted"] for z in zones)
    total_sent = total_supply_received + total_wasted
    total_critical_original = sum(
        z["casualties_critical"] for z in zones
    )

    # Critical deaths: zones where critical deadline passed and teams were absent
    critical_deaths = sum(
        1 for e in final_state["event_log"]
        if e["type"] == "critical_expired"
    )

    rescue_score = total_rescued / max(1, total_casualties)
    supply_score = total_supply_received / max(1, total_supply_needed)
    waste_ratio = total_wasted / max(1, total_sent)
    efficiency_score = 1.0 - waste_ratio

    return {
        "rescue_score": rescue_score,
        "supply_score": supply_score,
        "efficiency_score": efficiency_score,
        "critical_deaths": critical_deaths,
        "total_casualties": total_casualties,
        "total_rescued": total_rescued,
    }


def grade_task_1(event_log: list[dict], final_state: dict) -> float:
    """
    Task 1 grader — single zone flood.
    Simple: rescue completion + supply completion.
    Score = 0.6×rescue_score + 0.4×supply_score
    """
    s = _base_scores(final_state)
    raw = 0.6 * s["rescue_score"] + 0.4 * s["supply_score"]
    # Bonus: perfect rescue gets a small boost (but stays strictly below 1.0)
    if s["rescue_score"] >= 1.0:
        raw += 0.05
    return _strict_clamp(raw)


def grade_task_2(event_log: list[dict], final_state: dict) -> float:
    """
    Task 2 grader — multi-zone earthquake.
    Weighted: rescue + critical response + efficiency.
    Score = 0.5×rescue + 0.3×critical_response + 0.2×efficiency
    """
    s = _base_scores(final_state)

    zones = [z for z in final_state["zones"] if not z["is_false_sos"]]
    total_critical = sum(z["casualties_critical"] for z in zones)
    critical_deaths = s["critical_deaths"]
    critical_response = 1.0 - (critical_deaths / max(1, total_critical))

    raw = (
        0.50 * s["rescue_score"] +
        0.30 * max(0.0, critical_response) +
        0.20 * s["efficiency_score"]
    )
    return _strict_clamp(raw)


def grade_task_3(event_log: list[dict], final_state: dict) -> float:
    """
    Task 3 grader — cyclone with cascading failures + false SOS.
    Most complex: rescue + response time + airlift intelligence + false SOS penalty.
    """
    s = _base_scores(final_state)

    # Response time score: how quickly was first team deployed per zone
    zones = [z for z in final_state["zones"] if not z["is_false_sos"]]
    zone_ids = {z["zone_id"] for z in zones}
    first_response: dict[str, int] = {}
    for event in event_log:
        if event["type"] in ("deploy_team", "airlift"):
            zid = event.get("to")
            if zid and zid in zone_ids and zid not in first_response:
                first_response[zid] = event["step"]

    max_steps = final_state["max_steps"]
    if first_response:
        avg_response = sum(first_response.values()) / len(first_response)
        response_score = 1.0 - (avg_response / max_steps)
    else:
        response_score = 0.0

    # Airlift intelligence: airlifts used on blocked+critical zones
    airlift_events = [e for e in event_log if e["type"] == "airlift"]
    smart_airlifts = sum(
        1 for e in airlift_events
        if e.get("to") in zone_ids  # real zone, not false SOS
    )
    total_airlifts = len(airlift_events)
    airlift_iq = smart_airlifts / max(1, total_airlifts) if total_airlifts > 0 else 1.0

    # False SOS penalty: resources deployed to ghost zones
    false_sos_zone_ids = {z["zone_id"] for z in final_state["zones"] if z["is_false_sos"]}
    false_sos_actions = sum(
        1 for e in event_log
        if e["type"] in ("deploy_team", "send_supplies", "airlift")
        and e.get("to") in false_sos_zone_ids
    )
    total_actions = max(1, len([
        e for e in event_log
        if e["type"] in ("deploy_team", "send_supplies", "airlift")
    ]))
    false_sos_penalty = 0.15 * (false_sos_actions / total_actions)

    raw = (
        0.45 * s["rescue_score"] +
        0.25 * max(0.0, response_score) +
        0.20 * airlift_iq +
        0.10 * s["efficiency_score"]
        - false_sos_penalty
    )
    return _strict_clamp(raw)


def grade_episode(event_log: list[dict], final_state: dict, task_id: str) -> float:
    """
    Unified grader entry point. Called by /grader endpoint.
    Returns float in [0.0, 1.0].
    """
    graders = {
        "task_1": grade_task_1,
        "task_2": grade_task_2,
        "task_3": grade_task_3,
    }
    fn = graders.get(task_id)
    if fn is None:
        raise ValueError(f"Unknown task_id: {task_id}")
    return fn(event_log, final_state)
"""
reward.py — Isolated reward computation for the Disaster Relief environment.
Owner: Krish Potanwar
compute_step_reward() is a pure function — no side effects, fully unit-testable.
Formula locked from Day 1 design doc.
"""

from __future__ import annotations
import math
from models import ActionModel, RewardBreakdown


def compute_step_reward(
    zones_before: list[dict],
    zones_after: list[dict],
    action: ActionModel,
    action_result: str,
    resources_before: dict,
    resources_after: dict,
) -> RewardBreakdown:
    """
    Compute per-step reward as a RewardBreakdown.
    All inputs are plain dicts (snapshots of ZoneState) to keep this dependency-free.
    Returns RewardBreakdown with .total clamped to [−1.0, 1.0].
    """
    bd = RewardBreakdown()

    # Build lookup dicts
    before = {z["zone_id"]: z for z in zones_before}
    after  = {z["zone_id"]: z for z in zones_after}

    total_casualties = sum(z["casualties_total"] for z in zones_before if not z["is_false_sos"])
    total_critical   = sum(z["casualties_critical"] for z in zones_before if not z["is_false_sos"])
    total_supply_needed = sum(z["supply_needed"] for z in zones_before if not z["is_false_sos"])

    # ------------------------------------------------------------------
    # POSITIVE REWARDS
    # ------------------------------------------------------------------

    # R1: Rescue progress — normalized to max rescuable (teams × rate × zones attended)
    new_rescues = sum(
        max(0, after[zid]["casualties_rescued"] - before[zid]["casualties_rescued"])
        for zid in after
        if not before[zid]["is_false_sos"]
    )
    max_rescuable = max(1, sum(
        min(before[zid]["casualties_total"] - before[zid]["casualties_rescued"], before[zid]["teams_present"] * 4)
        for zid in before
        if not before[zid]["is_false_sos"] and before[zid]["teams_present"] > 0
    ))
    bd.r_rescue = 0.40 * min(1.0, new_rescues / max_rescuable) if max_rescuable > 0 else 0.0

    # R2: Supply gap closed — normalized
    supply_gap_closed = sum(
        max(0, after[zid]["supply_received"] - before[zid]["supply_received"])
        for zid in after
        if not before[zid]["is_false_sos"]
    )
    total_gap_before = max(1, sum(
        max(0, before[zid]["supply_needed"] - before[zid]["supply_received"])
        for zid in before
        if not before[zid]["is_false_sos"]
    ))
    bd.r_supply = 0.20 * min(1.0, supply_gap_closed / total_gap_before)

    # R3: Zone completion bonus — binary per newly completed zone
    newly_completed = sum(
        1 for zid in after
        if after[zid]["completed"] and not before[zid]["completed"]
        and not before[zid]["is_false_sos"]
    )
    bd.r_zone_complete = 0.15 * min(1.0, newly_completed / max(1, len(zones_before)))

    # R4: Critical rescue bonus — rescued from high-severity zones
    critical_rescues = sum(
        max(0, after[zid]["casualties_rescued"] - before[zid]["casualties_rescued"])
        for zid in after
        if before[zid]["severity"] >= 0.75 and not before[zid]["is_false_sos"]
    )
    bd.r_critical_rescue = 0.15 * min(1.0, critical_rescues / max(1, total_casualties * 0.3))

    # R5: Airlift precision — +1.0 if used on blocked+critical zone, −0.5 if wasted
    if action.action == "airlift" and action.to_zone:
        zid = action.to_zone
        if zid in before:
            zone = before[zid]
            if zone["road_blocked"] and zone["severity"] >= 0.75:
                bd.r_airlift_precision = 0.10 * 1.0   # smart use
            elif not zone["road_blocked"]:
                bd.r_airlift_precision = 0.10 * -0.5  # wasted — zone was accessible
            else:
                bd.r_airlift_precision = 0.10 * 0.3   # blocked but low severity
        else:
            bd.r_airlift_precision = 0.10 * -1.0      # invalid zone

    # ------------------------------------------------------------------
    # NEGATIVE PENALTIES
    # ------------------------------------------------------------------

    # P1: Critical casualties expired this step
    # casualties_remaining is a computed property — calculate inline from stored fields
    def remaining(z: dict) -> int:
        return z["casualties_total"] - z["casualties_rescued"]

    actual_expired = sum(
        max(0, before[zid]["casualties_critical"] - after[zid]["casualties_critical"])
        for zid in after
        if not before[zid]["is_false_sos"]
    )
    bd.p_critical_deaths = 0.40 * min(1.0, actual_expired / max(1, total_critical))

    # P2: Urgency decay — severity sum of unattended zones
    severity_unattended = sum(
        after[zid]["severity"]
        for zid in after
        if after[zid]["teams_present"] == 0
        and not after[zid]["completed"]
        and not after[zid]["is_false_sos"]
    )
    max_severity_sum = max(1, len([z for z in zones_before if not z["is_false_sos"]]))
    bd.p_urgency_decay = 0.15 * min(1.0, severity_unattended / max_severity_sum)

    # P3: Overcommitment — teams sitting in completed zones
    teams_idle_completed = sum(
        after[zid]["teams_present"]
        for zid in after
        if after[zid]["completed"]
    )
    total_teams_deployed = sum(z["teams_present"] for z in zones_after)
    bd.p_overcommitment = 0.10 * min(1.0, teams_idle_completed / max(1, total_teams_deployed))

    # P4: Supply waste — normalized ratio
    supply_sent_this_step = supply_gap_closed  # proxy: gap closed = sent useful amount
    supply_wasted_this_step = sum(
        max(0, after[zid]["supply_wasted"] - before[zid]["supply_wasted"])
        for zid in after
    )
    total_sent = supply_gap_closed + supply_wasted_this_step
    bd.p_supply_waste = 0.05 * min(1.0, supply_wasted_this_step / max(1, total_sent))

    # P5: Resources spent on false SOS zones
    resources_on_false = 0
    if action.action in ("deploy_team", "send_supplies", "airlift") and action.to_zone:
        if action.to_zone in before and before[action.to_zone]["is_false_sos"]:
            resources_on_false = action.units or 1
    total_resources_moved = (action.units or 1) if action.action != "wait" else 0
    bd.p_false_sos = 0.05 * min(1.0, resources_on_false / max(1, total_resources_moved))

    # P6: Wait penalty
    bd.p_wait = 0.05 if action.action == "wait" else 0.0

    # ------------------------------------------------------------------
    # TOTAL — clamp to [−1.0, 1.0]
    # ------------------------------------------------------------------
    raw = (
        bd.r_rescue + bd.r_supply + bd.r_zone_complete +
        bd.r_critical_rescue + bd.r_airlift_precision
        - bd.p_critical_deaths - bd.p_urgency_decay - bd.p_overcommitment
        - bd.p_supply_waste - bd.p_false_sos - bd.p_wait
    )
    bd.total = max(-1.0, min(1.0, raw))
    return bd


def compute_episode_score(cumulative_reward: float, max_steps: int) -> float:
    """
    Converts cumulative step rewards into a final grader score in [0.0, 1.0].
    Uses (tanh(normalized × 2) + 1) / 2 to spread scores across the full range.
    A mediocre agent scores ~0.35, a strong agent ~0.85.
    """
    normalized = cumulative_reward / max(1, max_steps)
    return (math.tanh(normalized * 2) + 1) / 2
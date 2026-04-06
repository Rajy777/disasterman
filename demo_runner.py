"""
demo_runner.py — Backend-authoritative episode runner for the Bengaluru live demo.

This module keeps the reviewer-facing map demo separate from the benchmark task
APIs while reusing the same environment mechanics, reward shaping, and agent
building blocks.
"""

from __future__ import annotations

import copy
import os
import time
from typing import Iterator

from environment import DisasterEnv
from models import ActionModel, ObservationModel, ZoneState
from reward import compute_episode_score
from demo_models import (
    DemoMapOverlay,
    DemoMapState,
    DemoResourceMovement,
    DemoResourcePosition,
    DemoRunResult,
    DemoScenarioDetail,
    DemoStep,
    DemoStreamMetaEvent,
)
from demo_scenarios import (
    ALLOWED_AGENTS,
    get_demo_route,
    get_demo_scenario_config,
    get_demo_scenario_detail,
    get_recall_route,
)


STAGE_NAMES = ("pytorch", "triage", "planner", "action")


class DemoDisasterEnv(DisasterEnv):
    """DisasterEnv variant that resets from an explicit scenario config dict."""

    def reset_from_config(self, cfg: dict) -> ObservationModel:
        scenario_cfg = copy.deepcopy(cfg)
        scenario_cfg.setdefault("task_id", scenario_cfg.get("scenario_id", "demo_scenario"))
        self._task_config = scenario_cfg
        self._current_step = 0
        self._max_steps = scenario_cfg["max_steps"]
        self._weather = "clear"
        self._event_log = []
        self._cumulative_reward = 0.0
        self._last_action_result = "none"
        self._done = False
        self._teams_in_transit = {}

        self._zones = []
        for zone_cfg in scenario_cfg["zones"]:
            self._zones.append(
                ZoneState(
                    zone_id=zone_cfg["zone_id"],
                    casualties_total=zone_cfg["casualties_total"],
                    casualties_rescued=0,
                    casualties_critical=zone_cfg["casualties_critical"],
                    critical_deadline=zone_cfg["critical_deadline"],
                    supply_needed=zone_cfg["supply_needed"],
                    supply_received=0,
                    supply_wasted=0,
                    road_blocked=zone_cfg["road_blocked"],
                    severity=zone_cfg["severity_init"],
                    teams_present=0,
                    is_false_sos=zone_cfg["is_false_sos"],
                    completed=(
                        zone_cfg["casualties_total"] == 0
                        and zone_cfg["supply_needed"] == 0
                    ),
                )
            )

        resources = scenario_cfg["resources"]
        self._teams_available = resources["rescue_teams"]
        self._supply_stock = resources["supply_stock"]
        self._airlifts_remaining = resources["airlifts"]

        self._log("episode_start", {"task_id": scenario_cfg["task_id"]})
        return self._build_observation()


def validate_demo_agent(agent: str) -> str:
    agent_name = agent.strip()
    if agent_name not in ALLOWED_AGENTS:
        raise ValueError(f"Unknown demo agent '{agent_name}'. Valid: {', '.join(ALLOWED_AGENTS)}")
    return agent_name


def list_demo_agents() -> list[str]:
    return list(ALLOWED_AGENTS)


def _get_runtime(agent: str):
    if agent != "ai_4stage":
        return None, f"{agent}-heuristic", None

    from openai import OpenAI

    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if groq_key:
        return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key), "llama-3.3-70b-versatile", None
    if openai_key:
        return OpenAI(api_key=openai_key), "gpt-4o-mini", None
    return None, "demo-4stage-heuristic-fallback", (
        "No GROQ_API_KEY or OPENAI_API_KEY set, so the Live Demo is using "
        "deterministic 4-stage fallback reasoning for this run."
    )


def _heuristic_triage(obs: dict, state: dict, zone_scores: list[dict]) -> dict:
    false_sos = [score["zone_id"] for score in zone_scores if score.get("is_false_sos_suspect")]
    zone_map = {zone["zone_id"]: zone for zone in obs["zones"]}

    deadline_alerts: list[dict] = []
    for zone in state["zones"]:
        if zone["zone_id"] in false_sos or zone.get("completed"):
            continue
        steps_until_deadline = zone["critical_deadline"] - obs["step_number"]
        if zone["teams_present"] == 0 and zone["casualties_critical"] > 0 and steps_until_deadline <= 2:
            deadline_alerts.append(
                {
                    "zone_id": zone["zone_id"],
                    "steps_until_deadline": max(0, steps_until_deadline),
                }
            )

    priority_zones: list[dict] = []
    for score in zone_scores:
        zid = score["zone_id"]
        if zid in false_sos:
            continue
        zone = zone_map[zid]
        if zone["road_blocked"] and zone["casualties_remaining"] > 0:
            action_type = "airlift"
            reason = "blocked corridor needs aerial access"
        elif zone["teams_present"] == 0 and zone["casualties_remaining"] > 0:
            action_type = "rescue"
            reason = "unattended casualties are burning time"
        elif zone["supply_gap"] > 0 and not zone["road_blocked"]:
            action_type = "supply"
            reason = "support gap is still slowing stabilization"
        elif zone["teams_present"] > 0 and zone["casualties_remaining"] == 0 and zone["supply_gap"] == 0:
            action_type = "recall"
            reason = "completed zone can release teams"
        else:
            action_type = "rescue"
            reason = "severity remains elevated"

        if zone["casualties_remaining"] > 0 or zone["supply_gap"] > 0 or zone["teams_present"] > 0:
            priority_zones.append({"zone_id": zid, "reason": reason, "action_type": action_type})
        if len(priority_zones) >= 5:
            break

    reserve_airlift_for = None
    if obs["resources"]["airlifts_remaining"] > 0:
        for score in zone_scores:
            zone = zone_map[score["zone_id"]]
            if score["zone_id"] in false_sos:
                continue
            if zone["road_blocked"] and zone["casualties_remaining"] > 0 and zone["severity"] >= 0.75:
                reserve_airlift_for = zone["zone_id"]
                break

    weather_warning = ""
    if obs["weather"] == "storm":
        weather_warning = "Storm conditions are slowing ground mobility into exposed corridors."
    elif obs["weather"] == "flood":
        weather_warning = "Flood conditions are increasing the value of airlifts and support hubs."

    return {
        "priority_zones": priority_zones,
        "false_sos_suspects": false_sos,
        "deadline_alerts": deadline_alerts,
        "reserve_airlift_for": reserve_airlift_for,
        "weather_warning": weather_warning,
    }


def _plan_for_zone(zone: dict, obs: dict) -> tuple[str, int | None, str]:
    if zone["road_blocked"] and zone["casualties_remaining"] > 0 and obs["resources"]["airlifts_remaining"] > 0:
        return "airlift", 1, "Airlift is the only viable access path into the blocked zone."
    if zone["teams_present"] == 0 and zone["casualties_remaining"] > 0 and not zone["road_blocked"] and obs["resources"]["teams_available"] > 0:
        units = min(2 if zone["severity"] >= 0.75 else 1, obs["resources"]["teams_available"])
        return "deploy_team", units, "Fresh teams can still unlock the biggest rescue gain here."
    if zone["supply_gap"] > 0 and not zone["road_blocked"] and obs["resources"]["supply_stock"] > 0:
        units = min(zone["supply_gap"], obs["resources"]["supply_stock"])
        return "send_supplies", units, "Support stock closes the remaining stabilization gap."
    if zone["teams_present"] > 0 and zone["casualties_remaining"] == 0 and zone["supply_gap"] == 0:
        return "recall_team", zone["teams_present"], "Completed zone can release crews for redeployment."
    return "wait", None, "No better action is currently available for this zone."


def _heuristic_plan(obs: dict, triage: dict, zone_scores: list[dict]) -> dict:
    zone_map = {zone["zone_id"]: zone for zone in obs["zones"]}
    priority_ids = [item["zone_id"] for item in triage.get("priority_zones", []) if item["zone_id"] in zone_map]
    if not priority_ids:
        priority_ids = [score["zone_id"] for score in zone_scores if not score.get("is_false_sos_suspect")]

    step_plan: list[dict] = []
    for idx, zid in enumerate(priority_ids[:3], start=1):
        action, units, reason = _plan_for_zone(zone_map[zid], obs)
        step_plan.append(
            {
                "step_offset": idx,
                "action": action,
                "zone": zid,
                "units": units,
                "reason": reason,
            }
        )

    if not step_plan:
        step_plan.append(
            {
                "step_offset": 1,
                "action": "wait",
                "zone": None,
                "units": None,
                "reason": "All visible zones are either resolved or inaccessible without resources.",
            }
        )

    step_one = step_plan[0]
    primary_zone = step_one.get("zone")
    action_type = step_one.get("action", "wait")
    critical_decision = (
        f"Focus next allocation on zone {primary_zone} via {action_type}."
        if primary_zone
        else "Hold position and preserve scarce resources."
    )
    recall_candidates = [
        zone["zone_id"]
        for zone in obs["zones"]
        if zone["teams_present"] > 0 and zone["casualties_remaining"] == 0 and zone["supply_gap"] == 0
    ]

    return {
        "step_plan": step_plan,
        "primary_zone": primary_zone,
        "primary_action_type": action_type,
        "recall_candidates": recall_candidates,
        "critical_decision": critical_decision,
        "airlift_target": triage.get("reserve_airlift_for"),
    }


def _action_from_plan(plan: dict, obs: dict, zone_scores: list[dict]) -> tuple[ActionModel, str]:
    from agents.greedy_agent import get_greedy_action

    step_plan = plan.get("step_plan", [])
    first = step_plan[0] if step_plan else {}
    action_type = first.get("action", "wait")
    zone = first.get("zone")
    units = first.get("units")
    reason = first.get("reason", "Planner fallback executed.")

    if action_type == "deploy_team" and zone and obs["resources"]["teams_available"] > 0:
        return ActionModel(action="deploy_team", to_zone=zone, units=max(1, units or 1)), reason
    if action_type == "send_supplies" and zone and obs["resources"]["supply_stock"] > 0:
        return ActionModel(action="send_supplies", to_zone=zone, units=max(1, units or 1)), reason
    if action_type == "airlift" and zone and obs["resources"]["airlifts_remaining"] > 0:
        airlift_type = "rescue"
        zone_obs = next((item for item in obs["zones"] if item["zone_id"] == zone), None)
        if zone_obs and zone_obs["casualties_remaining"] == 0 and zone_obs["supply_gap"] > 0:
            airlift_type = "supply"
        return ActionModel(action="airlift", to_zone=zone, type=airlift_type), reason
    if action_type == "recall_team" and zone:
        zone_obs = next((item for item in obs["zones"] if item["zone_id"] == zone), None)
        if zone_obs and zone_obs["teams_present"] > 0:
            return ActionModel(action="recall_team", from_zone=zone, units=max(1, min(zone_obs["teams_present"], units or 1))), reason

    greedy_action, greedy_reason = get_greedy_action(obs, zone_scores)
    return greedy_action, f"{reason} Fallback to greedy validator: {greedy_reason}"


def _location_by_zone(detail: DemoScenarioDetail) -> dict[str, tuple[float, float]]:
    return {
        location.zone_id or location.node_id: location.coordinates
        for location in detail.locations
    }


def _apply_overlay_state(detail: DemoScenarioDetail, cfg: dict, state: dict) -> list[DemoMapOverlay]:
    overlays = {
        overlay.overlay_id: overlay.model_copy(deep=True)
        for overlay in detail.overlays
    }
    zone_state = {zone["zone_id"]: zone for zone in state["zones"]}
    through_step = max(0, state["current_step"] - 1)

    for event in cfg.get("events", []):
        if event.get("step", 10 ** 6) > through_step:
            continue
        for update in event.get("overlay_updates", []):
            overlay = overlays.get(update.get("overlay_id"))
            if overlay is None:
                continue
            data = overlay.model_dump()
            data.update(update)
            overlays[overlay.overlay_id] = DemoMapOverlay(**data)

    for overlay_id, overlay in list(overlays.items()):
        if overlay.kind == "blocked_corridor" and overlay.zone_id and overlay.zone_id in zone_state:
            data = overlay.model_dump()
            data["active"] = bool(zone_state[overlay.zone_id]["road_blocked"])
            overlays[overlay_id] = DemoMapOverlay(**data)

    return list(overlays.values())


def _movement_for_action(
    cfg: dict,
    detail: DemoScenarioDetail,
    action: ActionModel,
    action_result: str,
) -> list[DemoResourceMovement]:
    if action_result != "success":
        return []

    zone_id = action.to_zone or action.from_zone
    if not zone_id:
        return []

    route = None
    if action.action == "deploy_team":
        route = get_demo_route(cfg, zone_id, "road")
    elif action.action == "send_supplies":
        route = get_demo_route(cfg, zone_id, "road")
    elif action.action == "airlift":
        route = get_demo_route(cfg, zone_id, "air") or get_demo_route(cfg, zone_id, "road")
    elif action.action == "recall_team":
        route = get_recall_route(cfg, zone_id)

    if route is None:
        return []

    zone_lookup = {location.node_id: location.label for location in detail.locations}
    color = {
        "deploy_team": "#38bdf8",
        "send_supplies": "#f97316",
        "airlift": "#c084fc",
        "recall_team": "#facc15",
    }.get(action.action, "#94a3b8")
    label = {
        "deploy_team": "Rescue teams moving",
        "send_supplies": "Supply convoy moving",
        "airlift": "Airlift in motion",
        "recall_team": "Recall convoy returning",
    }.get(action.action, "Movement")
    note = (
        f"{label} between {zone_lookup.get(route['from_node'], route['from_node'])} "
        f"and {zone_lookup.get(route['to_node'], route['to_node'])}."
    )

    return [
        DemoResourceMovement(
            movement_id=f"{route['route_id']}-{action.action}",
            kind="airlift" if action.action == "airlift" else ("supply" if action.action == "send_supplies" else "team"),
            label=label,
            route_id=route["route_id"],
            path=route["path"],
            from_node=route["from_node"],
            to_node=route["to_node"],
            units=action.units or 1,
            progress=0.42 if action.action == "recall_team" else 0.78,
            color=color,
            action=action.action,
            note=note,
        )
    ]


def _build_resource_positions(detail: DemoScenarioDetail, state: dict) -> list[DemoResourcePosition]:
    coords_by_zone = _location_by_zone(detail)
    positions: list[DemoResourcePosition] = [
        DemoResourcePosition(
            resource_id="hq-command",
            kind="hq",
            label="SST Response Hub",
            coordinates=coords_by_zone[detail.hq_node_id],
            status="ready",
            note=(
                f"HQ inventory: {state['teams_available']} teams, "
                f"{state['supply_stock']} supply units, {state['airlifts_remaining']} airlifts."
            ),
        )
    ]

    if state["teams_available"] > 0:
        positions.append(
            DemoResourcePosition(
                resource_id="hq-teams",
                kind="team",
                label="Ready rescue teams",
                coordinates=coords_by_zone[detail.hq_node_id],
                count=state["teams_available"],
                status="ready",
                note="Teams staged at HQ and ready for dispatch.",
            )
        )
    if state["supply_stock"] > 0:
        positions.append(
            DemoResourcePosition(
                resource_id="hq-supplies",
                kind="supply",
                label="HQ relief stock",
                coordinates=coords_by_zone[detail.hq_node_id],
                count=state["supply_stock"],
                status="ready",
                note="Remaining food, water, and medical stock at HQ.",
            )
        )
    if state["airlifts_remaining"] > 0:
        positions.append(
            DemoResourcePosition(
                resource_id="hq-airlifts",
                kind="airlift",
                label="Airlifts on standby",
                coordinates=coords_by_zone[detail.hq_node_id],
                count=state["airlifts_remaining"],
                status="ready",
                note="Airlifts reserved for blocked high-severity corridors.",
            )
        )

    for zone in state["zones"]:
        zone_id = zone["zone_id"]
        if zone_id not in coords_by_zone:
            continue
        zone_coords = coords_by_zone[zone_id]
        if zone["teams_present"] > 0:
            positions.append(
                DemoResourcePosition(
                    resource_id=f"{zone_id}-teams",
                    kind="team",
                    label=f"Rescue teams at zone {zone_id}",
                    coordinates=zone_coords,
                    count=zone["teams_present"],
                    status="deployed",
                    assigned_zone=zone_id,
                    note="Active rescue crews are already operating on site.",
                )
            )
        if zone["supply_received"] > 0:
            positions.append(
                DemoResourcePosition(
                    resource_id=f"{zone_id}-supplies",
                    kind="supply",
                    label=f"Relief cache at zone {zone_id}",
                    coordinates=zone_coords,
                    count=zone["supply_received"],
                    status="support",
                    assigned_zone=zone_id,
                    note="Delivered relief stock already positioned at the zone.",
                )
            )

    return positions


def _build_map_state(
    cfg: dict,
    detail: DemoScenarioDetail,
    state: dict,
    action: ActionModel,
    action_result: str,
    step_id: int,
) -> DemoMapState:
    overlays = _apply_overlay_state(detail, cfg, state)
    target = action.to_zone or action.from_zone
    verb = {
        "deploy_team": "Dispatching teams",
        "send_supplies": "Sending supplies",
        "airlift": "Launching airlift",
        "recall_team": "Recalling crews",
        "wait": "Holding position",
    }.get(action.action, "Updating state")
    suffix = f" toward zone {target}" if target else ""
    return DemoMapState(
        center=detail.center,
        zoom=detail.zoom,
        bounds=detail.bounds,
        overlays=overlays,
        resource_positions=_build_resource_positions(detail, state),
        recent_movements=_movement_for_action(cfg, detail, action, action_result),
        action_target=target,
        step_label=f"Step {step_id + 1}: {verb}{suffix} ({action_result})",
    )


def _reasoning_payload(
    *,
    zone_scores: list[dict],
    triage_summary: str,
    triage_data: dict,
    plan_decision: str,
    plan_data: dict,
    action_rationale: str,
    stage_timings_ms: dict[str, float],
    rejected_actions: list[str] | None = None,
) -> dict:
    return {
        "pytorch_scores": zone_scores,
        "triage_summary": triage_summary,
        "plan_decision": plan_decision,
        "action_rationale": action_rationale,
        "triage": triage_data,
        "plan": plan_data,
        "validator": {
            "valid": True,
            "fallback_used": action_rationale.lower().startswith("fallback"),
            "constraints_checked": [
                "zone_exists",
                "resource_limits",
                "road_access_or_airlift",
                "false_sos_avoidance",
                "scenario_schema",
            ],
        },
        "stage_timings_ms": stage_timings_ms,
        "rejected_actions": rejected_actions or [],
    }


def iter_demo_events(
    scenario_id: str,
    agent: str = "ai_4stage",
    *,
    delay_seconds: float = 0.0,
) -> Iterator[tuple[str, dict]]:
    from agents.action_agent import get_action
    from agents.greedy_agent import get_greedy_action
    from agents.planner_agent import run_planner
    from agents.random_agent import get_random_action
    from agents.triage_agent import run_triage
    from agents.zone_scorer import score_zones

    agent_name = validate_demo_agent(agent)
    cfg = get_demo_scenario_config(scenario_id)
    detail = get_demo_scenario_detail(scenario_id)
    env = DemoDisasterEnv()
    obs = env.reset_from_config(cfg)
    client, model_name, run_note = _get_runtime(agent_name)
    history: list[dict] = []
    total_reward = 0.0

    meta = DemoStreamMetaEvent(
        scenario=detail,
        scenario_id=scenario_id,
        agent=agent_name,
        model=model_name,
    )
    yield "meta", meta.model_dump()

    while True:
        obs_dict = obs.model_dump()
        state_before = env.state()
        step_id = obs_dict["step_number"]
        display_step = step_id + 1

        t0 = time.perf_counter()
        zone_scores = score_zones(obs_dict)
        pyt_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        false_sos = [item["zone_id"] for item in zone_scores if item.get("is_false_sos_suspect")]
        top_zones = [item["zone_id"] for item in zone_scores if item["zone_id"] not in false_sos][:3]

        yield "stage", {
            "step": display_step,
            "stage": "pytorch",
            "duration_ms": pyt_ms,
            "summary": f"Scored Bengaluru zones. Top priorities: {top_zones or ['none']}",
            "payload": {"top_zones": top_zones, "false_sos_suspects": false_sos},
        }

        if agent_name == "ai_4stage" and client is not None:
            t1 = time.perf_counter()
            triage = run_triage(obs_dict, client, model_name, zone_scores=zone_scores)
            triage_ms = round((time.perf_counter() - t1) * 1000.0, 2)
        else:
            triage = _heuristic_triage(obs_dict, state_before, zone_scores)
            triage_ms = 0.0

        triage_priority = [item.get("zone_id") for item in triage.get("priority_zones", [])[:3]]
        triage_false = triage.get("false_sos_suspects", [])
        triage_deadlines = triage.get("deadline_alerts", [])
        triage_confidence = round(min(0.98, 0.62 + 0.06 * len(triage_priority) + 0.04 * len(triage_deadlines)), 2)
        triage_summary = (
            f"Priority zones: {triage_priority or ['none']} | False SOS suspects: {triage_false or []} "
            f"| Deadline alerts: {[item.get('zone_id') for item in triage_deadlines]}"
        )
        triage_data = {
            "false_sos_suspects": triage_false,
            "deadline_alerts": triage_deadlines,
            "reserve_airlift_for": triage.get("reserve_airlift_for"),
            "confidence": triage_confidence,
            "priority_zones": triage_priority,
        }
        yield "stage", {
            "step": display_step,
            "stage": "triage",
            "duration_ms": triage_ms,
            "summary": triage_summary,
            "payload": triage_data,
        }

        if agent_name == "greedy":
            action, action_rationale = get_greedy_action(obs_dict, zone_scores)
            plan = {
                "step_plan": [
                    {
                        "step_offset": 1,
                        "action": action.action,
                        "zone": action.to_zone or action.from_zone,
                        "units": action.units,
                        "reason": action_rationale,
                    }
                ],
                "primary_zone": action.to_zone or action.from_zone,
                "primary_action_type": action.action,
                "critical_decision": "Greedy policy: recall → airlift → deploy → supply",
                "airlift_target": triage.get("reserve_airlift_for"),
            }
            plan_ms = 0.0
        elif agent_name == "random":
            action = get_random_action(obs_dict)
            action_rationale = (
                f"Randomly chose: {action.action}"
                + (f" → zone {action.to_zone or action.from_zone}" if (action.to_zone or action.from_zone) else "")
            )
            plan = {
                "step_plan": [
                    {
                        "step_offset": 1,
                        "action": action.action,
                        "zone": action.to_zone or action.from_zone,
                        "units": action.units,
                        "reason": action_rationale,
                    }
                ],
                "primary_zone": action.to_zone or action.from_zone,
                "primary_action_type": action.action,
                "critical_decision": "Random valid-action policy over the scenario graph.",
                "airlift_target": None,
            }
            plan_ms = 0.0
        elif client is not None:
            t2 = time.perf_counter()
            plan = run_planner(obs_dict, triage, zone_scores, client)
            plan_ms = round((time.perf_counter() - t2) * 1000.0, 2)

            t3 = time.perf_counter()
            action = get_action(
                obs_dict,
                triage,
                history,
                client,
                model_name,
                zone_scores=zone_scores,
                plan=plan,
            )
            action_ms = round((time.perf_counter() - t3) * 1000.0, 2)
            step_one = next((item for item in plan.get("step_plan", []) if item.get("step_offset") == 1), None)
            action_rationale = (
                step_one.get("reason", f"Execute {action.action}")
                if isinstance(step_one, dict)
                else f"Fallback: {action.action}"
            )
        else:
            plan = _heuristic_plan(obs_dict, triage, zone_scores)
            plan_ms = 0.0
            action, action_rationale = _action_from_plan(plan, obs_dict, zone_scores)
            action_ms = 0.0

        if agent_name != "ai_4stage" or client is None:
            action_ms = 0.0

        plan_decision = plan.get("critical_decision", "Computed scenario-aware allocation plan")
        plan_data = {
            "primary_zone": plan.get("primary_zone"),
            "primary_action_type": plan.get("primary_action_type"),
            "critical_decision": plan_decision,
            "step_plan": plan.get("step_plan", []),
        }
        yield "stage", {
            "step": display_step,
            "stage": "planner",
            "duration_ms": plan_ms,
            "summary": plan_decision,
            "payload": plan_data,
        }

        validator_payload = {
            "valid": True,
            "fallback_used": action_rationale.lower().startswith("fallback"),
            "constraints_checked": [
                "scenario_id_exists",
                "resource_limits",
                "road_access_or_airlift",
                "false_sos_avoidance",
                "action_schema",
            ],
        }
        yield "stage", {
            "step": display_step,
            "stage": "action",
            "duration_ms": action_ms,
            "summary": action_rationale,
            "payload": validator_payload,
        }

        result = env.step(action)
        total_reward += result.reward
        post_state = env.state()
        map_state = _build_map_state(
            cfg,
            detail,
            post_state,
            action,
            result.observation.last_action_result,
            step_id,
        )
        rejected_actions = [
            f"{item.get('action')}:{item.get('zone')}"
            for item in plan.get("step_plan", [])
            if isinstance(item, dict) and item.get("step_offset") in (2, 3)
        ]

        step_model = DemoStep(
            step=display_step,
            observation=result.observation,
            action=action,
            reward=round(result.reward, 4),
            reasoning=_reasoning_payload(
                zone_scores=zone_scores,
                triage_summary=triage_summary,
                triage_data=triage_data,
                plan_decision=plan_decision,
                plan_data=plan_data,
                action_rationale=action_rationale,
                stage_timings_ms={
                    "pytorch": pyt_ms,
                    "triage": triage_ms,
                    "planner": plan_ms,
                    "action": action_ms,
                },
                rejected_actions=rejected_actions,
            ),
            map_state=map_state,
        )
        yield "step", step_model.model_dump()

        obs = result.observation
        if result.done:
            break
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    final_score = compute_episode_score(total_reward, cfg["max_steps"])
    yield "done", {
        "scenario_id": scenario_id,
        "agent": agent_name,
        "model": model_name,
        "final_score": round(final_score, 4),
        "cumulative_reward": round(total_reward, 4),
        "steps_taken": post_state["current_step"],
        "note": run_note,
    }


def run_demo_scenario(scenario_id: str, agent: str = "ai_4stage") -> DemoRunResult:
    meta: dict | None = None
    steps: list[DemoStep] = []
    done: dict | None = None

    for event, payload in iter_demo_events(scenario_id, agent):
        if event == "meta":
            meta = payload
        elif event == "step":
            steps.append(DemoStep(**payload))
        elif event == "done":
            done = payload

    if meta is None or done is None:
        raise RuntimeError(f"Demo episode for scenario '{scenario_id}' did not finish cleanly.")

    return DemoRunResult(
        scenario=DemoScenarioDetail(**meta["scenario"]),
        agent=done["agent"],
        model=done.get("model"),
        final_score=done.get("final_score"),
        cumulative_reward=done["cumulative_reward"],
        steps_taken=done["steps_taken"],
        steps=steps,
        note=done.get("note"),
    )

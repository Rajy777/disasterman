"""
demo_scenarios.py — Curated Bengaluru showcase scenarios for the live demo mode.

These scenarios are intentionally separate from ALL_TASKS so benchmark evaluation
remains stable while the reviewer-facing map demo can use richer geography and
map metadata.
"""

from __future__ import annotations

import copy
from typing import Any

from demo_models import DemoScenarioDetail, DemoScenarioSummary


HQ_COORDS = (12.8452, 77.6631)  # Electronic City Phase 1 / SST-adjacent hub
BENGALURU_BOUNDS = [(12.82, 77.49), (13.11, 77.77)]
ALLOWED_AGENTS = ["ai_4stage", "greedy", "random"]


def _air_path(start: tuple[float, float], end: tuple[float, float], bump: float = 0.018) -> list[tuple[float, float]]:
    mid_lat = (start[0] + end[0]) / 2 + bump
    mid_lng = (start[1] + end[1]) / 2
    return [start, (mid_lat, mid_lng), end]


def _reverse_path(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return list(reversed(path))


DEMO_SCENARIOS: dict[str, dict[str, Any]] = {
    "bellandur_flood_response": {
        "scenario_id": "bellandur_flood_response",
        "title": "Bellandur Flood Response",
        "disaster_type": "Urban Flooding",
        "narrative": (
            "Cloudburst flooding around Bellandur and HSR cuts key corridors. "
            "Teams must balance water rescues, shelter supply runs, and a noisy false alert."
        ),
        "duration_steps": 9,
        "default_agent": "ai_4stage",
        "tags": ["Bengaluru", "flood", "false alert", "blocked roads"],
        "center": (12.923, 77.663),
        "zoom": 11.5,
        "bounds": BENGALURU_BOUNDS,
        "hq_node_id": "HQ",
        "allowed_agents": ALLOWED_AGENTS,
        "locations": [
            {
                "node_id": "HQ",
                "label": "SST Response Hub",
                "area": "Electronic City Phase 1",
                "coordinates": HQ_COORDS,
                "kind": "hq",
                "description": "Shared Bengaluru operations hub near Scaler School of Technology.",
            },
            {
                "node_id": "A",
                "zone_id": "A",
                "label": "Bellandur Breach",
                "area": "Bellandur Lake / ORR",
                "coordinates": (12.9279, 77.6729),
                "kind": "incident",
                "description": "Waterlogging and trapped residents near the lake edge.",
            },
            {
                "node_id": "B",
                "zone_id": "B",
                "label": "HSR Shelter Cluster",
                "area": "HSR Layout Sector 1",
                "coordinates": (12.9116, 77.6470),
                "kind": "support",
                "description": "Emergency shelter and food distribution point.",
            },
            {
                "node_id": "C",
                "zone_id": "C",
                "label": "Sarjapur Underpass",
                "area": "Sarjapur Road Junction",
                "coordinates": (12.9074, 77.6840),
                "kind": "incident",
                "description": "Vehicles stranded under an inundated underpass.",
            },
            {
                "node_id": "D",
                "zone_id": "D",
                "label": "Koramangala Clinic",
                "area": "Koramangala 4th Block",
                "coordinates": (12.9352, 77.6245),
                "kind": "medical",
                "description": "Clinic stabilizing evacuees and requesting supplies.",
            },
            {
                "node_id": "E",
                "zone_id": "E",
                "label": "Domlur Viral Alert",
                "area": "Domlur Flyover",
                "coordinates": (12.9629, 77.6387),
                "kind": "false_alert",
                "description": "A viral SOS cluster that looks urgent but carries no real casualties.",
            },
        ],
        "routes": [
            {"route_id": "HQ_A_road", "label": "EC to Bellandur", "mode": "road", "from_node": "HQ", "to_node": "A", "zone_id": "A",
             "path": [HQ_COORDS, (12.875, 77.654), (12.903, 77.665), (12.9279, 77.6729)]},
            {"route_id": "HQ_A_air", "label": "Airlift to Bellandur", "mode": "air", "from_node": "HQ", "to_node": "A", "zone_id": "A",
             "path": _air_path(HQ_COORDS, (12.9279, 77.6729))},
            {"route_id": "HQ_B_road", "label": "EC to HSR", "mode": "road", "from_node": "HQ", "to_node": "B", "zone_id": "B",
             "path": [HQ_COORDS, (12.871, 77.655), (12.893, 77.648), (12.9116, 77.6470)]},
            {"route_id": "HQ_B_air", "label": "Airlift to HSR", "mode": "air", "from_node": "HQ", "to_node": "B", "zone_id": "B",
             "path": _air_path(HQ_COORDS, (12.9116, 77.6470), bump=0.016)},
            {"route_id": "HQ_C_road", "label": "EC to Sarjapur", "mode": "road", "from_node": "HQ", "to_node": "C", "zone_id": "C",
             "path": [HQ_COORDS, (12.873, 77.667), (12.894, 77.678), (12.9074, 77.6840)]},
            {"route_id": "HQ_C_air", "label": "Airlift to Sarjapur", "mode": "air", "from_node": "HQ", "to_node": "C", "zone_id": "C",
             "path": _air_path(HQ_COORDS, (12.9074, 77.6840), bump=0.02)},
            {"route_id": "HQ_D_road", "label": "EC to Koramangala", "mode": "road", "from_node": "HQ", "to_node": "D", "zone_id": "D",
             "path": [HQ_COORDS, (12.872, 77.653), (12.905, 77.637), (12.9352, 77.6245)]},
            {"route_id": "HQ_E_road", "label": "EC to Domlur", "mode": "road", "from_node": "HQ", "to_node": "E", "zone_id": "E",
             "path": [HQ_COORDS, (12.878, 77.654), (12.919, 77.644), (12.9629, 77.6387)]},
        ],
        "overlays": [
            {
                "overlay_id": "bellandur_flood_zone",
                "label": "Bellandur floodwater spread",
                "kind": "flood_zone",
                "geometry": "polygon",
                "coordinates": [(12.921, 77.662), (12.935, 77.664), (12.938, 77.679), (12.924, 77.684), (12.916, 77.676)],
                "severity": "high",
                "active": True,
                "note": "Lake outflow has flooded nearby service roads.",
                "zone_id": "A",
            },
            {
                "overlay_id": "sarjapur_blocked_corridor",
                "label": "Sarjapur underpass blocked",
                "kind": "blocked_corridor",
                "geometry": "polyline",
                "coordinates": [(12.891, 77.675), (12.899, 77.680), (12.9074, 77.6840)],
                "severity": "high",
                "active": True,
                "note": "Ground vehicles are diverted until pumps clear the underpass.",
                "zone_id": "C",
            },
            {
                "overlay_id": "domlur_false_alert",
                "label": "Unverified SOS cluster",
                "kind": "false_alert",
                "geometry": "circle",
                "coordinates": [(12.9629, 77.6387)],
                "radius_m": 520,
                "severity": "medium",
                "active": True,
                "note": "Reviewer-visible false alert to explain the anti-noise logic.",
                "zone_id": "E",
            },
            {
                "overlay_id": "hsr_support_zone",
                "label": "HSR community shelter",
                "kind": "support_zone",
                "geometry": "circle",
                "coordinates": [(12.9116, 77.6470)],
                "radius_m": 450,
                "severity": "low",
                "active": True,
                "note": "Shelter, kitchen, and volunteer coordination point.",
                "zone_id": "B",
            },
        ],
        "max_steps": 9,
        "rescue_rate_per_team": 5,
        "weather_schedule": {1: "storm", 2: "flood", 3: "flood", 4: "storm", 5: "clear", 6: "clear", 7: "clear", 8: "clear"},
        "storm_blocks": ["A", "C"],
        "zones": [
            {"zone_id": "A", "casualties_total": 48, "casualties_critical": 12, "critical_deadline": 4, "supply_needed": 90, "road_blocked": True, "severity_init": 0.88, "is_false_sos": False},
            {"zone_id": "B", "casualties_total": 18, "casualties_critical": 4, "critical_deadline": 6, "supply_needed": 60, "road_blocked": False, "severity_init": 0.68, "is_false_sos": False},
            {"zone_id": "C", "casualties_total": 26, "casualties_critical": 6, "critical_deadline": 5, "supply_needed": 70, "road_blocked": True, "severity_init": 0.82, "is_false_sos": False},
            {"zone_id": "D", "casualties_total": 12, "casualties_critical": 2, "critical_deadline": 7, "supply_needed": 40, "road_blocked": False, "severity_init": 0.55, "is_false_sos": False},
            {"zone_id": "E", "casualties_total": 0, "casualties_critical": 0, "critical_deadline": 99, "supply_needed": 0, "road_blocked": False, "severity_init": 0.73, "is_false_sos": True},
        ],
        "resources": {"rescue_teams": 7, "supply_stock": 170, "airlifts": 2},
        "false_sos_zones": ["E"],
        "events": [
            {"step": 4, "type": "pump_failure", "zone": "B", "casualties": 18, "critical": 5, "supply_needed": 30, "severity_boost": 0.25,
             "overlay_updates": [{"overlay_id": "hsr_support_zone", "active": True}]},
            {"step": 5, "type": "road_clear", "zone": "C", "road_blocked": False,
             "overlay_updates": [{"overlay_id": "sarjapur_blocked_corridor", "active": False}]},
        ],
    },
    "peenya_industrial_fire": {
        "scenario_id": "peenya_industrial_fire",
        "title": "Peenya Industrial Fire",
        "disaster_type": "Industrial Fire",
        "narrative": (
            "An industrial fire in Peenya spreads smoke across worker housing and logistics depots. "
            "The demo shows hazardous corridors, supply prioritization, and a misleading social-media SOS."
        ),
        "duration_steps": 9,
        "default_agent": "ai_4stage",
        "tags": ["Bengaluru", "fire", "industrial", "multi-zone response"],
        "center": (13.013, 77.548),
        "zoom": 11.3,
        "bounds": BENGALURU_BOUNDS,
        "hq_node_id": "HQ",
        "allowed_agents": ALLOWED_AGENTS,
        "locations": [
            {
                "node_id": "HQ",
                "label": "SST Response Hub",
                "area": "Electronic City Phase 1",
                "coordinates": HQ_COORDS,
                "kind": "hq",
                "description": "Shared Bengaluru operations hub near Scaler School of Technology.",
            },
            {
                "node_id": "A",
                "zone_id": "A",
                "label": "Peenya Plant Blaze",
                "area": "Peenya 2nd Stage",
                "coordinates": (13.0328, 77.5131),
                "kind": "incident",
                "description": "Main fire site with trapped workers and heat exposure risk.",
            },
            {
                "node_id": "B",
                "zone_id": "B",
                "label": "Yeshwanthpur Depot",
                "area": "Yeshwanthpur Goods Yard",
                "coordinates": (13.0280, 77.5545),
                "kind": "support",
                "description": "Logistics depot supporting hydration and foam units.",
            },
            {
                "node_id": "C",
                "zone_id": "C",
                "label": "Nagasandra Housing",
                "area": "Nagasandra Worker Block",
                "coordinates": (13.0487, 77.5006),
                "kind": "incident",
                "description": "Dense worker housing threatened by smoke and panic.",
            },
            {
                "node_id": "D",
                "zone_id": "D",
                "label": "Malleshwaram Med Bay",
                "area": "Malleswaram 8th Cross",
                "coordinates": (13.0032, 77.5713),
                "kind": "medical",
                "description": "Triage tents for smoke inhalation and burns.",
            },
            {
                "node_id": "E",
                "zone_id": "E",
                "label": "Rajajinagar Social SOS",
                "area": "Rajajinagar Metro Edge",
                "coordinates": (12.9916, 77.5556),
                "kind": "false_alert",
                "description": "A dramatic but inaccurate viral SOS post pulling attention away from the fire zone.",
            },
        ],
        "routes": [
            {"route_id": "HQ_A_road", "label": "EC to Peenya", "mode": "road", "from_node": "HQ", "to_node": "A", "zone_id": "A",
             "path": [HQ_COORDS, (12.908, 77.623), (12.979, 77.563), (13.0328, 77.5131)]},
            {"route_id": "HQ_A_air", "label": "Airlift to Peenya", "mode": "air", "from_node": "HQ", "to_node": "A", "zone_id": "A",
             "path": _air_path(HQ_COORDS, (13.0328, 77.5131), bump=0.024)},
            {"route_id": "HQ_B_road", "label": "EC to Yeshwanthpur", "mode": "road", "from_node": "HQ", "to_node": "B", "zone_id": "B",
             "path": [HQ_COORDS, (12.905, 77.627), (12.973, 77.582), (13.0280, 77.5545)]},
            {"route_id": "HQ_C_road", "label": "EC to Nagasandra", "mode": "road", "from_node": "HQ", "to_node": "C", "zone_id": "C",
             "path": [HQ_COORDS, (12.911, 77.620), (12.987, 77.560), (13.0487, 77.5006)]},
            {"route_id": "HQ_C_air", "label": "Airlift to Nagasandra", "mode": "air", "from_node": "HQ", "to_node": "C", "zone_id": "C",
             "path": _air_path(HQ_COORDS, (13.0487, 77.5006), bump=0.026)},
            {"route_id": "HQ_D_road", "label": "EC to Malleswaram", "mode": "road", "from_node": "HQ", "to_node": "D", "zone_id": "D",
             "path": [HQ_COORDS, (12.906, 77.629), (12.966, 77.589), (13.0032, 77.5713)]},
            {"route_id": "HQ_E_road", "label": "EC to Rajajinagar", "mode": "road", "from_node": "HQ", "to_node": "E", "zone_id": "E",
             "path": [HQ_COORDS, (12.902, 77.622), (12.958, 77.579), (12.9916, 77.5556)]},
        ],
        "overlays": [
            {
                "overlay_id": "peenya_fire_core",
                "label": "Peenya heat plume",
                "kind": "fire_zone",
                "geometry": "circle",
                "coordinates": [(13.0328, 77.5131)],
                "radius_m": 900,
                "severity": "high",
                "active": True,
                "note": "High heat and toxic smoke are pushing crews back.",
                "zone_id": "A",
            },
            {
                "overlay_id": "nagasandra_smoke_corridor",
                "label": "Smoke-choked corridor",
                "kind": "blocked_corridor",
                "geometry": "polyline",
                "coordinates": [(13.034, 77.506), (13.041, 77.503), (13.0487, 77.5006)],
                "severity": "high",
                "active": True,
                "note": "Ground vehicles slow down while smoke blankets worker housing.",
                "zone_id": "C",
            },
            {
                "overlay_id": "rajinagar_false_alert",
                "label": "Viral SOS hotspot",
                "kind": "false_alert",
                "geometry": "circle",
                "coordinates": [(12.9916, 77.5556)],
                "radius_m": 500,
                "severity": "medium",
                "active": True,
                "note": "Looks dramatic online, but the casualty count is actually zero.",
                "zone_id": "E",
            },
        ],
        "max_steps": 9,
        "rescue_rate_per_team": 4,
        "weather_schedule": {1: "clear", 2: "clear", 3: "storm", 4: "storm", 5: "clear", 6: "clear", 7: "clear", 8: "clear"},
        "storm_blocks": ["C"],
        "zones": [
            {"zone_id": "A", "casualties_total": 34, "casualties_critical": 11, "critical_deadline": 4, "supply_needed": 50, "road_blocked": False, "severity_init": 0.90, "is_false_sos": False},
            {"zone_id": "B", "casualties_total": 20, "casualties_critical": 5, "critical_deadline": 6, "supply_needed": 80, "road_blocked": False, "severity_init": 0.72, "is_false_sos": False},
            {"zone_id": "C", "casualties_total": 28, "casualties_critical": 6, "critical_deadline": 5, "supply_needed": 60, "road_blocked": True, "severity_init": 0.78, "is_false_sos": False},
            {"zone_id": "D", "casualties_total": 14, "casualties_critical": 3, "critical_deadline": 7, "supply_needed": 45, "road_blocked": False, "severity_init": 0.56, "is_false_sos": False},
            {"zone_id": "E", "casualties_total": 0, "casualties_critical": 0, "critical_deadline": 99, "supply_needed": 0, "road_blocked": False, "severity_init": 0.71, "is_false_sos": True},
        ],
        "resources": {"rescue_teams": 6, "supply_stock": 150, "airlifts": 1},
        "false_sos_zones": ["E"],
        "events": [
            {"step": 3, "type": "secondary_explosion", "zone": "A", "casualties": 18, "critical": 6, "supply_needed": 25, "severity_boost": 0.12,
             "overlay_updates": [{"overlay_id": "peenya_fire_core", "active": True}]},
            {"step": 5, "type": "smoke_clearance", "zone": "C", "road_blocked": False,
             "overlay_updates": [{"overlay_id": "nagasandra_smoke_corridor", "active": False}]},
        ],
    },
    "whitefield_building_collapse": {
        "scenario_id": "whitefield_building_collapse",
        "title": "Whitefield Building Collapse",
        "disaster_type": "Structural Collapse",
        "narrative": (
            "A partial high-rise collapse in Whitefield jams access corridors and creates a rolling casualty spike. "
            "The agent must re-balance rescue lifts, triage sites, and support caches while avoiding rumor-driven noise."
        ),
        "duration_steps": 10,
        "default_agent": "ai_4stage",
        "tags": ["Bengaluru", "collapse", "aftershock", "urban mobility"],
        "center": (12.978, 77.714),
        "zoom": 11.4,
        "bounds": BENGALURU_BOUNDS,
        "hq_node_id": "HQ",
        "allowed_agents": ALLOWED_AGENTS,
        "locations": [
            {
                "node_id": "HQ",
                "label": "SST Response Hub",
                "area": "Electronic City Phase 1",
                "coordinates": HQ_COORDS,
                "kind": "hq",
                "description": "Shared Bengaluru operations hub near Scaler School of Technology.",
            },
            {
                "node_id": "A",
                "zone_id": "A",
                "label": "Whitefield Tower Site",
                "area": "ITPL / Whitefield",
                "coordinates": (12.9698, 77.7499),
                "kind": "incident",
                "description": "Primary collapse site with trapped workers and debris blocking approach roads.",
            },
            {
                "node_id": "B",
                "zone_id": "B",
                "label": "Hoodi Relief Camp",
                "area": "Hoodi Main Road",
                "coordinates": (12.9914, 77.7159),
                "kind": "support",
                "description": "Temporary shelter and water distribution setup.",
            },
            {
                "node_id": "C",
                "zone_id": "C",
                "label": "KR Puram Choke Point",
                "area": "KR Puram Junction",
                "coordinates": (12.9985, 77.6953),
                "kind": "incident",
                "description": "Traffic lockup around incoming heavy rescue equipment.",
            },
            {
                "node_id": "D",
                "zone_id": "D",
                "label": "Marathahalli Med Bay",
                "area": "Marathahalli Bridge",
                "coordinates": (12.9565, 77.7016),
                "kind": "medical",
                "description": "Medical relay stabilizing casualties before hospital transfer.",
            },
            {
                "node_id": "E",
                "zone_id": "E",
                "label": "Indiranagar Rumor Feed",
                "area": "100 Feet Road",
                "coordinates": (12.9784, 77.6408),
                "kind": "false_alert",
                "description": "A rumor-driven SOS thread that should be filtered out.",
            },
        ],
        "routes": [
            {"route_id": "HQ_A_road", "label": "EC to Whitefield", "mode": "road", "from_node": "HQ", "to_node": "A", "zone_id": "A",
             "path": [HQ_COORDS, (12.897, 77.676), (12.934, 77.703), (12.9698, 77.7499)]},
            {"route_id": "HQ_A_air", "label": "Airlift to Whitefield", "mode": "air", "from_node": "HQ", "to_node": "A", "zone_id": "A",
             "path": _air_path(HQ_COORDS, (12.9698, 77.7499), bump=0.02)},
            {"route_id": "HQ_B_road", "label": "EC to Hoodi", "mode": "road", "from_node": "HQ", "to_node": "B", "zone_id": "B",
             "path": [HQ_COORDS, (12.892, 77.676), (12.944, 77.699), (12.9914, 77.7159)]},
            {"route_id": "HQ_C_road", "label": "EC to KR Puram", "mode": "road", "from_node": "HQ", "to_node": "C", "zone_id": "C",
             "path": [HQ_COORDS, (12.893, 77.674), (12.950, 77.690), (12.9985, 77.6953)]},
            {"route_id": "HQ_C_air", "label": "Airlift to KR Puram", "mode": "air", "from_node": "HQ", "to_node": "C", "zone_id": "C",
             "path": _air_path(HQ_COORDS, (12.9985, 77.6953), bump=0.016)},
            {"route_id": "HQ_D_road", "label": "EC to Marathahalli", "mode": "road", "from_node": "HQ", "to_node": "D", "zone_id": "D",
             "path": [HQ_COORDS, (12.887, 77.672), (12.925, 77.692), (12.9565, 77.7016)]},
            {"route_id": "HQ_E_road", "label": "EC to Indiranagar", "mode": "road", "from_node": "HQ", "to_node": "E", "zone_id": "E",
             "path": [HQ_COORDS, (12.894, 77.671), (12.938, 77.660), (12.9784, 77.6408)]},
        ],
        "overlays": [
            {
                "overlay_id": "whitefield_collapse_core",
                "label": "Collapse exclusion zone",
                "kind": "collapse_zone",
                "geometry": "polygon",
                "coordinates": [(12.964, 77.742), (12.975, 77.744), (12.978, 77.754), (12.968, 77.758), (12.961, 77.751)],
                "severity": "high",
                "active": True,
                "note": "Heavy debris blocks direct access into the collapse footprint.",
                "zone_id": "A",
            },
            {
                "overlay_id": "krpuram_blocked_corridor",
                "label": "KR Puram gridlock",
                "kind": "blocked_corridor",
                "geometry": "polyline",
                "coordinates": [(12.972, 77.697), (12.986, 77.697), (12.9985, 77.6953)],
                "severity": "medium",
                "active": True,
                "note": "Heavy equipment has saturated the junction approach.",
                "zone_id": "C",
            },
            {
                "overlay_id": "indiranagar_false_alert",
                "label": "Rumor-driven SOS feed",
                "kind": "false_alert",
                "geometry": "circle",
                "coordinates": [(12.9784, 77.6408)],
                "radius_m": 520,
                "severity": "medium",
                "active": True,
                "note": "A loud but misleading signal that the pipeline should deprioritize.",
                "zone_id": "E",
            },
        ],
        "max_steps": 10,
        "rescue_rate_per_team": 4,
        "weather_schedule": {1: "clear", 2: "clear", 3: "storm", 4: "storm", 5: "clear", 6: "clear", 7: "clear", 8: "clear", 9: "clear"},
        "storm_blocks": ["A", "C"],
        "zones": [
            {"zone_id": "A", "casualties_total": 42, "casualties_critical": 14, "critical_deadline": 4, "supply_needed": 70, "road_blocked": True, "severity_init": 0.91, "is_false_sos": False},
            {"zone_id": "B", "casualties_total": 15, "casualties_critical": 3, "critical_deadline": 6, "supply_needed": 55, "road_blocked": False, "severity_init": 0.63, "is_false_sos": False},
            {"zone_id": "C", "casualties_total": 24, "casualties_critical": 5, "critical_deadline": 5, "supply_needed": 40, "road_blocked": True, "severity_init": 0.76, "is_false_sos": False},
            {"zone_id": "D", "casualties_total": 18, "casualties_critical": 4, "critical_deadline": 7, "supply_needed": 45, "road_blocked": False, "severity_init": 0.59, "is_false_sos": False},
            {"zone_id": "E", "casualties_total": 0, "casualties_critical": 0, "critical_deadline": 99, "supply_needed": 0, "road_blocked": False, "severity_init": 0.69, "is_false_sos": True},
        ],
        "resources": {"rescue_teams": 8, "supply_stock": 180, "airlifts": 2},
        "false_sos_zones": ["E"],
        "events": [
            {"step": 2, "type": "aftershock", "zone": "C", "casualties": 20, "critical": 5, "supply_needed": 20, "severity_boost": 0.18},
            {"step": 5, "type": "debris_clearance", "zone": "A", "road_blocked": False,
             "overlay_updates": [{"overlay_id": "whitefield_collapse_core", "active": True}]},
            {"step": 6, "type": "kr_puram_release", "zone": "C", "road_blocked": False,
             "overlay_updates": [{"overlay_id": "krpuram_blocked_corridor", "active": False}]},
        ],
    },
}


def _detail_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": cfg["scenario_id"],
        "title": cfg["title"],
        "disaster_type": cfg["disaster_type"],
        "narrative": cfg["narrative"],
        "duration_steps": cfg["duration_steps"],
        "default_agent": cfg["default_agent"],
        "tags": cfg["tags"],
        "center": cfg["center"],
        "zoom": cfg["zoom"],
        "bounds": cfg["bounds"],
        "hq_node_id": cfg["hq_node_id"],
        "allowed_agents": cfg["allowed_agents"],
        "locations": cfg["locations"],
        "routes": cfg["routes"],
        "overlays": cfg["overlays"],
    }


def list_demo_scenario_summaries() -> list[DemoScenarioSummary]:
    return [
        DemoScenarioSummary(
            scenario_id=cfg["scenario_id"],
            title=cfg["title"],
            disaster_type=cfg["disaster_type"],
            narrative=cfg["narrative"],
            duration_steps=cfg["duration_steps"],
            default_agent=cfg["default_agent"],
            tags=cfg["tags"],
            center=cfg["center"],
            zoom=cfg["zoom"],
        )
        for cfg in DEMO_SCENARIOS.values()
    ]


def get_demo_scenario_detail(scenario_id: str) -> DemoScenarioDetail:
    cfg = DEMO_SCENARIOS.get(scenario_id)
    if cfg is None:
        raise KeyError(f"Unknown demo scenario: {scenario_id}")
    return DemoScenarioDetail(**_detail_payload(cfg))


def get_demo_scenario_config(scenario_id: str) -> dict[str, Any]:
    cfg = DEMO_SCENARIOS.get(scenario_id)
    if cfg is None:
        raise KeyError(f"Unknown demo scenario: {scenario_id}")
    return copy.deepcopy(cfg)


def get_demo_route(cfg: dict[str, Any], zone_id: str, mode: str) -> dict[str, Any] | None:
    for route in cfg["routes"]:
        if route.get("zone_id") == zone_id and route["mode"] == mode:
            return route
    return None


def get_recall_route(cfg: dict[str, Any], zone_id: str) -> dict[str, Any] | None:
    road = get_demo_route(cfg, zone_id, "road")
    if road is None:
        return None
    reversed_route = dict(road)
    reversed_route["route_id"] = f"{road['route_id']}_recall"
    reversed_route["label"] = f"Recall from {zone_id} to HQ"
    reversed_route["from_node"] = road["to_node"]
    reversed_route["to_node"] = road["from_node"]
    reversed_route["path"] = _reverse_path(road["path"])
    return reversed_route

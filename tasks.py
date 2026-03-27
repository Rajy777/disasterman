"""
tasks.py — Task configuration dicts for the Disaster Relief environment.
Owner: Tushar Sharma
Each config is passed directly to DisasterEnv.reset(task_config).
Numbers are locked from the Day 1 design doc.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Task 1 — Single zone flood. Easy. GPT-4 target: 0.70–0.85
# ---------------------------------------------------------------------------

TASK_1 = {
    "task_id": "task_1",
    "name": "Single zone flood response",
    "difficulty": "easy",
    "max_steps": 10,
    "rescue_rate_per_team": 4,       # casualties rescued per team per step
    "supply_rate_per_truck": 20,     # supply units delivered per truck per step
    "weather_schedule": {},          # {step: "storm"|"flood"|"clear"}
    "dam_break": None,               # None or {"step": int, "zone": str, "casualties": int}
    "zones": [
        {
            "zone_id": "A",
            "casualties_total": 30,
            "casualties_critical": 5,
            "critical_deadline": 4,  # expire at step 4 if unattended
            "supply_needed": 80,
            "road_blocked": False,
            "severity_init": 0.75,
            "is_false_sos": False,
        }
    ],
    "resources": {
        "rescue_teams": 8,
        "supply_stock": 200,
        "airlifts": 0,
    },
    "false_sos_zones": [],
}

# ---------------------------------------------------------------------------
# Task 2 — Multi-zone earthquake. Medium. GPT-4 target: 0.40–0.60
# ---------------------------------------------------------------------------

TASK_2 = {
    "task_id": "task_2",
    "name": "Multi-zone earthquake response",
    "difficulty": "medium",
    "max_steps": 15,
    "rescue_rate_per_team": 4,
    "supply_rate_per_truck": 20,
    "weather_schedule": {
        8: "storm",   # storm hits at step 8
        9: "storm",
        10: "storm",
        11: "clear",  # clears at step 11
    },
    "dam_break": None,
    "zones": [
        {
            "zone_id": "A",
            "casualties_total": 20,
            "casualties_critical": 4,
            "critical_deadline": 5,
            "supply_needed": 60,
            "road_blocked": False,
            "severity_init": 0.65,
            "is_false_sos": False,
        },
        {
            "zone_id": "B",
            "casualties_total": 35,
            "casualties_critical": 8,
            "critical_deadline": 6,
            "supply_needed": 100,
            "road_blocked": True,    # blocked at start
            "severity_init": 0.90,
            "is_false_sos": False,
        },
        {
            "zone_id": "C",
            "casualties_total": 25,
            "casualties_critical": 5,
            "critical_deadline": 7,
            "supply_needed": 70,
            "road_blocked": True,    # blocked at start, clears step 5
            "severity_init": 0.80,
            "is_false_sos": False,
            "unblock_at_step": 5,
        },
        {
            "zone_id": "D",
            "casualties_total": 15,
            "casualties_critical": 3,
            "critical_deadline": 8,
            "supply_needed": 40,
            "road_blocked": False,
            "severity_init": 0.50,
            "is_false_sos": False,
        },
        {
            "zone_id": "E",
            "casualties_total": 25,
            "casualties_critical": 5,
            "critical_deadline": 9,
            "supply_needed": 60,
            "road_blocked": False,
            "severity_init": 0.60,
            "is_false_sos": False,
        },
    ],
    "resources": {
        "rescue_teams": 6,
        "supply_stock": 150,
        "airlifts": 1,
    },
    "false_sos_zones": [],
    # Storm at step 8 dynamically blocks zone D for steps 8–10
    "storm_blocks": ["D"],
}

# ---------------------------------------------------------------------------
# Task 3 — Cyclone with cascading failures. Hard. GPT-4 target: 0.20–0.40
# ---------------------------------------------------------------------------

TASK_3 = {
    "task_id": "task_3",
    "name": "Cyclone — cascading failures and false SOS signals",
    "difficulty": "hard",
    "max_steps": 20,
    "rescue_rate_per_team": 4,
    "supply_rate_per_truck": 20,
    "weather_schedule": {
        3: "storm",
        4: "storm",
        5: "flood",
        6: "flood",
        7: "flood",
        8: "storm",
        9: "clear",
    },
    "dam_break": {
        "step": 7,
        "zone": "E",        # adds 60 casualties to zone E mid-episode
        "casualties": 60,
        "critical": 20,
        "supply_needed": 100,
    },
    "zones": [
        {"zone_id": "A", "casualties_total": 50, "casualties_critical": 10, "critical_deadline": 5,  "supply_needed": 120, "road_blocked": False, "severity_init": 0.80, "is_false_sos": False},
        {"zone_id": "B", "casualties_total": 40, "casualties_critical": 8,  "critical_deadline": 6,  "supply_needed": 100, "road_blocked": True,  "severity_init": 0.85, "is_false_sos": False},
        {"zone_id": "C", "casualties_total": 60, "casualties_critical": 12, "critical_deadline": 7,  "supply_needed": 140, "road_blocked": True,  "severity_init": 0.90, "is_false_sos": False},
        {"zone_id": "D", "casualties_total": 30, "casualties_critical": 6,  "critical_deadline": 8,  "supply_needed": 80,  "road_blocked": False, "severity_init": 0.70, "is_false_sos": False},
        {"zone_id": "E", "casualties_total": 40, "casualties_critical": 8,  "critical_deadline": 10, "supply_needed": 100, "road_blocked": True,  "severity_init": 0.75, "is_false_sos": False},
        {"zone_id": "F", "casualties_total": 35, "casualties_critical": 7,  "critical_deadline": 9,  "supply_needed": 90,  "road_blocked": False, "severity_init": 0.65, "is_false_sos": False},
        {"zone_id": "G", "casualties_total": 45, "casualties_critical": 9,  "critical_deadline": 11, "supply_needed": 110, "road_blocked": True,  "severity_init": 0.85, "is_false_sos": False},
        # False SOS zones — no real casualties, waste agent resources
        {"zone_id": "H", "casualties_total": 0,  "casualties_critical": 0,  "critical_deadline": 99, "supply_needed": 0,   "road_blocked": False, "severity_init": 0.0,  "is_false_sos": True},
        {"zone_id": "I", "casualties_total": 0,  "casualties_critical": 0,  "critical_deadline": 99, "supply_needed": 0,   "road_blocked": False, "severity_init": 0.0,  "is_false_sos": True},
        {"zone_id": "J", "casualties_total": 0,  "casualties_critical": 0,  "critical_deadline": 99, "supply_needed": 0,   "road_blocked": False, "severity_init": 0.0,  "is_false_sos": True},
    ],
    "resources": {
        "rescue_teams": 8,
        "supply_stock": 200,
        "airlifts": 2,
    },
    "false_sos_zones": ["H", "I", "J"],
    "storm_blocks": ["D", "F"],
}

# ---------------------------------------------------------------------------
# Registry — used by FastAPI /tasks endpoint
# ---------------------------------------------------------------------------

ALL_TASKS = {
    "task_1": TASK_1,
    "task_2": TASK_2,
    "task_3": TASK_3,
}
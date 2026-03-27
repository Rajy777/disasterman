"""
main.py — FastAPI server for Disaster Relief Coordination Env (DRC-Env).
OpenEnv-compliant REST API exposing reset(), step(), state(), and grader endpoints.
Owner: Raj Yadav
Deploy target: Hugging Face Spaces (port 7860)

Endpoints:
  GET  /health                  — Liveness check
  GET  /tasks                   — List all 3 task configs + action schema
  POST /reset                   — Start new episode, returns session_id + observation
  POST /step                    — Submit one action, returns StepResult
  GET  /state/{session_id}      — Full internal state (hidden fields exposed for graders)
  POST /grader                  — Score a completed episode trajectory
  POST /baseline                — Run baseline agent on all 3 tasks (requires GROQ_API_KEY)
  POST /humanizer               — Convert raw observation JSON into plain-English situation report
"""
from __future__ import annotations
import os
import uuid
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from environment import DisasterEnv
from models import ActionModel, ObservationModel, StepResult
from graders import grade_episode
from tasks import ALL_TASKS

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Disaster Relief Coordination Env (DRC-Env)",
    description=(
        "OpenEnv-compliant AI agent training environment. "
        "Simulates multi-zone disaster response under cascading failures, false SOS signals, "
        "and weather events. Agent pipeline: PyTorch ZoneScorer → Triage → Planner → Action."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Session store — one DisasterEnv per session_id
# ---------------------------------------------------------------------------

_sessions: dict[str, DisasterEnv] = {}
_sessions_lock = threading.Lock()
MAX_SESSIONS = 100  # evict oldest when exceeded


def _get_session(session_id: str) -> DisasterEnv:
    with _sessions_lock:
        env = _sessions.get(session_id)
    if env is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found. Call /reset first.")
    return env


def _create_session() -> tuple[str, DisasterEnv]:
    session_id = str(uuid.uuid4())[:8]
    env = DisasterEnv()
    with _sessions_lock:
        if len(_sessions) >= MAX_SESSIONS:
            # Evict oldest session
            oldest = next(iter(_sessions))
            del _sessions[oldest]
        _sessions[session_id] = env
    return session_id, env


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    task_id: str = "task_1"

class ResetResponse(BaseModel):
    session_id: str
    observation: ObservationModel

class StepRequest(BaseModel):
    session_id: str
    action: ActionModel

class GraderRequest(BaseModel):
    event_log: list[dict]
    final_state: dict
    task_id: str

class GraderResponse(BaseModel):
    task_id: str
    score: float

class BaselineRequest(BaseModel):
    tasks: list[str] = ["task_1", "task_2", "task_3"]

class HumanizerRequest(BaseModel):
    session_id: str

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Liveness probe. HF Spaces pings this to confirm deployment."""
    return {"status": "ok", "env": "DRC-Env v1.0", "sessions_active": len(_sessions)}


@app.get("/tasks")
def list_tasks():
    """
    Return all task configs and the action schema.
    Judges use this to verify the environment has 3+ tasks.
    """
    return {
        "tasks": [
            {
                "task_id": tid,
                "name": cfg["name"],
                "difficulty": cfg["difficulty"],
                "max_steps": cfg["max_steps"],
                "zones": len(cfg["zones"]),
                "resources": cfg["resources"],
                "false_sos_zones": cfg.get("false_sos_zones", []),
            }
            for tid, cfg in ALL_TASKS.items()
        ],
        "action_schema": {
            "deploy_team":  {"action": "deploy_team",  "to_zone": "str",  "units": "int"},
            "send_supplies": {"action": "send_supplies", "to_zone": "str",  "units": "int"},
            "airlift":       {"action": "airlift",       "to_zone": "str",  "type": "rescue|supply"},
            "recall_team":   {"action": "recall_team",   "from_zone": "str", "units": "int"},
            "wait":          {"action": "wait"},
        },
        "observation_fields": [
            "zones[].zone_id", "zones[].casualties_remaining", "zones[].supply_gap",
            "zones[].severity", "zones[].road_blocked", "zones[].teams_present", "zones[].sos_active",
            "resources.teams_available", "resources.supply_stock",
            "resources.airlifts_remaining", "resources.teams_in_transit",
            "step_number", "steps_remaining", "weather", "last_action_result",
        ],
    }


@app.post("/reset", response_model=ResetResponse)
def reset(req: ResetRequest):
    """
    Initialize a new episode. Returns session_id + first observation.
    Pass session_id to all subsequent /step and /state calls.
    """
    if req.task_id not in ALL_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id '{req.task_id}'. Valid: {list(ALL_TASKS.keys())}"
        )
    session_id, env = _create_session()
    obs = env.reset(req.task_id)
    return ResetResponse(session_id=session_id, observation=obs)


@app.post("/step", response_model=StepResult)
def step(req: StepRequest):
    """
    Submit one action for the given session. Advances world state by one timestep.
    Returns observation, reward, done flag, and reward breakdown in info.
    """
    env = _get_session(req.session_id)
    try:
        result = env.step(req.action)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.get("/state/{session_id}")
def state(session_id: str):
    """
    Return full internal world state including hidden fields (casualties_critical, is_false_sos).
    Used by graders and for debugging. Not exposed to the agent during inference.
    """
    env = _get_session(session_id)
    return env.state()


@app.post("/grader", response_model=GraderResponse)
def grader(req: GraderRequest):
    """
    Score a completed episode trajectory.
    Accepts event_log + final_state dict (from /state endpoint after done=True).
    Returns grader score in [0.0, 1.0].
    """
    if req.task_id not in ALL_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id '{req.task_id}'. Valid: {list(ALL_TASKS.keys())}"
        )
    try:
        score = grade_episode(req.event_log, req.final_state, req.task_id)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Grader error: {e}")
    return GraderResponse(task_id=req.task_id, score=score)


@app.post("/baseline")
def baseline(req: BaselineRequest):
    """
    Run baseline agent on the specified tasks (default: all 3).
    Requires GROQ_API_KEY environment variable.
    Returns grader scores for each task.
    WARNING: This takes 1–3 minutes to complete.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not groq_key and not openai_key:
        raise HTTPException(
            status_code=503,
            detail="No API key set. Configure GROQ_API_KEY (recommended, free) or OPENAI_API_KEY in HF Space Secrets to enable /baseline."
        )

    # Import here to avoid loading OpenAI client on startup if key not present
    try:
        from inference_v2 import run_task
    except ImportError:
        from inference import run_task  # fallback to v1 inference

    results = {}
    for task_id in req.tasks:
        if task_id not in ALL_TASKS:
            results[task_id] = {"error": f"Unknown task_id: {task_id}"}
            continue
        try:
            result = run_task(task_id, verbose=False)
            results[task_id] = result
        except Exception as e:
            results[task_id] = {"error": str(e), "grader_score": 0.0}

    return {
        "baseline_scores": results,
        "pipeline": "PyTorch ZoneScorer → Triage → Planner → Action (4-stage)",
        "model": "llama-3.3-70b-versatile (all tasks)",
        "note": "Scores are reproducible at temperature=0.",
    }


@app.post("/humanizer")
def humanizer(req: HumanizerRequest):
    """
    Convert the current session state into a plain-English situation report.

    Takes a session_id and returns a human-readable briefing describing:
    - Active disaster zones with casualties and supply needs
    - Which zones have road blocks (require airlift)
    - False SOS suspect zones (high severity but zero casualties)
    - Available resources at HQ
    - Weather conditions and step count
    - Recommended next action

    Useful for: debugging agent decisions, demos, and understanding what
    the environment is doing without reading raw JSON.
    """
    env = _get_session(req.session_id)
    state = env.state()

    # --- Weather line
    weather = state.get("weather", "clear")
    weather_desc = {
        "clear": "Weather is clear — all ground routes operational.",
        "storm": "STORM WARNING — storm conditions active, some roads may be blocked.",
        "flood": "FLOOD ALERT — flooding reported, multiple road blocks in effect.",
    }.get(weather, f"Weather: {weather}.")

    # --- Resources
    teams   = state.get("teams_available", 0)
    supply  = state.get("supply_stock", 0)
    airlift = state.get("airlifts_remaining", 0)
    transit = state.get("teams_in_transit", {})
    step    = state.get("current_step", 0)
    max_s   = state.get("max_steps", 10)
    steps_left = max_s - step

    lines = []
    lines.append(f"=== SITUATION REPORT — Step {step}/{max_s} ({steps_left} steps remaining) ===")
    lines.append(f"{weather_desc}")
    lines.append("")
    lines.append(f"HQ RESOURCES:")
    lines.append(f"  Rescue teams available : {teams}")
    lines.append(f"  Supply units in stock  : {supply}")
    lines.append(f"  Airlifts remaining     : {airlift}  (SCARCE — use wisely)")
    if transit:
        transit_str = ", ".join(f"{k}: {v} teams" for k, v in transit.items())
        lines.append(f"  Teams in transit       : {transit_str} (arrive next step)")
    lines.append("")

    # --- Zone breakdown
    zones = state.get("zones", [])
    critical_zones   = []
    needy_zones      = []
    false_sos_zones  = []
    blocked_zones    = []
    completed_zones  = []

    for z in zones:
        zid      = z["zone_id"]
        cas_rem  = z["casualties_total"] - z["casualties_rescued"]
        sup_gap  = z["supply_needed"] - z["supply_received"]
        blocked  = z["road_blocked"]
        is_false = z["is_false_sos"]
        sev      = z["severity"]
        teams_on = z["teams_present"]
        done     = z.get("completed", False)

        if is_false:
            false_sos_zones.append((zid, sev))
        elif done:
            completed_zones.append(zid)
        elif cas_rem > 0 and sev >= 0.75:
            critical_zones.append((zid, cas_rem, sup_gap, blocked, teams_on))
        elif cas_rem > 0 or sup_gap > 0:
            needy_zones.append((zid, cas_rem, sup_gap, blocked, teams_on))
        if blocked and not is_false and not done:
            blocked_zones.append(zid)

    if critical_zones:
        lines.append("CRITICAL ZONES (severity ≥ 0.75 — act immediately):")
        for zid, cas, sup, blk, t in critical_zones:
            road = "ROAD BLOCKED — needs airlift" if blk else "road clear"
            lines.append(f"  Zone {zid}: {cas} casualties remaining, {sup} supply gap | {road} | {t} teams on site")
    else:
        lines.append("No critical zones at this step.")

    lines.append("")

    if needy_zones:
        lines.append("ACTIVE ZONES (need attention):")
        for zid, cas, sup, blk, t in needy_zones:
            road = "road BLOCKED" if blk else "road clear"
            lines.append(f"  Zone {zid}: {cas} casualties, {sup} supply gap | {road} | {t} teams on site")
    lines.append("")

    if false_sos_zones:
        lines.append("FALSE SOS SUSPECTS (ignore — sending resources here wastes them):")
        for zid, sev in false_sos_zones:
            lines.append(f"  Zone {zid}: severity={sev:.2f} but ZERO real casualties — likely false alarm")
    lines.append("")

    if completed_zones:
        lines.append(f"COMPLETED ZONES (fully rescued + supplied): {', '.join(completed_zones)}")
        lines.append("")

    # --- Simple recommendation
    lines.append("RECOMMENDED ACTION:")
    if airlift > 0 and critical_zones:
        zid = critical_zones[0][0]
        if critical_zones[0][3]:  # blocked
            lines.append(f"  airlift Zone {zid} (critical + road blocked) — use your airlift now.")
        else:
            lines.append(f"  deploy_team to Zone {zid} (highest severity, road clear, {teams} teams available).")
    elif critical_zones and teams > 0:
        zid = critical_zones[0][0]
        lines.append(f"  deploy_team to Zone {zid} (critical zone, {teams} teams at HQ).")
    elif needy_zones and teams > 0:
        zid = needy_zones[0][0]
        lines.append(f"  deploy_team to Zone {zid} (next priority zone, {teams} teams at HQ).")
    elif needy_zones and supply > 0:
        zid = needy_zones[0][0]
        lines.append(f"  send_supplies to Zone {zid} (no teams available but supplies can help).")
    else:
        lines.append("  wait — no immediate action recommended (but wait incurs a penalty).")

    report = "\n".join(lines)
    return {
        "session_id": req.session_id,
        "step": step,
        "max_steps": max_s,
        "steps_remaining": steps_left,
        "report": report,
        "summary": {
            "critical_zones":  [z[0] for z in critical_zones],
            "needy_zones":     [z[0] for z in needy_zones],
            "false_sos_zones": [z[0] for z in false_sos_zones],
            "blocked_zones":   blocked_zones,
            "completed_zones": completed_zones,
            "resources": {
                "teams": teams,
                "supply": supply,
                "airlifts": airlift,
            },
        },
    }


# ---------------------------------------------------------------------------
# HF Spaces entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

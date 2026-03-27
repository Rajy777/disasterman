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


# ---------------------------------------------------------------------------
# HF Spaces entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

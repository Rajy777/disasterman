# Disaster Relief Coordination Env (DRC-Env)

**OpenEnv-compliant AI agent training environment**
Team: Agentic Apocalypse · Hackathon: OpenEnv Round 1 · Version 1.0

---

## What Is This?

DRC-Env is a real-world AI agent training and evaluation environment built on the OpenEnv specification. It simulates a multi-zone disaster response operation where an AI agent acts as an emergency coordinator — deploying rescue teams, routing supply trucks, and making strategic airlift decisions under time pressure, resource constraints, and deliberately misleading false SOS signals.

**Why it's novel:** No existing OpenEnv environment tests cascading failures, false SOS signals, and constrained multi-resource allocation simultaneously.

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Groq API key (needed for /baseline only)
export GROQ_API_KEY=your_key_here

# 3. Start the server
python main.py

# 4. Test it
curl http://localhost:7860/health
curl http://localhost:7860/tasks
```

### Docker

```bash
docker build -t drc-env .
docker run -p 7860:7860 -e GROQ_API_KEY=your_key drc-env
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/tasks` | List all 3 tasks + action schema |
| POST | `/reset` | Start new episode → `{session_id, observation}` |
| POST | `/step` | Submit one action → `{observation, reward, done, info}` |
| GET | `/state/{session_id}` | Full state (hidden fields for graders) |
| POST | `/grader` | Score completed episode → `{score: float}` |
| POST | `/baseline` | Run baseline agent on all 3 tasks |

### Example: Run a full episode

```python
import requests

BASE = "http://localhost:7860"

# 1. Start episode
r = requests.post(f"{BASE}/reset", json={"task_id": "task_1"})
session_id = r.json()["session_id"]
obs = r.json()["observation"]

# 2. Agent loop
while True:
    action = {"action": "deploy_team", "to_zone": "A", "units": 2}
    r = requests.post(f"{BASE}/step", json={"session_id": session_id, "action": action})
    result = r.json()
    if result["done"]:
        break

# 3. Get final state and score
state = requests.get(f"{BASE}/state/{session_id}").json()
score = requests.post(f"{BASE}/grader", json={
    "event_log": state["event_log"],
    "final_state": state,
    "task_id": "task_1"
}).json()["score"]

print(f"Final score: {score:.4f}")
```

---

## Observation Space

The agent receives a **filtered view** of the world — not the full state. Hidden fields (`casualties_critical`, `is_false_sos`) are excluded to simulate realistic partial observability.

```json
{
  "zones": [
    {
      "zone_id": "A",
      "casualties_remaining": 15,
      "supply_gap": 40,
      "severity": 0.82,
      "road_blocked": false,
      "teams_present": 2,
      "sos_active": true
    }
  ],
  "resources": {
    "teams_available": 4,
    "supply_stock": 120,
    "airlifts_remaining": 1,
    "teams_in_transit": {}
  },
  "step_number": 3,
  "steps_remaining": 7,
  "weather": "clear",
  "last_action_result": "success"
}
```

**Key design choices:**
- `severity` (0–1) hides `casualties_critical` — the agent must infer urgency from context
- `sos_active` is `True` for both real AND false SOS zones — agent cannot distinguish directly
- `last_action_result` gives feedback without exposing internal state

---

## Action Space

| Action | JSON | Effect |
|--------|------|--------|
| `deploy_team` | `{"action":"deploy_team","to_zone":"B","units":2}` | Move N rescue teams to zone. Fails if road blocked. |
| `send_supplies` | `{"action":"send_supplies","to_zone":"C","units":40}` | Route supply units. Oversupply is waste. |
| `airlift` | `{"action":"airlift","to_zone":"D","type":"rescue"}` | Bypass road blocks. Scarce resource. |
| `recall_team` | `{"action":"recall_team","from_zone":"A","units":1}` | Pull teams back. 1-step transit delay. |
| `wait` | `{"action":"wait"}` | Do nothing. Always penalized. |

---

## Tasks

### Task 1 — Single Zone Flood (Easy)
- 1 zone, 10 steps, 8 teams, 200 supply, 0 airlifts
- No road blocks, no events
- A competent agent deploys all teams immediately and sends the correct supply amount
- **GPT-4 target: 0.70–0.85**
- **Grader:** `0.6 × rescue_score + 0.4 × supply_score`

### Task 2 — Multi-Zone Earthquake (Medium)
- 5 zones, 15 steps, 6 teams, 150 supply, 1 airlift
- Zones B and C blocked at start; C unblocks at step 5
- Storm hits step 8, blocking zone D for 3 steps
- **GPT-4 target: 0.40–0.60**
- **Grader:** `0.50 × rescue + 0.30 × critical_response + 0.20 × efficiency`

### Task 3 — Cyclone with Cascading Failures (Hard)
- 10 zones (7 real + **3 false SOS**), 20 steps, 8 teams, 200 supply, 2 airlifts
- Dam breaks at step 7 → adds 60 casualties to Zone E
- Weather: storm (3–4), flood (5–7), storm (8), clear (9+)
- **False SOS zones H, I, J** emit `sos_active=True` but have zero casualties
- **GPT-4 target: 0.20–0.40**
- **Grader:** `0.45 × rescue + 0.25 × response_time + 0.20 × airlift_iq + 0.10 × efficiency − false_sos_penalty`

> **The winning detail:** An agent that responds to every SOS wastes resources on H/I/J, dropping score by 0.15+. This mechanic breaks frontier models.

---

## Reward Function

```
step_reward = clamp(R_positive − R_negative, −1.0, 1.0)
episode_score = (tanh(cumulative / max_steps × 2) + 1) / 2  →  [0.0, 1.0]
```

| Weight | Component | Formula |
|--------|-----------|---------|
| +0.40 | Rescue progress | new_rescues / max_rescuable_this_step |
| +0.20 | Supply gap closed | gap_closed / total_gap |
| +0.15 | Zone completion | Binary bonus per completed zone |
| +0.15 | Critical rescue | Rescues from severity ≥ 0.75 zones |
| +0.10 | Airlift precision | +1.0 blocked+critical, −0.5 accessible |
| −0.40 | Critical deaths | expired / critical_total |
| −0.15 | Urgency decay | Severity sum of unattended zones |
| −0.10 | Overcommitment | Teams idle in completed zones |
| −0.05 | Supply waste | wasted / total_sent |
| −0.05 | False SOS | Resources on ghost zones |
| −0.05 | Wait penalty | Flat per-step penalty |

---

## Baseline Scores

Baseline agent: **Llama 3.3-70B (Task 3) / Llama 3.1-8B (Tasks 1–2)** via Groq API
Architecture: 2-agent chain per step (Triage Agent → Action Agent)
Temperature: 0.0 (deterministic)

| Task | Score | Target | Status |
|------|-------|--------|--------|
| task_1 (Easy) | TBD | 0.70–0.85 | Run after deploy |
| task_2 (Medium) | TBD | 0.40–0.60 | Run after deploy |
| task_3 (Hard) | TBD | 0.20–0.40 | Run after deploy |

> Run `POST /baseline` after deployment to populate scores.

---

## Project Structure

```
disasterman-v2/
├── main.py             FastAPI server — all OpenEnv endpoints
├── environment.py      DisasterEnv: reset(), step(), state()
├── models.py           Pydantic contracts (frozen after first push)
├── reward.py           compute_step_reward() — pure function, unit-testable
├── graders.py          grade_task_1/2/3() — deterministic scoring
├── tasks.py            TASK_1/2/3 config dicts
├── agents/
│   ├── triage_agent.py Triage Analyst — zone priority + false SOS detection
│   └── action_agent.py Action Coordinator — takes triage JSON, returns action
├── inference_v2.py     Multi-agent parallel runner (3 tasks simultaneously)
├── test_env.py         20-test integration suite
├── openenv.yaml        OpenEnv spec metadata
├── Dockerfile          python:3.11-slim, exposes port 7860
└── requirements.txt    fastapi, uvicorn, pydantic, openai
```

---

## Team

| Member | Files | Role |
|--------|-------|------|
| Krish Potanwar | models.py, reward.py, graders.py | Foundation layer |
| Tushar Sharma | environment.py, tasks.py | Core simulation engine |
| Raj Yadav | inference.py, test_env.py, main.py | Integration + API |

---

## Pre-Submission Checklist

- [ ] `docker build && docker run` works from scratch
- [ ] `GET /health` returns 200
- [ ] `GET /tasks` lists 3 tasks
- [ ] `openenv validate` passes with zero errors
- [ ] Baseline scores populated in README
- [ ] All 20 integration tests pass: `python test_env.py`

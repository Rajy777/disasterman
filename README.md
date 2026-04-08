---
title: Disaster Relief Coordination Env
emoji: 🚑
colorFrom: red
colorTo: red
sdk: docker
pinned: false
license: mit
short_description: Multi-zone disaster relief AI env for OpenEnv
---

# Disaster Relief Coordination Env (DRC-Env)

**Meta PyTorch OpenEnv Hackathon by Scaler — OpenEnv-compliant AI training environment**

Every year, delayed disaster response costs lives. DRC-Env puts an AI agent in the role of an emergency coordinator managing real triage decisions: deploy rescue teams, route supplies, and call airlifts across multiple disaster zones — all under time pressure, resource scarcity, and deliberately injected false SOS signals designed to drain resources from zones that actually need them.

Live demo: **https://huggingface.co/spaces/krishpotanwar/disaster-relief-env**

Mirror (Vercel CDN): **https://disasterman-scaler-demo.vercel.app**

---

## Why This Environment Is Novel

Most benchmark environments test agents on clean, well-labeled observations. DRC-Env deliberately breaks that assumption in three ways:

**1. False SOS signals that look real.**
Zones H, I, and J in task_3 broadcast genuine-looking SOS signals with non-zero severity scores — but have zero casualties. There is no flag in the observation space that marks a signal as false; `is_false_sos` is hidden and only visible to the grader. An agent that cannot distinguish signal noise from genuine distress wastes scarce airlifts and misses the zones that matter. A reward penalty of −0.05 per false-SOS resource deployment reinforces this.

**2. Cascading failures mid-episode.**
At step 7 of task_3, a dam breaks and floods Zone E with 60 new casualties. Road conditions shift with weather. The agent must continuously replan — a static resource allocation computed at step 0 fails catastrophically. This tests generalization, not memorization.

**3. Native PyTorch integration in the decision loop.**
Stage 1 of the baseline pipeline is a trained PyTorch MLP (`ZoneScorerNet`) that runs inference every step at under 1ms. Its output — a priority score per zone — feeds directly into the LLM triage prompt. This is not a toy PyTorch import; it replaces what would otherwise require the LLM to reason from raw numbers, demonstrably improving score on task_2 and task_3.

---

## Tasks

| Task | Name | Difficulty | Zones | Steps | Target Score |
|------|------|-----------|-------|-------|--------------|
| task_1 | Single Zone Flood Response | Easy | 1 | 10 | 0.70–0.85 |
| task_2 | Multi-Zone Earthquake Response | Medium | 5 | 15 | 0.40–0.60 |
| task_3 | Cyclone + Cascading Failures + False SOS | Hard | 10 | 20 | 0.20–0.40 |

**task_3 in detail:** Zones H, I, J send plausible SOS signals with zero real casualties. At step 7 a dam breaks, flooding Zone E (+60 casualties). Weather shifts drive dynamic road blocks. Optimal play requires false-alarm detection, immediate dam-break redeployment, and airlift precision.

---

## Baseline Agent — 4-Stage PyTorch Pipeline

The included baseline fulfills the hackathon's PyTorch requirement through a production-style architecture, not a trivial import:

```
Stage 1: PyTorch ZoneScorerNet  — local MLP, <1ms inference, runs every step
Stage 2: Triage Agent           — LLM, false SOS detection + deadline alerts
Stage 3: Planner Agent          — LLM, 3-step lookahead resource allocation
Stage 4: Action Agent           — LLM + hard constraint validator + deterministic fallback
```

**ZoneScorerNet (Stage 1):**
Architecture: MLP 6→16→1 with Sigmoid output. Input features: `severity`, `casualty_ratio`, `supply_ratio`, `road_blocked`, `unattended`, `time_pressure`. Trained on 50K synthetic examples generated from the environment's own reward dynamics. False SOS zones consistently score near 0.0 — the network learns to ignore severity noise when casualty and supply ratios are zero. Training time: ~8 seconds on CPU. Pre-trained weights ship inside the Docker image so judges see no setup friction.

**Anti-hallucination strategy (Stage 4):**
LLMs hallucinate invalid zone IDs and over-commit resources. Three layers prevent this:
1. Constraint injection — every prompt lists valid zone IDs, blocked roads, and exact resource counts
2. Post-LLM hard validator (`_validate_and_fix()`) — rejects any action that violates game rules
3. Deterministic fallback heuristic — executes if LLM output fails validation, ensuring the episode always completes

**LLM:** `llama-3.3-70b-versatile` via Groq (free tier, high rate limits)

---

## Grader Coverage

The `/grader` endpoint scores all 8 dimensions defined in the OpenEnv spec:

| Dimension | How It Is Measured |
|-----------|-------------------|
| Task completion | Casualties rescued + supply gaps closed across all zones |
| Resource efficiency | Penalty for idle teams, supply over-delivery, and false SOS waste |
| Time performance | Urgency decay for high-severity zones left unattended |
| Decision quality | Critical rescues (severity ≥ 0.75) as a fraction of total |
| Adaptability | Score delta before vs. after the dam-break event (task_3) |
| False signal handling | Resources deployed to `is_false_sos` zones (hidden grader field) |
| Airlift precision | Airlifts used only on blocked + critical zones vs. total airlifts used |
| Episode score | `(tanh(cumulative_reward / max_steps * 2) + 1) / 2` — normalized to [0, 1] |

---

## Observation Space

```
zones[]:
  zone_id               string         Zone identifier (A–J)
  casualties_remaining  int            Remaining casualties needing rescue
  supply_gap            int            Remaining supply deficit
  severity              float [0,1]    Urgency score (hides casualties_critical)
  road_blocked          bool           Whether ground deployment is blocked
  teams_present         int            Rescue teams currently in zone
  sos_active            bool           SOS signal active (real OR false — indistinguishable)

resources:
  teams_available       int            Teams at HQ ready to deploy
  supply_stock          int            Supply units available
  airlifts_remaining    int            Airlifts left (scarce)
  teams_in_transit      dict[str,int]  Teams currently traveling (1-step delay)

step_number             int
steps_remaining         int
weather                 string         [clear, storm, flood]
last_action_result      string         [success, invalid, blocked, insufficient_resources, none]
```

**Hidden from agent, visible to grader only:** `casualties_critical`, `is_false_sos`

---

## Action Space

| Action | Parameters | Description |
|--------|-----------|-------------|
| `deploy_team` | `to_zone`, `units` | Move teams to zone. Fails if road blocked. |
| `send_supplies` | `to_zone`, `units` | Route supply units to zone. |
| `airlift` | `to_zone`, `type` (rescue/supply) | Bypass road block. Consumes 1 airlift. |
| `recall_team` | `from_zone`, `units` | Pull teams back to HQ (1-step transit delay). |
| `wait` | — | Do nothing. Penalized every step. |

---

## Reward Function

```
step_reward    = clamp(R_positive - R_negative, -1.0, 1.0)
episode_score  = (tanh(cumulative_reward / max_steps * 2) + 1) / 2
```

| Component | Weight | Description |
|-----------|--------|-------------|
| rescue progress | +0.40 | Normalized casualties rescued |
| supply gap closed | +0.20 | Supply deficit addressed |
| zone completion | +0.15 | Zone fully rescued + supplied |
| critical rescues | +0.15 | Rescues from severity ≥ 0.75 zones |
| airlift precision | +0.10 | Smart airlift use on blocked+critical zones |
| critical deaths | −0.40 | Critical casualties expired |
| urgency decay | −0.15 | High-severity zones left unattended |
| overcommitment | −0.10 | Teams idling in completed zones |
| supply waste | −0.05 | Over-delivery of supplies |
| false SOS | −0.05 | Resources deployed to false alarm zones |
| wait penalty | −0.05 | Flat penalty per wait action |

---

## Setup & Usage

### Prerequisites

- Python 3.11+
- `HF_TOKEN` — your Groq API key (free at [console.groq.com](https://console.groq.com)) set as this env var
- `API_BASE_URL` — defaults to `https://api.groq.com/openai/v1`
- `MODEL_NAME` — defaults to `llama-3.3-70b-versatile`

### Local Development

```bash
# Install dependencies
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Pre-train ZoneScorerNet (one-time, ~8 seconds)
python agents/train_zone_scorer.py

# Start the FastAPI server
python main.py
# Server runs at http://localhost:7860

# Run the 4-stage baseline agent on all tasks
export HF_TOKEN=your_groq_key_here   # required
export API_BASE_URL=https://api.groq.com/openai/v1   # optional, this is the default
export MODEL_NAME=llama-3.3-70b-versatile             # optional, this is the default
python inference.py
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/tasks` | List all tasks + action schema |
| POST | `/reset` | Start new episode → `{session_id, observation}` |
| POST | `/step` | Submit action → `{observation, reward, done, info}` |
| GET | `/state/{session_id}` | Full state including hidden fields (for graders) |
| POST | `/grader` | Score a completed episode (all 8 dimensions) |
| POST | `/baseline` | Run baseline agent on all 3 tasks (requires API key) |
| GET | `/simulate/stream/{task_id}?agent=...` | Live SSE stream of 4-stage agent thinking + step updates |

### Quick Test

```bash
# Start episode
curl -X POST http://localhost:7860/reset \
     -H "Content-Type: application/json" \
     -d '{"task_id": "task_1"}'

# Take action (use session_id from reset response)
curl -X POST http://localhost:7860/step \
     -H "Content-Type: application/json" \
     -d '{"session_id": "<id>", "action": {"action": "deploy_team", "to_zone": "A", "units": 3}}'
```

---

## Docker / HF Spaces

The Docker image builds both the Python backend and the React frontend in a single container. At build time it:
1. Installs Node.js 20 and runs `npm install && npm run build` inside `frontend/`
2. Trains `ZoneScorerNet` and bakes the weights into the image
3. Starts FastAPI on port 7860 — serves the React SPA at `/` and the API at `/health`, `/tasks`, `/reset`, `/step`, etc.

```bash
# Build
docker build -t drc-env .

# Run
docker run -p 7860:7860 -e HF_TOKEN=your_groq_key drc-env
# Full UI + API at http://localhost:7860
```

See `DEPLOY_TO_HF.txt` for the full Hugging Face Spaces deployment guide.

---

## Frontend Deployment

The React dashboard is served in two ways:

| URL | How | Notes |
|-----|-----|-------|
| `https://krishpotanwar-disaster-relief-env.hf.space` | FastAPI serves `frontend/dist/` directly | Primary — self-contained, use for hackathon submission |
| `https://disasterman-scaler-demo.vercel.app` | Vercel CDN, proxies `/api/*` to HF | Mirror — faster static asset delivery |

The Vercel mirror uses proxy mode: `frontend/vercel.json` rewrites `/api/*` → `https://krishpotanwar-disaster-relief-env.hf.space/*`. No `VITE_API_URL` env var needed.

Backend supports both canonical and compatibility routes:
- Canonical: `/health`, `/tasks`, `/reset`, `/step`, `/simulate/{task_id}`, `/compare/{task_id}`, `/simulate/stream/{task_id}`
- Compatibility: `/api/health`, `/api/tasks`, `/api/reset`, `/api/step`, `/api/simulate/{task_id}`, `/api/compare/{task_id}`, `/api/simulate/stream/{task_id}`

---

## Interactive Dashboard

The HF Space serves a full React dashboard at the root URL alongside the API. Six tabs:

| Tab | What it shows |
|-----|--------------|
| **Strategy Generator** | Groq-powered AI strategy generation — enter a scenario, get a full response plan |
| **Command Center** | Operational command & control view with probability matrix and comms intercept terminal |
| **Simulate** | Step-by-step episode runner with per-zone card grid (casualties, supply, PyTorch score, action icons) |
| **Live Demo** | Leaflet Bengaluru map — 3 scenarios (cyclone, flood, building collapse) with SSE-streamed 4-stage agent reasoning |
| **Compare** | Side-by-side Random vs Greedy vs 4-Stage AI agent score comparison across tasks |
| **System Logs** | Live backend observability — endpoint activity, session log, agent pipeline traces |

**Landing page** with project overview loads before the tab interface.

Key features across all tabs:
- 4-stage streaming thought process (`PyTorch → Triage → Planner → Action`) via SSE
- Leaflet Bengaluru map with 10 native city-side zone coordinates and resource routing overlays
- Probability matrix for zone priority visualization
- Comms Intercept Terminal showing raw SOS signal analysis
- Recruiter-facing explainability panel + Copilot Q&A prompts

---

## Expected Baseline Scores

| Task | Score Range | Notes |
|------|------------|-------|
| task_1 | 0.75–0.90 | Easy, single zone |
| task_2 | 0.45–0.65 | Medium, multi-zone with resource scarcity |
| task_3 | 0.25–0.45 | Hard, false SOS + cascading failures |

Scores are reproducible at `temperature=0`.

---

## Project Structure

```
disasterman/
├── main.py                    # FastAPI server — OpenEnv API + React SPA serving
├── environment.py             # DisasterEnv — world state + step logic
├── models.py                  # Pydantic models (ActionModel, ObservationModel)
├── reward.py                  # Reward function components
├── graders.py                 # Episode grader — returns [0.0, 1.0] across 8 dimensions
├── tasks.py                   # Task configurations (task_1, task_2, task_3)
├── inference.py               # 4-stage agent pipeline runner
├── test_env.py                # Environment unit tests (98 tests)
├── demo_runner.py             # Bengaluru live demo scenario runner
├── demo_scenarios.py          # Demo scenario definitions (cyclone, flood, collapse)
├── demo_models.py             # Demo data models
├── requirements.txt
├── Dockerfile                 # Builds frontend + trains ZoneScorerNet at image build time
├── openenv.yaml               # OpenEnv spec
├── agents/
│   ├── zone_scorer.py         # PyTorch ZoneScorerNet (Stage 1)
│   ├── zone_scorer_weights.pt # Pre-trained weights (baked into Docker image)
│   ├── train_zone_scorer.py   # Training script (~8s on CPU)
│   ├── triage_agent.py        # Triage Agent — false SOS detection (Stage 2)
│   ├── planner_agent.py       # Planner Agent — 3-step lookahead (Stage 3)
│   └── action_agent.py        # Action Agent + hard validator + fallback (Stage 4)
└── frontend/                  # React 18 + TypeScript + Vite + Tailwind dashboard
    └── src/
        └── components/
            ├── LandingPage.tsx
            ├── CommandCenterTab.tsx
            ├── StrategyGeneratorTab.tsx
            ├── SimulationTab.tsx
            ├── LiveDemoTab.tsx
            ├── CompareTab.tsx
            └── SystemLogsTab.tsx
```

---

## Team

**Agentic Apocalypse** — Built for the Meta PyTorch OpenEnv Hackathon by Scaler.

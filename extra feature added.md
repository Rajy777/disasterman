# Extra Feature Added

## What was added
- Leaflet-based Bengaluru live disaster map
- SSE streaming endpoint for live simulation thinking flow
- 4-stage pipeline visualization (PyTorch -> Triage -> Planner -> Action)
- Recruiter-facing Copilot Q&A panel
- Zustand real-time stream store

## Deployment targets
- Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo
- Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space
- Isolated Vercel app: https://disasterman-scaler-demo.vercel.app

## Notes
This log was created on request to track extra features added in this session.

## Detailed Session Log

### 2026-04-01 05:10:37 IST — Milestone 1: Backend Bengaluru live demo pipeline
- Backend changes:
  - Added `demo_models.py` with separate demo-only contracts (`DemoScenarioSummary`, `DemoScenarioDetail`, `DemoRunResult`, `DemoStep`, `DemoMapState`, `DemoResourceMovement`, `DemoMapOverlay`).
  - Added `demo_scenarios.py` with exactly three curated Bengaluru scenarios: `bellandur_flood_response`, `peenya_industrial_fire`, and `whitefield_building_collapse`.
  - Added `demo_runner.py` with a dedicated `DemoDisasterEnv`, backend-authored map state, resource positions, route movement payloads, and deterministic 4-stage fallback reasoning for `ai_4stage` when API keys are missing.
  - Added separate demo endpoints in `main.py`: `GET /demo/scenarios`, `POST /demo/run/{scenario_id}`, `GET /demo/stream/{scenario_id}`, plus `/api/demo/*` aliases.
- Frontend changes: none in this milestone.
- Deploy changes: none in this milestone.
- Verification performed:
  - Local smoke test: `run_demo_scenario('bellandur_flood_response', 'greedy')`
  - FastAPI TestClient checks for `/demo/scenarios` and `/demo/run/bellandur_flood_response`
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — local implementation completed in workspace, not pushed in this session.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — target backend URL identified, deployment not updated in this session.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — target frontend URL identified, deployment not updated in this session.
- Known issues/open follow-ups:
  - If `GROQ_API_KEY` or `OPENAI_API_KEY` is absent, demo `ai_4stage` intentionally runs deterministic fallback reasoning instead of live LLM calls so the reviewer demo still works.

### 2026-04-01 05:10:37 IST — Milestone 2: Leaflet reviewer-facing frontend
- Backend changes:
  - No new backend routes added in this milestone; frontend consumed the previously added `/demo/*` APIs.
- Frontend changes:
  - Added a new top-level `Live Demo` tab in `frontend/src/App.tsx`.
  - Added `frontend/src/components/LiveDemoTab.tsx` with scenario cards, agent selector, run controls, step scrubber, replay controls, live stage timeline support, and automatic SSE-to-HTTP replay fallback.
  - Added `frontend/src/components/LeafletDemoMap.tsx` using real Leaflet tiles for Bengaluru, curated route polylines, scenario overlays, active target highlighting, resource markers, and animated movement markers.
  - Expanded `frontend/src/types.ts` with demo interfaces and expanded `frontend/src/api/client.ts` with demo catalog/run/stream helpers.
  - Restored Leaflet CSS in `frontend/src/index.css`.
- Deploy changes: none in this milestone.
- Verification performed:
  - `npm run lint`
  - `npm run build`
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — code prepared locally, not pushed in this session.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — expected backend target for the new frontend wiring.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — expected frontend target once pushed/deployed.
- Known issues/open follow-ups:
  - Production build emits a large-chunk warning from Vite because the map/demo code adds bundle weight, but the build still succeeds.

### 2026-04-01 05:10:37 IST — Milestone 3: Isolated deployment wiring
- Backend changes: none in this milestone.
- Frontend changes:
  - Updated `frontend/vercel.json` so `/api/*` now proxies to `https://krishpotanwar-disasterman-scaler-demo.hf.space/*` instead of the main HF backend.
  - Updated app header links to point at the isolated repo and isolated HF docs.
- Deploy changes:
  - Deployment targets were rewired in config only.
  - No push, merge, or deployment command was run in this session.
- Verification performed:
  - Confirmed the new Vercel rewrite target locally in `frontend/vercel.json`.
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — config-ready, no push in this session.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — configured as proxy destination.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — configured as intended deployment surface.
- Known issues/open follow-ups:
  - Live URLs will not reflect these changes until the isolated remotes are pushed and deployed.

### 2026-04-01 05:10:37 IST — Milestone 4: Verification sweep
- Backend changes:
  - Added live demo regression checks to `test_env.py` covering scenario registry shape, `/demo/scenarios`, `/demo/run`, stream event ordering via `iter_demo_events`, and schema stability across `ai_4stage`, `greedy`, and `random`.
- Frontend changes: none beyond those already listed above.
- Deploy changes: none.
- Verification performed:
  - `python3 test_env.py` → `124/124 passed`
  - `npm run lint` → passed
  - `npm run build` → passed
  - FastAPI SSE smoke test for `/demo/stream/peenya_industrial_fire?agent=greedy` → event order observed as `meta`, `stage`, `stage`, `stage`, `stage`, `step`, ... `done`
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — verified locally only.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — not redeployed from this session.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — not redeployed from this session.
- Known issues/open follow-ups:
  - No deployment/push was performed in this session because isolated-first implementation was completed locally and awaits your explicit go-ahead for publishing.

### 2026-04-01 05:17:19 IST — Milestone 5: Publication to isolated targets
- Backend changes:
  - Published commit `6d849c8` containing the Bengaluru demo backend (`demo_models.py`, `demo_scenarios.py`, `demo_runner.py`, and `main.py` demo endpoints) to the isolated GitHub and Hugging Face remotes.
- Frontend changes:
  - Published the Leaflet reviewer demo frontend and Vercel proxy wiring from the isolated frontend app.
- Deploy changes:
  - Pushed `HEAD -> main` to isolated GitHub repo `Krishpotanwar/disasterman-scaler-demo`.
  - Pushed `HEAD -> main` to isolated Hugging Face Space `krishpotanwar/disasterman-scaler-demo`.
  - Deployed the isolated Vercel production app with Vercel CLI.
  - Production deployment details:
    - deployment id: `dpl_EJHjnigbCzk1ePnzoQgpvndyBMev`
    - production url: `https://disasterman-scaler-demo-pjb9t2fq0-krishpotanwars-projects.vercel.app`
    - alias: `https://disasterman-scaler-demo.vercel.app`
- Verification performed:
  - Hugging Face Space metadata confirmed repo SHA `6d849c8d955fb4d417afb7886a053f698bc54821` and runtime SHA matched after rollout.
  - `https://krishpotanwar-disasterman-scaler-demo.hf.space/health` → `200`
  - `https://krishpotanwar-disasterman-scaler-demo.hf.space/api/demo/scenarios` → `200`
  - `https://disasterman-scaler-demo.vercel.app/` → `200`
  - `https://disasterman-scaler-demo.vercel.app/api/demo/scenarios` → `200`
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — updated on `main` with commit `6d849c8`.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — live and serving the demo API.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — live and proxying to the isolated HF backend.
- Known issues/open follow-ups:
  - Vite still reports a large bundle-size warning during production build, but the deployment completed successfully and is live.

### 2026-04-01 05:17:19 IST — Milestone 6: Production API base hotfix
- Backend changes: none.
- Frontend changes:
  - Fixed `frontend/src/api/client.ts` so production always uses the Vercel `/api` proxy instead of trusting `VITE_API_URL`.
  - This prevents stale build-time env values from pointing the deployed frontend at the wrong HF Space for new demo endpoints.
- Deploy changes:
  - Prepared a frontend-only patch release for isolated targets after a live 404 report from the deployed app.
- Verification performed:
  - Local production build succeeded after the change.
  - Verified the compiled production bundle resolves the runtime API base to `/api`.
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — pending patch push from this milestone.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — backend unchanged by this milestone.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — pending redeploy from this milestone.
- Known issues/open follow-ups:
  - The old HF URL string may still appear in the minified asset as dead compile-time env text, but runtime requests now resolve through `/api`.

### 2026-04-01 05:32:41 IST — Milestone 7: Replay controls and map legend polish
- Backend changes: none.
- Frontend changes:
  - Added explicit `Prev` and `Next` replay step buttons to `frontend/src/components/LiveDemoTab.tsx` so reviewers can move through the simulation one step at a time without using only the scrubber.
  - Clarified the map legend in `frontend/src/components/LeafletDemoMap.tsx` by adding `Support hub`, `Medical node`, and `False alert` entries.
  - Tuned location colors so support hubs and medical nodes are visually distinct instead of both reading as generic green markers.
- Deploy changes:
  - Prepared a frontend-only patch release for the isolated Vercel app.
- Verification performed:
  - `npm run build` → passed
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — pending patch push from this milestone.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — backend unchanged by this milestone.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — pending redeploy from this milestone.
- Known issues/open follow-ups:
  - Vite still reports the existing large bundle-size warning, but the frontend build succeeds.

### 2026-04-01 05:51:53 IST — Milestone 8: Benchmark SSE fallback and clearer no-key handling
- Backend changes: none.
- Frontend changes:
  - Updated `frontend/src/components/SimulationTab.tsx` so benchmark runs fall back to the standard `/simulate/{task_id}` replay API if the SSE stream fails before any step data arrives.
  - This turns a generic `SSE stream failed (...)` message into the backend-authored validation detail for no-key `ai_4stage` runs, while still preserving live-mode behavior when a stream has already delivered replay data.
  - Updated `frontend/src/hooks/useSimulation.ts` to surface `Error.message` directly so API failures render as cleaner user-facing messages instead of `String(error)` output.
- Deploy changes:
  - Prepared a frontend-only patch release for the isolated Vercel app after a production report from the benchmark `Simulate` tab.
- Verification performed:
  - Live endpoint check: `GET /api/simulate/stream/task_3?agent=ai_4stage` returns `503` with the expected no-key detail from the isolated backend.
  - Live endpoint check: `POST /api/simulate/task_3` returns the same `503` detail, confirming the fallback path can surface the real cause.
  - `npm run build` → passed
- Current live URLs/status:
  - Isolated GitHub repo: https://github.com/Krishpotanwar/disasterman-scaler-demo — pending patch push from this milestone.
  - Isolated Hugging Face Space: https://krishpotanwar-disasterman-scaler-demo.hf.space — backend unchanged by this milestone.
  - Isolated Vercel app: https://disasterman-scaler-demo.vercel.app — pending redeploy from this milestone.
- Known issues/open follow-ups:
  - The isolated benchmark backend still does not have `GROQ_API_KEY` or `OPENAI_API_KEY`, so `ai_4stage` benchmark runs correctly remain unavailable there; this milestone only improves the reviewer-facing error/fallback behavior.

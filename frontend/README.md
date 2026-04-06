# DisasterMan Frontend

React + TypeScript + Vite frontend for the DisasterMan disaster-relief simulator.

## What It Does

- Loads task metadata from the FastAPI backend
- Replays full simulation runs step by step
- Compares `random`, `greedy`, and `ai_4stage` agents side by side
- Shows map state, resources, scores, and agent reasoning

## Local Development

From this `frontend/` directory:

```bash
npm install
npm run dev
```

Default API behavior:

- Development: `http://localhost:7860`
- Production: `/api` proxy
- Override: set `VITE_API_URL`

## Environment Variables

```bash
VITE_API_URL=http://localhost:7860
```

Use `VITE_API_URL` when you want the frontend to talk directly to a backend instead of using the production proxy rewrite.

## Build

```bash
npm run build
```

## Notes

- The compare view only includes the 4-stage AI agent when the backend has `GROQ_API_KEY` or `OPENAI_API_KEY` configured.
- Production rewrites for Vercel live in `vercel.json`.

"""
inference_v2.py — DisasterMan v3: 4-Stage Multi-Agent Pipeline.

Architecture per step:
  1. PyTorch ZoneScorer  — local neural net (<1ms), ranks zones by priority
  2. Triage Agent        — LLM analysis, false SOS detection, deadline alerts
  3. Planner Agent       — LLM 3-step lookahead, resource allocation plan
  4. Action Agent        — LLM final action + hard constraint validator

All tasks use llama-3.3-70b-versatile (best free planning model via Groq).
All 3 tasks run in parallel via ThreadPoolExecutor.

Anti-hallucination strategy:
  - Explicit constraint injection (valid zones, blocked zones, resource counts)
  - Post-LLM constraint validator in action_agent._validate_and_fix()
  - Deterministic fallback heuristic if LLM output fails validation

Usage:
  export GROQ_API_KEY=your_key
  python inference_v2.py
"""

from __future__ import annotations
import os
import time
import concurrent.futures
from openai import OpenAI

from environment import DisasterEnv
from graders import grade_episode
from agents.zone_scorer import score_zones
from agents.triage_agent import run_triage
from agents.planner_agent import run_planner
from agents.action_agent import get_action

# API key resolution: prefer GROQ (free, fast Llama 3.3 70B).
# Falls back to OPENAI_API_KEY for OpenAI GPT models if Groq key not set.
# The OpenAI Python client is used in both cases (OpenEnv spec requirement).
GROQ_KEY   = os.environ.get("GROQ_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

def _build_client() -> tuple[OpenAI, str]:
    """
    Return (client, model_name) using the best available API key.
    Groq is preferred: free tier supports llama-3.3-70b-versatile with high rate limits.
    Falls back to OpenAI GPT-4o-mini if only OPENAI_API_KEY is set.
    """
    if GROQ_KEY:
        return (
            OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_KEY),
            "llama-3.3-70b-versatile",
        )
    if OPENAI_KEY:
        return (
            OpenAI(api_key=OPENAI_KEY),
            "gpt-4o-mini",
        )
    raise EnvironmentError(
        "No API key found. Set GROQ_API_KEY (recommended, free) "
        "or OPENAI_API_KEY in your environment."
    )

# Step delay (seconds) — rate-limit buffer (3 LLM calls per step)
STEP_DELAY = 0.5

# GPT-4 target ranges for reference
SCORE_TARGETS = {
    "task_1": (0.70, 0.85),
    "task_2": (0.40, 0.60),
    "task_3": (0.20, 0.40),
}


def run_task(task_id: str, verbose: bool = True) -> dict:
    """
    Run one full episode using the 4-stage pipeline.

    Returns dict with:
        task_id, grader_score, cumulative_reward, steps_taken, model
    """
    client, MODEL = _build_client()

    env = DisasterEnv()
    obs = env.reset(task_id)
    history: list[dict] = []    # rolling action history for Action Agent
    total_reward = 0.0
    step = 0

    if verbose:
        print(f"\n{'='*65}")
        print(f"[{task_id.upper()}] Starting | 4-stage pipeline | Model: {MODEL}")
        print(f"{'='*65}")

    while True:
        obs_dict = obs.model_dump()

        # Stage 1 — PyTorch zone scoring (local, no API call)
        zone_scores = score_zones(obs_dict)

        # Stage 2 — Triage analysis (LLM, consumes PyTorch scores)
        triage = run_triage(obs_dict, client, MODEL, zone_scores=zone_scores)

        # Stage 3 — Strategic planner (LLM, 3-step lookahead)
        plan = run_planner(obs_dict, triage, zone_scores, client)

        # Stage 4 — Action execution (LLM + constraint validator)
        action = get_action(
            obs_dict, triage, history, client, MODEL,
            zone_scores=zone_scores,
            plan=plan,
        )

        result = env.step(action)
        total_reward += result.reward
        step += 1

        if verbose:
            false_sos = triage.get("false_sos_suspects", [])
            deadlines = triage.get("deadline_alerts", [])
            top_score = zone_scores[0]["zone_id"] if zone_scores else "?"

            suffix = ""
            if deadlines:
                suffix += f" [DL:{[d['zone_id'] for d in deadlines]}]"
            if false_sos:
                suffix += f" [FSOS:{false_sos}]"

            print(
                f"[{task_id}] S{step:02d} | {action.action:15s} "
                f"to={str(action.to_zone):4s} u={str(action.units):4s} "
                f"res={result.observation.last_action_result:20s} | "
                f"r={result.reward:+.3f} cum={total_reward:+.3f} | top={top_score}"
                + suffix
            )

        obs = result.observation
        if result.done:
            break

        time.sleep(STEP_DELAY)

    final_state = env.state()
    score = grade_episode(final_state["event_log"], final_state, task_id)
    lo, hi = SCORE_TARGETS[task_id]
    status = "✓ IN TARGET" if lo <= score <= hi else ("▲ ABOVE" if score > hi else "✗ BELOW")

    if verbose:
        print(f"\n[{task_id.upper()}] Score: {score:.4f} | Target: {lo:.2f}–{hi:.2f} | {status}")
        print(f"[{task_id.upper()}] Reward: {total_reward:.4f} | Steps: {step}")

    return {
        "task_id": task_id,
        "grader_score": score,
        "cumulative_reward": total_reward,
        "steps_taken": step,
        "model": MODEL,
    }


def run_all_parallel() -> dict:
    """
    Run all 3 tasks in parallel via ThreadPoolExecutor(max_workers=3).
    Each task has its own independent env + agent chain + Groq client.
    """
    if not GROQ_KEY and not OPENAI_KEY:
        raise EnvironmentError(
            "No API key found. Set GROQ_API_KEY (recommended, free at https://console.groq.com) "
            "or OPENAI_API_KEY in your environment."
        )

    _, model_name = _build_client()

    print("\n" + "=" * 65)
    print("DisasterMan v3 — 4-Stage Multi-Agent Pipeline")
    print("=" * 65)
    print("  Stage 1: PyTorch ZoneScorerNet  (local, ~0ms)")
    print(f"  Stage 2: Triage Agent           ({model_name}, ~800ms)")
    print(f"  Stage 3: Planner Agent          ({model_name}, ~1s)")
    print(f"  Stage 4: Action Agent + Validator ({model_name}, ~600ms)")
    print("  Running tasks: task_1, task_2, task_3 in PARALLEL")
    print("=" * 65)

    results: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(run_task, tid): tid
            for tid in ["task_1", "task_2", "task_3"]
        }
        for future in concurrent.futures.as_completed(futures):
            task_id = futures[future]
            try:
                results[task_id] = future.result()
            except Exception as exc:
                print(f"\n[ERROR] {task_id} raised: {exc}")
                results[task_id] = {
                    "task_id": task_id,
                    "grader_score": 0.0,
                    "error": str(exc),
                }

    return results


def print_summary(results: dict) -> None:
    print("\n" + "=" * 65)
    print("DISASTERMAN v3 — FINAL SCORES")
    print("=" * 65)
    total = 0.0
    for tid in ["task_1", "task_2", "task_3"]:
        r = results.get(tid, {})
        score = r.get("grader_score", 0.0)
        lo, hi = SCORE_TARGETS[tid]
        status = "✓" if lo <= score <= hi else ("▲ BEAT IT" if score > hi else "✗")
        print(f"  {tid}: {score:.4f}  GPT-4 target={lo:.2f}–{hi:.2f}  {status}")
        total += score
    print(f"\n  Combined score: {total:.4f} / 3.0")
    print("=" * 65)


def run_task_detailed(task_id: str) -> dict:
    """
    Run one full episode using the 4-stage pipeline, capturing per-step reasoning.

    Returns dict with:
        task_id, agent, final_score, cumulative_reward, steps_taken, steps: [...]

    Each step contains: step, observation, action, reward, reasoning{pytorch_scores,
    triage_summary, plan_decision, action_rationale}
    """
    client, MODEL = _build_client()

    env = DisasterEnv()
    obs = env.reset(task_id)
    history: list[dict] = []
    total_reward = 0.0
    steps_data: list[dict] = []

    while True:
        obs_dict = obs.model_dump()

        zone_scores = score_zones(obs_dict)
        triage = run_triage(obs_dict, client, MODEL, zone_scores=zone_scores)
        plan = run_planner(obs_dict, triage, zone_scores, client)
        action = get_action(
            obs_dict, triage, history, client, MODEL,
            zone_scores=zone_scores,
            plan=plan,
        )

        result = env.step(action)
        total_reward += result.reward

        # Build human-readable summaries for frontend display
        triage_summary = (
            f"Priority zones: {[p['zone_id'] for p in triage.get('priority_zones', [])[:3]]} | "
            f"False SOS suspects: {triage.get('false_sos_suspects', [])} | "
            f"Deadline alerts: {[d['zone_id'] for d in triage.get('deadline_alerts', [])]}"
        )
        plan_decision = plan.get("critical_decision", "")
        step_plan = plan.get("step_plan", [])
        step1 = next((s for s in step_plan if s.get("step_offset") == 1), None)
        action_rationale = (
            step1.get("reason", f"Execute {action.action}") if step1
            else f"Fallback: {action.action}"
        )

        steps_data.append({
            "step": obs_dict["step_number"],
            "observation": obs_dict,
            "action": action.model_dump(),
            "reward": round(result.reward, 4),
            "reasoning": {
                "pytorch_scores": zone_scores,
                "triage_summary": triage_summary,
                "plan_decision": plan_decision,
                "action_rationale": action_rationale,
            },
        })

        obs = result.observation
        if result.done:
            break

        time.sleep(STEP_DELAY)

    final_state = env.state()
    score = grade_episode(final_state["event_log"], final_state, task_id)

    return {
        "task_id": task_id,
        "agent": "ai_4stage",
        "final_score": round(score, 4),
        "cumulative_reward": round(total_reward, 4),
        "steps_taken": len(steps_data),
        "steps": steps_data,
    }


if __name__ == "__main__":
    results = run_all_parallel()
    print_summary(results)

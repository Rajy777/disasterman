"""
inference_v2.py — Multi-Agent Parallel Disaster Response System v2.

Architecture:
  - 3 tasks run in PARALLEL via ThreadPoolExecutor
  - Each step uses a 2-agent chain: Triage Agent → Action Agent
  - Task 3 uses llama-3.3-70b-versatile (better planning for complex scenarios)
  - Task 1 & 2 use llama-3.1-8b-instant (fast, already proven)

Key improvements over v1:
  - False SOS heuristic: detected before LLM call (zero casualties + zero gap = false)
  - Triage agent provides structured priority list to action agent
  - Rolling history (last 3 exchanges) prevents context bloat on long episodes
  - Model upgrade for Task 3 only

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
from agents.triage_agent import run_triage
from agents.action_agent import get_action

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

# Model selection per task — Task 3 needs deeper reasoning
TASK_MODELS = {
    "task_1": "llama-3.1-8b-instant",
    "task_2": "llama-3.1-8b-instant",
    "task_3": "llama-3.3-70b-versatile",
}

# GPT-4 target ranges for reference
SCORE_TARGETS = {
    "task_1": (0.70, 0.85),
    "task_2": (0.40, 0.60),
    "task_3": (0.20, 0.40),
}


def run_task(task_id: str) -> dict:
    """
    Run one full episode using the 2-agent chain (Triage + Action).
    Returns result dict with grader_score, cumulative_reward, steps_taken.
    """
    model = TASK_MODELS[task_id]
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_KEY)

    env = DisasterEnv()
    obs = env.reset(task_id)
    history: list[dict] = []
    total_reward = 0.0
    step = 0

    print(f"\n{'='*60}")
    print(f"[{task_id.upper()}] Starting | Model: {model}")
    print(f"{'='*60}")

    while True:
        obs_dict = obs.model_dump()

        # Stage 1 — Triage Analysis
        triage = run_triage(obs_dict, client, model)

        # Stage 2 — Action Decision
        action = get_action(obs_dict, triage, history, client, model)

        result = env.step(action)
        total_reward += result.reward
        step += 1

        false_sos = triage.get("false_sos_suspects", [])
        deadlines = triage.get("deadline_alerts", [])
        deadline_str = f" [DEADLINES:{[d['zone_id'] for d in deadlines]}]" if deadlines else ""
        false_str = f" [FALSE_SOS:{false_sos}]" if false_sos else ""

        print(
            f"[{task_id}] S{step:02d} | {action.action:15s} "
            f"to={str(action.to_zone):4s} units={str(action.units):4s} "
            f"res={result.observation.last_action_result:25s} | "
            f"r={result.reward:+.3f} cum={total_reward:+.3f}"
            + deadline_str + false_str
        )

        obs = result.observation
        if result.done:
            break

        # Rate limit buffer: 70B model needs slightly more time
        time.sleep(0.4 if model.endswith("70b-versatile") else 0.2)

    final_state = env.state()
    score = grade_episode(final_state["event_log"], final_state, task_id)
    lo, hi = SCORE_TARGETS[task_id]
    status = "✓ IN TARGET" if lo <= score <= hi else ("▲ ABOVE" if score > hi else "✗ BELOW")

    print(f"\n[{task_id.upper()}] Score: {score:.4f} | Target: {lo:.2f}–{hi:.2f} | {status}")
    print(f"[{task_id.upper()}] Cumulative reward: {total_reward:.4f} | Steps: {step}")

    return {
        "task_id": task_id,
        "grader_score": score,
        "cumulative_reward": total_reward,
        "steps_taken": step,
        "model": model,
    }


def run_all_parallel() -> dict:
    """
    Run all 3 tasks in parallel using ThreadPoolExecutor(max_workers=3).
    Each task runs its own env + agent chain independently.
    """
    if not GROQ_KEY:
        raise EnvironmentError("GROQ_API_KEY environment variable not set.")

    print("\n" + "=" * 60)
    print("DisasterMan v2 — Multi-Agent Parallel Runner")
    print("=" * 60)
    print("  task_1: llama-3.1-8b-instant  (easy, single zone)")
    print("  task_2: llama-3.1-8b-instant  (medium, multi-zone)")
    print("  task_3: llama-3.3-70b-versatile  (hard, cyclone+false SOS)")
    print("  Agent chain: Triage → Action (2 LLM calls per step)")
    print("=" * 60)

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
    print("\n" + "=" * 60)
    print("DISASTERMAN v2 — FINAL SUMMARY")
    print("=" * 60)
    total = 0.0
    for tid in ["task_1", "task_2", "task_3"]:
        r = results.get(tid, {})
        score = r.get("grader_score", 0.0)
        lo, hi = SCORE_TARGETS[tid]
        status = "✓" if lo <= score <= hi else ("▲" if score > hi else "✗")
        model = r.get("model", "?")
        print(f"  {tid}: {score:.4f}  target={lo:.2f}–{hi:.2f}  {status}  [{model}]")
        total += score
    print(f"\n  Combined score: {total:.4f} / 3.0")
    print("=" * 60)


if __name__ == "__main__":
    results = run_all_parallel()
    print_summary(results)

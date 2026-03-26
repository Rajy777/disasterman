"""
colab_disaster_agent.py — ALL-IN-ONE Disaster Management AI Agent
Created for: Hugging Face / Meta AI Hackathon
Logic: Meta Llama 3 via Groq API

INSTRUCTIONS FOR COLAB:
1. Run a cell with: !pip install openai pydantic
2. Set your key: os.environ["GROQ_API_KEY"] = "your_key_here"
3. Run this script.
"""

import os
import json
import time
import math
import copy
import traceback
from typing import Optional, Literal, List, Dict
from pydantic import BaseModel, Field
from openai import OpenAI

# ===========================================================================
# 1. MODELS (models.py)
# ===========================================================================

class ZoneState(BaseModel):
    zone_id: str
    casualties_total: int
    casualties_rescued: int = 0
    casualties_critical: int
    critical_deadline: int
    supply_needed: int
    supply_received: int = 0
    supply_wasted: int = 0
    road_blocked: bool = False
    severity: float = Field(ge=0.0, le=1.0)
    teams_present: int = 0
    is_false_sos: bool = False
    completed: bool = False

    @property
    def casualties_remaining(self) -> int:
        return self.casualties_total - self.casualties_rescued

    @property
    def supply_gap(self) -> int:
        return max(0, self.supply_needed - self.supply_received)

class ZoneObs(BaseModel):
    zone_id: str
    casualties_remaining: int
    supply_gap: int
    severity: float = Field(ge=0.0, le=1.0)
    road_blocked: bool
    teams_present: int
    sos_active: bool

class ResourcesObs(BaseModel):
    teams_available: int
    supply_stock: int
    airlifts_remaining: int
    teams_in_transit: Dict[str, int]

class ObservationModel(BaseModel):
    zones: List[ZoneObs]
    resources: ResourcesObs
    step_number: int
    steps_remaining: int
    weather: Literal["clear", "storm", "flood"]
    last_action_result: Literal["success", "invalid", "blocked", "insufficient_resources", "none"]

class ActionModel(BaseModel):
    action: Literal["deploy_team", "send_supplies", "airlift", "recall_team", "wait"]
    to_zone: Optional[str] = None
    from_zone: Optional[str] = None
    units: Optional[int] = Field(default=None, ge=1)
    type: Optional[Literal["rescue", "supply"]] = None

class RewardBreakdown(BaseModel):
    r_rescue: float = 0.0
    r_supply: float = 0.0
    r_zone_complete: float = 0.0
    r_critical_rescue: float = 0.0
    r_airlift_precision: float = 0.0
    p_critical_deaths: float = 0.0
    p_urgency_decay: float = 0.0
    p_overcommitment: float = 0.0
    p_supply_waste: float = 0.0
    p_false_sos: float = 0.0
    p_wait: float = 0.0
    total: float = 0.0

class StepResult(BaseModel):
    observation: ObservationModel
    reward: float
    done: bool
    info: dict

# ===========================================================================
# 2. REWARD LOGIC (reward.py)
# ===========================================================================

def compute_step_reward(
    zones_before: list[dict],
    zones_after: list[dict],
    action: ActionModel,
    action_result: str,
    resources_before: dict,
    resources_after: dict,
) -> RewardBreakdown:
    bd = RewardBreakdown()
    before = {z["zone_id"]: z for z in zones_before}
    after  = {z["zone_id"]: z for z in zones_after}

    total_casualties = sum(z["casualties_total"] for z in zones_before if not z["is_false_sos"])
    total_critical   = sum(z["casualties_critical"] for z in zones_before if not z["is_false_sos"])
    total_supply_needed = sum(z["supply_needed"] for z in zones_before if not z["is_false_sos"])

    new_rescues = sum(
        max(0, after[zid]["casualties_rescued"] - before[zid]["casualties_rescued"])
        for zid in after if not before[zid]["is_false_sos"]
    )
    max_rescuable = max(1, sum(
        min(before[zid]["casualties_total"] - before[zid]["casualties_rescued"], before[zid]["teams_present"] * 4)
        for zid in before if not before[zid]["is_false_sos"] and before[zid]["teams_present"] > 0
    ))
    bd.r_rescue = 0.40 * min(1.0, new_rescues / max_rescuable) if max_rescuable > 0 else 0.0

    supply_gap_closed = sum(
        max(0, after[zid]["supply_received"] - before[zid]["supply_received"])
        for zid in after if not before[zid]["is_false_sos"]
    )
    total_gap_before = max(1, sum(
        max(0, before[zid]["supply_needed"] - before[zid]["supply_received"])
        for zid in before if not before[zid]["is_false_sos"]
    ))
    bd.r_supply = 0.20 * min(1.0, supply_gap_closed / total_gap_before)

    newly_completed = sum(
        1 for zid in after if after[zid]["completed"] and not before[zid]["completed"]
        and not before[zid]["is_false_sos"]
    )
    bd.r_zone_complete = 0.15 * min(1.0, newly_completed / max(1, len(zones_before)))

    critical_rescues = sum(
        max(0, after[zid]["casualties_rescued"] - before[zid]["casualties_rescued"])
        for zid in after if before[zid]["severity"] >= 0.75 and not before[zid]["is_false_sos"]
    )
    bd.r_critical_rescue = 0.15 * min(1.0, critical_rescues / max(1, total_casualties * 0.3))

    if action.action == "airlift" and action.to_zone:
        zid = action.to_zone
        if zid in before:
            zone = before[zid]
            if zone["road_blocked"] and zone["severity"] >= 0.75:
                bd.r_airlift_precision = 0.10 * 1.0
            elif not zone["road_blocked"]:
                bd.r_airlift_precision = 0.10 * -0.5
            else:
                bd.r_airlift_precision = 0.10 * 0.3

    actual_expired = sum(
        max(0, before[zid]["casualties_critical"] - after[zid]["casualties_critical"])
        for zid in after if not before[zid]["is_false_sos"]
    )
    bd.p_critical_deaths = 0.40 * min(1.0, actual_expired / max(1, total_critical))

    severity_unattended = sum(
        after[zid]["severity"] for zid in after if after[zid]["teams_present"] == 0
        and not after[zid]["completed"] and not after[zid]["is_false_sos"]
    )
    bd.p_urgency_decay = 0.15 * min(1.0, severity_unattended / max(1, len([z for z in zones_before if not z["is_false_sos"]])))

    teams_idle_completed = sum(after[zid]["teams_present"] for zid in after if after[zid]["completed"])
    total_teams_deployed = sum(z["teams_present"] for z in zones_after)
    bd.p_overcommitment = 0.10 * min(1.0, teams_idle_completed / max(1, total_teams_deployed))

    supply_wasted_this_step = sum(max(0, after[zid]["supply_wasted"] - before[zid]["supply_wasted"]) for zid in after)
    bd.p_supply_waste = 0.05 * min(1.0, supply_wasted_this_step / max(1, supply_gap_closed + supply_wasted_this_step))

    bd.p_wait = 0.05 if action.action == "wait" else 0.0
    
    raw = (bd.r_rescue + bd.r_supply + bd.r_zone_complete + bd.r_critical_rescue + bd.r_airlift_precision
           - bd.p_critical_deaths - bd.p_urgency_decay - bd.p_overcommitment - bd.p_supply_waste - bd.p_wait)
    bd.total = max(-1.0, min(1.0, raw))
    return bd

def compute_episode_score(cumulative_reward: float, max_steps: int) -> float:
    normalized = cumulative_reward / max(1, max_steps)
    return (math.tanh(normalized * 2) + 1) / 2

# ===========================================================================
# 3. GRADERS (graders.py)
# ===========================================================================

def _base_scores(final_state: dict) -> dict:
    zones = [z for z in final_state["zones"] if not z["is_false_sos"]]
    total_casualties = sum(z["casualties_total"] for z in zones)
    total_rescued = sum(z["casualties_rescued"] for z in zones)
    total_supply_needed = sum(z["supply_needed"] for z in zones)
    total_supply_received = sum(min(z["supply_received"], z["supply_needed"]) for z in zones)
    total_wasted = sum(z["supply_wasted"] for z in zones)
    total_sent = total_supply_received + total_wasted
    critical_deaths = sum(1 for e in final_state["event_log"] if e["type"] == "critical_expired")
    return {
        "rescue_score": total_rescued / max(1, total_casualties),
        "supply_score": total_supply_received / max(1, total_supply_needed),
        "efficiency_score": 1.0 - (total_wasted / max(1, total_sent)),
        "critical_deaths": critical_deaths,
        "total_casualties": total_casualties,
        "total_rescued": total_rescued,
    }

def grade_task_1(event_log: list[dict], final_state: dict) -> float:
    s = _base_scores(final_state)
    raw = 0.6 * s["rescue_score"] + 0.4 * s["supply_score"]
    if s["rescue_score"] >= 1.0: raw = min(1.0, raw + 0.05)
    return round(max(0.0, min(1.0, raw)), 4)

def grade_task_2(event_log: list[dict], final_state: dict) -> float:
    s = _base_scores(final_state)
    zones = [z for z in final_state["zones"] if not z["is_false_sos"]]
    total_critical = sum(z["casualties_critical"] for z in zones)
    critical_response = 1.0 - (s["critical_deaths"] / max(1, total_critical))
    raw = 0.50 * s["rescue_score"] + 0.30 * max(0.0, critical_response) + 0.20 * s["efficiency_score"]
    return round(max(0.0, min(1.0, raw)), 4)

def grade_task_3(event_log: list[dict], final_state: dict) -> float:
    s = _base_scores(final_state)
    zones = [z for z in final_state["zones"] if not z["is_false_sos"]]
    zone_ids = {z["zone_id"] for z in zones}
    first_response = {}
    for event in event_log:
        if event["type"] in ("deploy_team", "airlift"):
            zid = event.get("to")
            if zid and zid in zone_ids and zid not in first_response:
                first_response[zid] = event["step"]
    response_score = 1.0 - (sum(first_response.values()) / len(first_response) / final_state["max_steps"]) if first_response else 0.0
    airlift_events = [e for e in event_log if e["type"] == "airlift"]
    smart_airlifts = sum(1 for e in airlift_events if e.get("to") in zone_ids)
    airlift_iq = smart_airlifts / max(1, len(airlift_events)) if airlift_events else 1.0
    raw = 0.45 * s["rescue_score"] + 0.25 * response_score + 0.20 * airlift_iq + 0.10 * s["efficiency_score"]
    return round(max(0.0, min(1.0, raw)), 4)

def grade_episode(event_log: list[dict], final_state: dict, task_id: str) -> float:
    graders = {"task_1": grade_task_1, "task_2": grade_task_2, "task_3": grade_task_3}
    return graders[task_id](event_log, final_state)

# ===========================================================================
# 4. TASKS (tasks.py)
# ===========================================================================

TASK_1 = {
    "task_id": "task_1", "max_steps": 10, "rescue_teams": 8, "supply_stock": 200, "airlifts": 0,
    "zones": [{"zone_id": "A", "casualties_total": 30, "casualties_critical": 5, "critical_deadline": 4, "supply_needed": 80, "road_blocked": False, "severity_init": 0.75, "is_false_sos": False}]
}

TASK_2 = {
    "task_id": "task_2", "max_steps": 15, "rescue_teams": 6, "supply_stock": 150, "airlifts": 1,
    "weather_schedule": {8: "storm", 9: "storm", 10: "storm", 11: "clear"}, "storm_blocks": ["D"],
    "zones": [
        {"zone_id": "A", "casualties_total": 20, "casualties_critical": 4, "critical_deadline": 5, "supply_needed": 60, "road_blocked": False, "severity_init": 0.65, "is_false_sos": False},
        {"zone_id": "B", "casualties_total": 35, "casualties_critical": 8, "critical_deadline": 6, "supply_needed": 100, "road_blocked": True, "severity_init": 0.90, "is_false_sos": False},
        {"zone_id": "C", "casualties_total": 25, "casualties_critical": 5, "critical_deadline": 7, "supply_needed": 70, "road_blocked": True, "severity_init": 0.80, "is_false_sos": False, "unblock_at_step": 5},
        {"zone_id": "D", "casualties_total": 15, "casualties_critical": 3, "critical_deadline": 8, "supply_needed": 40, "road_blocked": False, "severity_init": 0.50, "is_false_sos": False},
        {"zone_id": "E", "casualties_total": 25, "casualties_critical": 5, "critical_deadline": 9, "supply_needed": 60, "road_blocked": False, "severity_init": 0.60, "is_false_sos": False},
    ]
}

TASK_3 = {
    "task_id": "task_3", "max_steps": 20, "rescue_teams": 8, "supply_stock": 200, "airlifts": 2,
    "weather_schedule": {3: "storm", 5: "flood", 8: "storm", 9: "clear"}, "storm_blocks": ["D", "F"],
    "dam_break": {"step": 7, "zone": "E", "casualties": 60, "critical": 20, "supply_needed": 100},
    "zones": [
        {"zone_id": "A", "casualties_total": 50, "casualties_critical": 10, "critical_deadline": 5, "supply_needed": 120, "road_blocked": False, "severity_init": 0.80, "is_false_sos": False},
        {"zone_id": "B", "casualties_total": 40, "casualties_critical": 8, "critical_deadline": 6, "supply_needed": 100, "road_blocked": True, "severity_init": 0.85, "is_false_sos": False},
        {"zone_id": "C", "casualties_total": 60, "casualties_critical": 12, "critical_deadline": 7, "supply_needed": 140, "road_blocked": True, "severity_init": 0.90, "is_false_sos": False},
        {"zone_id": "D", "casualties_total": 30, "casualties_critical": 6, "critical_deadline": 8, "supply_needed": 80, "road_blocked": False, "severity_init": 0.70, "is_false_sos": False},
        {"zone_id": "E", "casualties_total": 40, "casualties_critical": 8, "critical_deadline": 10, "supply_needed": 100, "road_blocked": True, "severity_init": 0.75, "is_false_sos": False},
        {"zone_id": "F", "casualties_total": 35, "casualties_critical": 7, "critical_deadline": 9, "supply_needed": 90, "road_blocked": False, "severity_init": 0.65, "is_false_sos": False},
        {"zone_id": "G", "casualties_total": 45, "casualties_critical": 9, "critical_deadline": 11, "supply_needed": 110, "road_blocked": True, "severity_init": 0.85, "is_false_sos": False},
        {"zone_id": "H", "casualties_total": 0, "casualties_critical": 0, "critical_deadline": 99, "supply_needed": 0, "road_blocked": False, "severity_init": 0.0, "is_false_sos": True},
        {"zone_id": "I", "casualties_total": 0, "casualties_critical": 0, "critical_deadline": 99, "supply_needed": 0, "road_blocked": False, "severity_init": 0.0, "is_false_sos": True},
        {"zone_id": "J", "casualties_total": 0, "casualties_critical": 0, "critical_deadline": 99, "supply_needed": 0, "road_blocked": False, "severity_init": 0.0, "is_false_sos": True},
    ]
}

# ===========================================================================
# 5. ENVIRONMENT (environment.py)
# ===========================================================================

class DisasterEnv:
    def __init__(self):
        self._reset_vars()

    def _reset_vars(self):
        self._zones = []; self._teams_available = 0; self._teams_in_transit = {}
        self._supply_stock = 0; self._airlifts_remaining = 0; self._current_step = 0
        self._max_steps = 0; self._weather = "clear"; self._event_log = []
        self._cumulative_reward = 0.0; self._last_action_result = "none"; self._done = False

    def reset(self, task_id: str) -> ObservationModel:
        self._reset_vars()
        cfg = {"task_1": TASK_1, "task_2": TASK_2, "task_3": TASK_3}[task_id]
        self._task_config = cfg; self._max_steps = cfg["max_steps"]
        for z in cfg["zones"]:
            self._zones.append(ZoneState(**z, completed=(z["casualties_total"] == 0 and z["supply_needed"] == 0)))
        self._teams_available = cfg["rescue_teams"]; self._supply_stock = cfg["supply_stock"]
        self._airlifts_remaining = cfg["airlifts"]
        return self._build_observation()

    def step(self, action: ActionModel) -> StepResult:
        z_before = [z.model_dump() for z in self._zones]
        r_before = {"teams": self._teams_available, "supplies": self._supply_stock, "airlifts": self._airlifts_remaining}
        res = self._execute_action(action)
        self._last_action_result = res
        self._advance_world()
        z_after = [z.model_dump() for z in self._zones]
        r_after = {"teams": self._teams_available, "supplies": self._supply_stock, "airlifts": self._airlifts_remaining}
        bd = compute_step_reward(z_before, z_after, action, res, r_before, r_after)
        self._cumulative_reward += bd.total; self._current_step += 1
        self._done = self._current_step >= self._max_steps or all(z.completed for z in self._zones if not z.is_false_sos)
        return StepResult(observation=self._build_observation(), reward=bd.total, done=self._done, info={"cumulative_reward": self._cumulative_reward})

    def _execute_action(self, action: ActionModel) -> str:
        zone = next((z for z in self._zones if z.zone_id == (action.to_zone or action.from_zone)), None)
        if action.action == "wait": return "success"
        if not zone and action.action != "wait": return "invalid"
        
        if action.action == "deploy_team":
            if zone.road_blocked: return "blocked"
            u = action.units or 1
            if self._teams_available < u: return "insufficient_resources"
            self._teams_available -= u; zone.teams_present += u; return "success"
        
        if action.action == "send_supplies":
            if zone.road_blocked: return "blocked"
            u = action.units or 0
            if self._supply_stock < u: return "insufficient_resources"
            self._supply_stock -= u; gap = zone.supply_gap; zone.supply_received += min(u, gap); zone.supply_wasted += max(0, u - gap); return "success"
            
        if action.action == "airlift":
            if self._airlifts_remaining <= 0: return "insufficient_resources"
            self._airlifts_remaining -= 1
            if (action.type or "rescue") == "rescue":
                if self._teams_available < 1: return "insufficient_resources"
                self._teams_available -= 1; zone.teams_present += 1
            else:
                gap = zone.supply_gap; zone.supply_received += min(30, gap); zone.supply_wasted += max(0, 30-gap); self._supply_stock = max(0, self._supply_stock-30)
            return "success"
            
        if action.action == "recall_team":
            u = action.units or 1
            if zone.teams_present < u: return "insufficient_resources"
            zone.teams_present -= u; self._teams_in_transit[zone.zone_id] = self._teams_in_transit.get(zone.zone_id, 0) + u; return "success"
        return "invalid"

    def _advance_world(self):
        for zid, count in self._teams_in_transit.items(): self._teams_available += count
        self._teams_in_transit = {}
        self._weather = self._task_config.get("weather_schedule", {}).get(self._current_step, "clear")
        for z in self._zones:
            if self._weather in ("storm", "flood") and z.zone_id in self._task_config.get("storm_blocks", []): z.road_blocked = True
            if self._task_config.get("dam_break") and self._current_step == self._task_config["dam_break"]["step"] and z.zone_id == self._task_config["dam_break"]["zone"]:
                db = self._task_config["dam_break"]; z.casualties_total += db["casualties"]; z.casualties_critical += db["critical"]; z.supply_needed += db["supply_needed"]; z.completed = False
            if z.teams_present > 0 and not z.is_false_sos: z.casualties_rescued += min(z.casualties_remaining, z.teams_present * 4)
            if not z.is_false_sos and self._current_step >= z.critical_deadline and z.teams_present == 0: z.casualties_critical = 0
            z.completed = z.casualties_rescued >= z.casualties_total and z.supply_received >= z.supply_needed
            if not z.is_false_sos and not z.completed:
                rem = z.casualties_remaining / max(1, z.casualties_total); crit = z.casualties_critical / max(1, z.casualties_total)
                z.severity = min(1.0, 0.5 * rem + 0.3 * crit + 0.2 * (self._current_step / self._max_steps))

    def _build_observation(self) -> ObservationModel:
        zobs = [ZoneObs(zone_id=z.zone_id, casualties_remaining=z.casualties_remaining, supply_gap=z.supply_gap, severity=round(z.severity, 3), road_blocked=z.road_blocked, teams_present=z.teams_present, sos_active=(z.casualties_remaining > 0 or z.is_false_sos)) for z in self._zones]
        return ObservationModel(zones=zobs, resources=ResourcesObs(teams_available=self._teams_available, supply_stock=self._supply_stock, airlifts_remaining=self._airlifts_remaining, teams_in_transit=self._teams_in_transit), step_number=self._current_step, steps_remaining=self._max_steps - self._current_step, weather=self._weather, last_action_result=self._last_action_result)

    def state(self) -> dict:
        return {"zones": [z.model_dump() for z in self._zones], "max_steps": self._max_steps, "event_log": []} # Simplified for colab

# ===========================================================================
# 6. INFERENCE (inference.py)
# ===========================================================================

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY", ""))

SYSTEM_PROMPT = "You are a disaster relief coordinator. Goal: Maximize rescues, close supply gaps, avoid false SOS. Respond with JSON ONLY. Actions: deploy_team, send_supplies, airlift, recall_team, wait."

def obs_to_prompt(obs: dict) -> str:
    p = f"Step {obs['step_number']} | Weather: {obs['weather']} | Res: {obs['resources']}\nZones:\n"
    for z in obs["zones"]: p += f"- {z['zone_id']}: {z['casualties_remaining']} rem, {z['supply_gap']} gap, {z['severity']} sev, {z['teams_present']} teams\n"
    return p

def get_agent_action(obs: dict, history: list) -> ActionModel:
    history.append({"role": "user", "content": obs_to_prompt(obs)})
    resp = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history, temperature=0.1, response_format={"type": "json_object"})
    raw = resp.choices[0].message.content.strip(); history.append({"role": "assistant", "content": raw})
    data = json.loads(raw)
    if isinstance(data.get("to_zone"), str) and data["to_zone"].startswith("Zone "): data["to_zone"] = data["to_zone"][5:]
    return ActionModel(**data)

def run_task(task_id: str):
    env = DisasterEnv(); obs = env.reset(task_id); history = []; total_reward = 0.0; step = 0
    print(f"\n--- RUNNING {task_id} ---")
    while True:
        action = get_agent_action(obs.model_dump(), history)
        res = env.step(action); total_reward += res.reward; step += 1
        print(f"S{step:02} | {action.action:12} | R:{res.reward:+.3f} | C:{total_reward:+.3f}")
        obs = res.observation
        if res.done: break
    print(f"Final Reward: {total_reward:.4f}")

if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: Please set os.environ['GROQ_API_KEY'] first.")
    else:
        for t in ["task_1", "task_2", "task_3"]:
            try: run_task(t)
            except Exception as e: print(f"Error in {t}: {e}")

"""
models.py — Pydantic contracts for the Disaster Relief OpenEnv environment.
Owner: Krish Potanwar
FROZEN after first push. Do not rename fields without team sync.
"""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Zone-level models
# ---------------------------------------------------------------------------

class ZoneState(BaseModel):
    """Full internal state of one zone. Returned by state() only — NOT observation."""
    zone_id: str
    casualties_total: int
    casualties_rescued: int = 0
    casualties_critical: int          # HIDDEN from agent — only severity exposed
    critical_deadline: int            # step by which critical casualties expire
    supply_needed: int
    supply_received: int = 0
    supply_wasted: int = 0
    road_blocked: bool = False
    severity: float = Field(ge=0.0, le=1.0)   # computed each step
    teams_present: int = 0
    is_false_sos: bool = False        # HIDDEN from agent
    completed: bool = False

    @property
    def casualties_remaining(self) -> int:
        return self.casualties_total - self.casualties_rescued

    @property
    def supply_gap(self) -> int:
        return max(0, self.supply_needed - self.supply_received)


class ZoneObs(BaseModel):
    """Filtered zone view exposed to the agent. No hidden fields."""
    zone_id: str
    casualties_remaining: int
    supply_gap: int
    severity: float = Field(ge=0.0, le=1.0)
    road_blocked: bool
    teams_present: int
    sos_active: bool                  # True for real AND false SOS zones — agent can't tell


# ---------------------------------------------------------------------------
# Observation model — what the agent sees each step
# ---------------------------------------------------------------------------

class ResourcesObs(BaseModel):
    teams_available: int
    supply_stock: int
    airlifts_remaining: int
    teams_in_transit: dict[str, int]  # {"zone_id": count} — returning teams, not yet at HQ


class ObservationModel(BaseModel):
    zones: list[ZoneObs]
    resources: ResourcesObs
    step_number: int
    steps_remaining: int
    weather: Literal["clear", "storm", "flood"]
    last_action_result: Literal["success", "invalid", "blocked", "insufficient_resources", "none"]


# ---------------------------------------------------------------------------
# Action model — what the agent sends
# ---------------------------------------------------------------------------

class ActionModel(BaseModel):
    action: Literal["deploy_team", "send_supplies", "airlift", "recall_team", "wait"]
    to_zone: Optional[str] = None
    from_zone: Optional[str] = None
    units: Optional[int] = Field(default=None, ge=1)
    type: Optional[Literal["rescue", "supply"]] = None   # for airlift only


# ---------------------------------------------------------------------------
# Reward model — structured breakdown returned in info dict
# ---------------------------------------------------------------------------

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
    total: float = 0.0               # clamped to [−1.0, 1.0]


# ---------------------------------------------------------------------------
# Step result — returned from environment.step()
# ---------------------------------------------------------------------------

class StepResult(BaseModel):
    observation: ObservationModel
    reward: float                    # clamped step reward
    done: bool
    info: dict                       # includes reward_breakdown, event_log tail
"""
demo_models.py — Pydantic contracts for the Bengaluru live disaster demo.

These models are intentionally separate from the benchmark task contracts so
the reviewer-facing demo can evolve without mutating the official task schema.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from models import ActionModel, ObservationModel


LatLng = tuple[float, float]


class DemoScenarioSummary(BaseModel):
    scenario_id: str
    title: str
    disaster_type: str
    narrative: str
    duration_steps: int
    default_agent: Literal["ai_4stage", "greedy", "random"] = "ai_4stage"
    tags: list[str]
    center: LatLng
    zoom: float


class DemoLocation(BaseModel):
    node_id: str
    label: str
    area: str
    coordinates: LatLng
    kind: Literal["hq", "incident", "support", "false_alert", "medical", "staging"]
    description: str = ""
    zone_id: Optional[str] = None


class DemoRoute(BaseModel):
    route_id: str
    label: str
    mode: Literal["road", "air"]
    from_node: str
    to_node: str
    path: list[LatLng]
    zone_id: Optional[str] = None


class DemoMapOverlay(BaseModel):
    overlay_id: str
    label: str
    kind: Literal["flood_zone", "fire_zone", "collapse_zone", "blocked_corridor", "false_alert", "support_zone"]
    geometry: Literal["polygon", "polyline", "circle"]
    coordinates: list[LatLng]
    radius_m: Optional[int] = None
    severity: Literal["low", "medium", "high"] = "medium"
    active: bool = True
    note: str = ""
    zone_id: Optional[str] = None


class DemoScenarioDetail(DemoScenarioSummary):
    bounds: list[LatLng]
    hq_node_id: str
    allowed_agents: list[Literal["ai_4stage", "greedy", "random"]]
    locations: list[DemoLocation]
    routes: list[DemoRoute]
    overlays: list[DemoMapOverlay]


class DemoResourcePosition(BaseModel):
    resource_id: str
    kind: Literal["hq", "team", "supply", "airlift"]
    label: str
    coordinates: LatLng
    count: int = 1
    status: Literal["ready", "deployed", "support", "airborne"]
    assigned_zone: Optional[str] = None
    note: str = ""


class DemoResourceMovement(BaseModel):
    movement_id: str
    kind: Literal["team", "supply", "airlift"]
    label: str
    route_id: str
    path: list[LatLng]
    from_node: str
    to_node: str
    units: int = 1
    progress: float = 1.0
    color: str = "#38bdf8"
    action: str
    note: str = ""


class DemoMapState(BaseModel):
    center: LatLng
    zoom: float
    bounds: list[LatLng]
    overlays: list[DemoMapOverlay]
    resource_positions: list[DemoResourcePosition]
    recent_movements: list[DemoResourceMovement]
    action_target: Optional[str] = None
    step_label: str = ""


class DemoStep(BaseModel):
    step: int
    observation: ObservationModel
    action: ActionModel
    reward: float
    reasoning: dict
    map_state: DemoMapState


class DemoRunResult(BaseModel):
    scenario: DemoScenarioDetail
    agent: Literal["ai_4stage", "greedy", "random"]
    model: Optional[str] = None
    final_score: Optional[float] = None
    cumulative_reward: float
    steps_taken: int
    steps: list[DemoStep]
    note: Optional[str] = None


class DemoRunRequest(BaseModel):
    agent: Literal["ai_4stage", "greedy", "random"] = "ai_4stage"


class DemoStreamMetaEvent(BaseModel):
    scenario: DemoScenarioDetail
    scenario_id: str
    agent: Literal["ai_4stage", "greedy", "random"]
    model: str

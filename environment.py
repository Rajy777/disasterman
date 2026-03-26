"""
environment.py — Core DisasterEnv class. Implements OpenEnv spec.
Owner: Tushar Sharma
Imports: models.py (Krish), reward.py (Krish), tasks.py (Tushar)
"""

from __future__ import annotations
import copy
from typing import Optional

from models import (
    ZoneState, ZoneObs, ObservationModel, ActionModel,
    RewardBreakdown, StepResult, ResourcesObs
)
from reward import compute_step_reward
from tasks import ALL_TASKS


class DisasterEnv:
    """
    OpenEnv-compliant Disaster Relief Coordination environment.
    One instance = one session. Call reset() to start a new episode.
    """

    def __init__(self):
        self._zones: list[ZoneState] = []
        self._teams_available: int = 0
        self._teams_in_transit: dict[str, int] = {}
        self._supply_stock: int = 0
        self._airlifts_remaining: int = 0
        self._current_step: int = 0
        self._max_steps: int = 0
        self._weather: str = "clear"
        self._event_log: list[dict] = []
        self._cumulative_reward: float = 0.0
        self._task_config: dict = {}
        self._last_action_result: str = "none"
        self._done: bool = False

    # ------------------------------------------------------------------
    # OpenEnv API
    # ------------------------------------------------------------------

    def reset(self, task_id: str = "task_1") -> ObservationModel:
        """Initialize environment for a given task. Returns first observation."""
        cfg = ALL_TASKS[task_id]
        self._task_config = cfg
        self._current_step = 0
        self._max_steps = cfg["max_steps"]
        self._weather = "clear"
        self._event_log = []
        self._cumulative_reward = 0.0
        self._last_action_result = "none"
        self._done = False
        self._teams_in_transit = {}

        # Build zone states
        self._zones = []
        for z in cfg["zones"]:
            self._zones.append(ZoneState(
                zone_id=z["zone_id"],
                casualties_total=z["casualties_total"],
                casualties_rescued=0,
                casualties_critical=z["casualties_critical"],
                critical_deadline=z["critical_deadline"],
                supply_needed=z["supply_needed"],
                supply_received=0,
                supply_wasted=0,
                road_blocked=z["road_blocked"],
                severity=z["severity_init"],
                teams_present=0,
                is_false_sos=z["is_false_sos"],
                completed=(z["casualties_total"] == 0 and z["supply_needed"] == 0),
            ))

        # Load resources
        res = cfg["resources"]
        self._teams_available = res["rescue_teams"]
        self._supply_stock = res["supply_stock"]
        self._airlifts_remaining = res["airlifts"]

        self._log("episode_start", {"task_id": task_id})
        return self._build_observation()

    def step(self, action: ActionModel) -> StepResult:
        """
        Process one action, advance world state by one timestep.
        Returns (observation, reward, done, info).
        """
        if self._done:
            raise RuntimeError("Episode is done. Call reset() to start a new episode.")

        # Snapshot state before action for reward computation
        zones_before = [z.model_dump() for z in self._zones]
        resources_before = self._snapshot_resources()

        # --- Execute action ---
        action_result = self._execute_action(action)
        self._last_action_result = action_result

        # --- Advance world state ---
        self._advance_world()

        # --- Snapshot after ---
        zones_after = [z.model_dump() for z in self._zones]
        resources_after = self._snapshot_resources()

        # --- Compute reward ---
        breakdown = compute_step_reward(
            zones_before, zones_after,
            action, action_result,
            resources_before, resources_after,
        )
        self._cumulative_reward += breakdown.total

        # --- Check done ---
        self._current_step += 1
        all_complete = all(z.completed for z in self._zones if not z.is_false_sos)
        self._done = self._current_step >= self._max_steps or all_complete

        self._log("step", {
            "step": self._current_step,
            "action": action.model_dump(),
            "result": action_result,
            "reward": breakdown.total,
            "cumulative": self._cumulative_reward,
        })

        obs = self._build_observation()
        return StepResult(
            observation=obs,
            reward=breakdown.total,
            done=self._done,
            info={
                "reward_breakdown": breakdown.model_dump(),
                "cumulative_reward": self._cumulative_reward,
                "step": self._current_step,
                "event_log_tail": self._event_log[-3:],
            }
        )

    def state(self) -> dict:
        """Full internal state snapshot. Includes hidden fields. Used by graders."""
        return {
            "zones": [z.model_dump() for z in self._zones],
            "teams_available": self._teams_available,
            "teams_in_transit": self._teams_in_transit,
            "supply_stock": self._supply_stock,
            "airlifts_remaining": self._airlifts_remaining,
            "current_step": self._current_step,
            "max_steps": self._max_steps,
            "weather": self._weather,
            "cumulative_reward": self._cumulative_reward,
            "done": self._done,
            "event_log": self._event_log,
            "task_id": self._task_config.get("task_id", "unknown"),
        }

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def _execute_action(self, action: ActionModel) -> str:
        """Execute the action, mutate state, return result string."""

        if action.action == "deploy_team":
            return self._deploy_team(action)

        elif action.action == "send_supplies":
            return self._send_supplies(action)

        elif action.action == "airlift":
            return self._airlift(action)

        elif action.action == "recall_team":
            return self._recall_team(action)

        elif action.action == "wait":
            return "success"

        return "invalid"

    def _deploy_team(self, action: ActionModel) -> str:
        zone = self._get_zone(action.to_zone)
        if zone is None:
            return "invalid"
        if zone.road_blocked:
            return "blocked"
        units = action.units or 1
        if self._teams_available < units:
            return "insufficient_resources"
        self._teams_available -= units
        zone.teams_present += units
        self._log("deploy_team", {"to": action.to_zone, "units": units})
        return "success"

    def _send_supplies(self, action: ActionModel) -> str:
        zone = self._get_zone(action.to_zone)
        if zone is None:
            return "invalid"
        if zone.road_blocked:
            return "blocked"
        units = action.units or 0
        if self._supply_stock < units:
            return "insufficient_resources"
        self._supply_stock -= units
        # Cap at supply_needed — remainder is waste
        useful = min(units, zone.supply_gap)
        wasted = units - useful
        zone.supply_received += useful
        zone.supply_wasted += wasted
        self._log("send_supplies", {"to": action.to_zone, "units": units, "wasted": wasted})
        return "success"

    def _airlift(self, action: ActionModel) -> str:
        if self._airlifts_remaining <= 0:
            return "insufficient_resources"
        zone = self._get_zone(action.to_zone)
        if zone is None:
            return "invalid"
        self._airlifts_remaining -= 1
        airlift_type = action.type or "rescue"
        if airlift_type == "rescue":
            self._teams_available -= 1
            zone.teams_present += 1
        else:
            # Supply airlift: deliver 30 units regardless of road
            useful = min(30, zone.supply_gap)
            zone.supply_received += useful
            zone.supply_wasted += (30 - useful)
            self._supply_stock = max(0, self._supply_stock - 30)
        self._log("airlift", {"to": action.to_zone, "type": airlift_type})
        return "success"

    def _recall_team(self, action: ActionModel) -> str:
        zone = self._get_zone(action.from_zone)
        if zone is None:
            return "invalid"
        units = action.units or 1
        if zone.teams_present < units:
            return "insufficient_resources"
        zone.teams_present -= units
        # 1-step transit delay before teams become available
        zid = action.from_zone
        self._teams_in_transit[zid] = self._teams_in_transit.get(zid, 0) + units
        self._log("recall_team", {"from": action.from_zone, "units": units})
        return "success"

    # ------------------------------------------------------------------
    # World state advancement (called each step after action)
    # ------------------------------------------------------------------

    def _advance_world(self):
        """Advance time: rescue progress, supply updates, events, severity recalc."""
        cfg = self._task_config
        step = self._current_step  # before increment

        # --- Resolve teams in transit ---
        arrived = dict(self._teams_in_transit)
        self._teams_in_transit = {}
        for _, count in arrived.items():
            self._teams_available += count

        # --- Weather events ---
        weather_schedule = cfg.get("weather_schedule", {})
        self._weather = weather_schedule.get(step, "clear")

        # Apply storm road blocks
        storm_blocks = cfg.get("storm_blocks", [])
        for z in self._zones:
            if self._weather in ("storm", "flood") and z.zone_id in storm_blocks:
                z.road_blocked = True
            elif self._weather == "clear" and z.zone_id in storm_blocks:
                # Restore based on original config
                original = next((oz for oz in cfg["zones"] if oz["zone_id"] == z.zone_id), None)
                if original:
                    z.road_blocked = original["road_blocked"]

        # Unblock zones at scheduled steps
        for zone_cfg in cfg["zones"]:
            if zone_cfg.get("unblock_at_step") == step:
                zone = self._get_zone(zone_cfg["zone_id"])
                if zone:
                    zone.road_blocked = False

        # --- Dam break event ---
        dam = cfg.get("dam_break")
        if dam and step == dam["step"]:
            zone = self._get_zone(dam["zone"])
            if zone:
                zone.casualties_total += dam["casualties"]
                zone.casualties_critical += dam["critical"]
                zone.supply_needed += dam["supply_needed"]
                zone.severity = min(1.0, zone.severity + 0.3)
                zone.completed = False
                self._log("dam_break", {"zone": dam["zone"], "added_casualties": dam["casualties"]})

        # --- Rescue progress ---
        rescue_rate = cfg.get("rescue_rate_per_team", 4)
        for zone in self._zones:
            if zone.teams_present > 0 and not zone.is_false_sos:
                rescued_this_step = min(
                    zone.casualties_remaining,
                    zone.teams_present * rescue_rate,
                )
                zone.casualties_rescued += rescued_this_step

        # --- Critical casualty expiry ---
        for zone in self._zones:
            if not zone.is_false_sos and step >= zone.critical_deadline:
                if zone.casualties_critical > 0 and zone.teams_present == 0:
                    # Critical casualties expire — they count as unrescued deaths
                    zone.casualties_critical = 0
                    self._log("critical_expired", {"zone": zone.zone_id, "step": step})

        # --- Zone completion check ---
        for zone in self._zones:
            if not zone.is_false_sos:
                zone.completed = (
                    zone.casualties_rescued >= zone.casualties_total and
                    zone.supply_received >= zone.supply_needed
                )

        # --- Severity recalculation ---
        for zone in self._zones:
            if zone.is_false_sos:
                # Keep original high severity to trick the agent
                continue
            if zone.completed:
                zone.severity = 0.0
                continue
            remaining_ratio = zone.casualties_remaining / max(1, zone.casualties_total)
            time_pressure = (self._max_steps - step) / max(1, self._max_steps)
            critical_factor = zone.casualties_critical / max(1, zone.casualties_total)
            zone.severity = min(1.0, (
                0.5 * remaining_ratio +
                0.3 * critical_factor +
                0.2 * (1 - time_pressure)
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_observation(self) -> ObservationModel:
        false_sos_zones = self._task_config.get("false_sos_zones", [])
        zone_obs = []
        for z in self._zones:
            zone_obs.append(ZoneObs(
                zone_id=z.zone_id,
                casualties_remaining=z.casualties_remaining,
                supply_gap=z.supply_gap,
                severity=round(z.severity, 3),
                road_blocked=z.road_blocked,
                teams_present=z.teams_present,
                sos_active=(z.casualties_remaining > 0 or z.is_false_sos),
            ))
        return ObservationModel(
            zones=zone_obs,
            resources=ResourcesObs(
                teams_available=self._teams_available,
                supply_stock=self._supply_stock,
                airlifts_remaining=self._airlifts_remaining,
                teams_in_transit=dict(self._teams_in_transit),
            ),
            step_number=self._current_step,
            steps_remaining=self._max_steps - self._current_step,
            weather=self._weather,
            last_action_result=self._last_action_result,
        )

    def _get_zone(self, zone_id: Optional[str]) -> Optional[ZoneState]:
        if zone_id is None:
            return None
        for z in self._zones:
            if z.zone_id == zone_id:
                return z
        return None

    def _snapshot_resources(self) -> dict:
        return {
            "teams_available": self._teams_available,
            "supply_stock": self._supply_stock,
            "airlifts_remaining": self._airlifts_remaining,
        }

    def _log(self, event_type: str, data: dict):
        self._event_log.append({"type": event_type, "step": self._current_step, **data})
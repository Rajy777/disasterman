"""
zone_scorer.py — PyTorch Zone Priority Scoring Network.

A compact MLP that scores zones by rescue priority using 6 hand-crafted features.
No GPU required. Inference < 1ms on CPU. Domain-knowledge initialization means
the model is useful out-of-the-box even without pre-trained weights.

Run `python agents/train_zone_scorer.py` to generate zone_scorer_weights.pt
from synthetic optimal-trajectory data and save significantly better weights.

Architecture: Linear(6→16) → ReLU → Linear(16→1) → Sigmoid
Features: severity, casualty_ratio, supply_ratio, road_blocked, unattended, time_pressure
"""

from __future__ import annotations
import os
import torch
import torch.nn as nn

_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "zone_scorer_weights.pt")
_model: "ZoneScorerNet | None" = None


class ZoneScorerNet(nn.Module):
    """
    Tiny MLP: 6 zone features → priority score in [0, 1].
    Higher score = more urgent zone to attend first.
    """
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(6, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ---------------------------------------------------------------------------
# Domain-knowledge weight initialization
# ---------------------------------------------------------------------------

def _apply_domain_init(model: ZoneScorerNet) -> None:
    """
    Initialize weights to encode domain expertise before any training.
    Feature order: [severity, cas_ratio, supply_ratio, road_blocked, unattended, time_pressure]
    A model with these weights already beats a random baseline significantly.
    """
    with torch.no_grad():
        w1 = torch.zeros(16, 6)
        # Neuron 0 — urgency composite (severity + unattended + time pressure dominate)
        w1[0] = torch.tensor([2.5, 1.2, 0.4, 0.2, 2.2, 1.8])
        # Neuron 1 — casualty focus
        w1[1] = torch.tensor([1.0, 2.5, 0.3, 0.0, 1.2, 0.8])
        # Neuron 2 — supply focus
        w1[2] = torch.tensor([0.4, 0.4, 2.5, 0.0, 0.5, 0.4])
        # Neuron 3 — deadline / time pressure (severity + time)
        w1[3] = torch.tensor([1.8, 0.8, 0.6, 0.3, 1.8, 2.5])
        # Neuron 4 — blocked penalty (blocked zone needs airlift, lower ground priority)
        w1[4] = torch.tensor([1.0, 0.8, 0.5, -1.5, 1.0, 1.0])
        # Noise neurons for generalization
        w1[5:] = torch.randn(11, 6) * 0.25
        model.net[0].weight.copy_(w1)
        model.net[0].bias.fill_(0.0)

        w2 = torch.zeros(1, 16)
        w2[0, 0] = 1.6   # urgency
        w2[0, 1] = 1.3   # casualty
        w2[0, 2] = 0.9   # supply
        w2[0, 3] = 1.5   # deadline
        w2[0, 4] = 0.7   # blocked
        w2[0, 5:] = torch.randn(11) * 0.1
        model.net[2].weight.copy_(w2)
        model.net[2].bias.fill_(-1.2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _load_model() -> ZoneScorerNet:
    """Load (or initialize) the zone scorer model. Cached as module-level singleton."""
    global _model
    if _model is not None:
        return _model

    m = ZoneScorerNet()
    if os.path.exists(_WEIGHTS_PATH):
        state = torch.load(_WEIGHTS_PATH, map_location="cpu", weights_only=True)
        m.load_state_dict(state)
    else:
        _apply_domain_init(m)

    m.eval()
    _model = m
    return m


def score_zones(obs: dict) -> list[dict]:
    """
    Score all zones in the observation using ZoneScorerNet.

    Returns a list sorted by priority score descending:
        [{"zone_id": str, "score": float, "is_false_sos_suspect": bool}, ...]

    False SOS zones (sos_active=True, casualties=0, supply_gap=0) get score=0.0
    and are flagged so the pipeline never wastes resources on them.
    """
    model = _load_model()

    total_casualties = max(1, sum(z["casualties_remaining"] for z in obs["zones"]))
    total_supply_gap = max(1, sum(z["supply_gap"] for z in obs["zones"]))
    steps_remaining = max(1, obs.get("steps_remaining", 10))

    results: list[dict] = []
    with torch.no_grad():
        for z in obs["zones"]:
            is_false_sos = (
                z.get("sos_active", False)
                and z["casualties_remaining"] == 0
                and z["supply_gap"] == 0
            )
            if is_false_sos:
                results.append({
                    "zone_id": z["zone_id"],
                    "score": 0.0,
                    "is_false_sos_suspect": True,
                })
                continue

            # 6-feature vector
            features = torch.tensor([
                float(z["severity"]),
                z["casualties_remaining"] / total_casualties,
                z["supply_gap"] / total_supply_gap,
                1.0 if z["road_blocked"] else 0.0,
                1.0 if z["teams_present"] == 0 else 0.0,
                1.0 - (steps_remaining / 20.0),   # time pressure (20 = max steps any task)
            ], dtype=torch.float32)

            score = model(features.unsqueeze(0)).squeeze().item()
            results.append({
                "zone_id": z["zone_id"],
                "score": round(score, 4),
                "is_false_sos_suspect": False,
            })

    return sorted(results, key=lambda x: x["score"], reverse=True)

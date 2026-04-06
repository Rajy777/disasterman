"""
train_zone_scorer.py — Offline training for ZoneScorerNet.

Generates 50,000 synthetic (features, label) pairs from domain-knowledge rules,
then trains the MLP with MSE loss for 200 epochs. Saves weights to zone_scorer_weights.pt.

Run: python agents/train_zone_scorer.py
Time: ~8 seconds on CPU.

Label derivation (ground-truth priority score for a zone):
    priority = 0.35 * severity
             + 0.25 * casualty_ratio
             + 0.10 * supply_ratio
             + 0.15 * unattended       (no teams = much more urgent)
             + 0.15 * time_pressure
             - 0.05 * road_blocked     (needs airlift, not ground priority)
    priority = clamp(priority + noise, 0, 1)
"""

from __future__ import annotations
import os
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# Add parent to path so we can import ZoneScorerNet
import sys
sys.path.insert(0, os.path.dirname(__file__))
from zone_scorer import ZoneScorerNet, _WEIGHTS_PATH


def generate_training_data(n: int = 50_000) -> tuple[torch.Tensor, torch.Tensor]:
    """Generate synthetic zone feature vectors and their optimal priority labels."""
    torch.manual_seed(42)

    # Random feature matrix: [severity, cas_ratio, supply_ratio, blocked, unattended, time_pressure]
    X = torch.zeros(n, 6)
    X[:, 0] = torch.rand(n)                          # severity in [0, 1]
    X[:, 1] = torch.rand(n)                          # casualty ratio in [0, 1]
    X[:, 2] = torch.rand(n)                          # supply ratio in [0, 1]
    X[:, 3] = (torch.rand(n) > 0.6).float()          # road_blocked: ~40% chance
    X[:, 4] = (torch.rand(n) > 0.5).float()          # unattended: 50% chance
    X[:, 5] = torch.rand(n)                          # time_pressure in [0, 1]

    # Ground-truth labels from domain-knowledge formula
    y = (
        0.35 * X[:, 0]
        + 0.25 * X[:, 1]
        + 0.10 * X[:, 2]
        + 0.15 * X[:, 4]
        + 0.15 * X[:, 5]
        - 0.05 * X[:, 3]
    )

    # Add small noise so model learns to generalize
    y = y + torch.randn(n) * 0.03
    y = y.clamp(0.0, 1.0).unsqueeze(1)

    return X, y


def train(epochs: int = 200, batch_size: int = 512, lr: float = 1e-3) -> None:
    X, y = generate_training_data()
    dataset = TensorDataset(X, y)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = ZoneScorerNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(xb)

        if epoch % 50 == 0:
            avg = total_loss / len(dataset)
            print(f"  Epoch {epoch:3d}/{epochs} | MSE loss: {avg:.6f}")

    torch.save(model.state_dict(), _WEIGHTS_PATH)
    print(f"\nWeights saved → {_WEIGHTS_PATH}")

    # Quick sanity check
    model.eval()
    with torch.no_grad():
        # High severity, unattended, high time pressure → should score high
        high_prio = torch.tensor([[0.9, 0.8, 0.7, 0.0, 1.0, 0.9]])
        # Low severity, attended, zero casualties → false SOS territory
        low_prio  = torch.tensor([[0.0, 0.0, 0.0, 0.0, 0.0, 0.1]])
        print(f"\nSanity check:")
        print(f"  High-priority zone score : {model(high_prio).item():.4f}  (expect > 0.7)")
        print(f"  Low/false SOS zone score : {model(low_prio).item():.4f}   (expect < 0.3)")


if __name__ == "__main__":
    print("Training ZoneScorerNet on synthetic data...")
    train()
    print("Done.")

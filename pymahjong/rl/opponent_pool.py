"""Opponent snapshot pool for self-play training.

Maintains a bounded ring buffer of historical policy snapshots so the
learner can play against past versions of itself in addition to the
current parameters.  This is the standard trick used in Suphx /
AlphaStar / OpenAI Five to prevent intransitive cycling (a > b > c > a)
in self-play.

Snapshots may live in memory only (default) or be checkpointed to disk.

Usage::

    pool = OpponentPool(capacity=20)
    # ...after each PPO update...
    pool.add_snapshot(model, step=total_steps)
    # ...when assigning opponents for an episode...
    frozen_state = pool.sample()
    opp_model = build_model()
    opp_model.load_state_dict(frozen_state)
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import torch
except Exception:  # noqa: BLE001  -- torch optional
    torch = None  # type: ignore


@dataclass
class Snapshot:
    """A single frozen policy snapshot.

    Attributes:
        step: training step at which the snapshot was taken.
        state_dict: model state dict (CPU tensors, kept lightweight).
        win_rate: rolling Bayesian estimate of the *learner's* win-rate
            against this snapshot.  Used for prioritized sampling (PFSP).
            ``win_rate = (wins + alpha) / (games + 2 * alpha)``.
        games: total games played against this snapshot.
        wins: learner wins (1st place finishes) against this snapshot.
    """

    step: int
    state_dict: Dict[str, Any]
    games: int = 0
    wins: float = 0.0
    win_rate: float = 0.5

    def update_winrate(self, learner_won: bool, alpha: float = 1.0) -> None:
        self.games += 1
        self.wins += 1.0 if learner_won else 0.0
        self.win_rate = (self.wins + alpha) / (self.games + 2.0 * alpha)


class OpponentPool:
    """Bounded ring-buffer of historical snapshots with optional PFSP sampling.

    Args:
        capacity: max number of snapshots retained.  When full, the
            oldest snapshot is evicted.
        sampling: one of:

            * ``"uniform"`` — sample any snapshot with equal probability.
            * ``"latest"`` — always sample the newest snapshot.
            * ``"pfsp"`` — prioritized fictitious self-play: probability
              ∝ ``f(p_win) = (1 - p_win) ** pfsp_p`` (encourages playing
              opponents the learner *can't* beat yet).
        pfsp_p: exponent for the PFSP weighting (default 2.0).  Higher
            values bias more aggressively toward hard opponents.
        seed: optional RNG seed.
        save_dir: optional directory for persisting snapshots to disk.
            If set, each :meth:`add_snapshot` also writes
            ``snapshot_<step>.pt`` and :meth:`save`/:meth:`load` work
            against that directory.
    """

    def __init__(
        self,
        capacity: int = 20,
        sampling: str = "pfsp",
        pfsp_p: float = 2.0,
        seed: Optional[int] = None,
        save_dir: Optional[str] = None,
    ):
        if sampling not in {"uniform", "latest", "pfsp"}:
            raise ValueError(f"Unknown sampling strategy: {sampling!r}")
        self.capacity = int(capacity)
        self.sampling = sampling
        self.pfsp_p = float(pfsp_p)
        self.snapshots: List[Snapshot] = []
        self._rng = random.Random(seed)
        self.save_dir = save_dir
        if save_dir is not None:
            os.makedirs(save_dir, exist_ok=True)

    # ------------------------------------------------------------------ size

    def __len__(self) -> int:
        return len(self.snapshots)

    def is_empty(self) -> bool:
        return not self.snapshots

    # ------------------------------------------------------------------ insert

    def add_snapshot(self, model, step: int) -> Snapshot:
        """Snapshot *model*'s current parameters into the pool.

        The model is moved to CPU and detached before storing so the
        snapshot doesn't pin GPU memory or accidentally back-prop later.
        """
        if torch is None:
            raise RuntimeError("torch is required for OpponentPool.add_snapshot")
        cpu_state = {k: v.detach().to("cpu").clone() for k, v in model.state_dict().items()}
        snap = Snapshot(step=step, state_dict=cpu_state)
        self.snapshots.append(snap)
        if len(self.snapshots) > self.capacity:
            self.snapshots.pop(0)
        if self.save_dir is not None:
            path = os.path.join(self.save_dir, f"snapshot_{step:09d}.pt")
            torch.save({"step": step, "state_dict": cpu_state}, path)
        return snap

    # ------------------------------------------------------------------ sample

    def sample(self) -> Optional[Snapshot]:
        """Return a snapshot per the configured strategy (or ``None`` if empty)."""
        if not self.snapshots:
            return None
        if self.sampling == "latest" or len(self.snapshots) == 1:
            return self.snapshots[-1]
        if self.sampling == "uniform":
            return self._rng.choice(self.snapshots)
        # PFSP: weight by (1 - learner_winrate) ^ p.
        weights = [(1.0 - s.win_rate) ** self.pfsp_p + 1e-6 for s in self.snapshots]
        return self._rng.choices(self.snapshots, weights=weights, k=1)[0]

    # ------------------------------------------------------------------ persistence

    def save(self, path: Optional[str] = None) -> None:
        """Persist the pool's metadata to disk."""
        if torch is None:
            raise RuntimeError("torch is required for OpponentPool.save")
        target = path or (
            os.path.join(self.save_dir, "pool_index.pt") if self.save_dir else None
        )
        if target is None:
            raise ValueError("No path provided and no save_dir configured.")
        torch.save(
            {
                "capacity": self.capacity,
                "sampling": self.sampling,
                "pfsp_p": self.pfsp_p,
                "snapshots": [
                    {
                        "step": s.step,
                        "games": s.games,
                        "wins": s.wins,
                        "win_rate": s.win_rate,
                        "state_dict": s.state_dict,
                    }
                    for s in self.snapshots
                ],
            },
            target,
        )

    def load(self, path: Optional[str] = None) -> None:
        """Restore the pool from a file produced by :meth:`save`."""
        if torch is None:
            raise RuntimeError("torch is required for OpponentPool.load")
        target = path or (
            os.path.join(self.save_dir, "pool_index.pt") if self.save_dir else None
        )
        if target is None or not os.path.exists(target):
            return
        data = torch.load(target, map_location="cpu")
        self.snapshots = [
            Snapshot(
                step=int(d["step"]),
                state_dict=d["state_dict"],
                games=int(d.get("games", 0)),
                wins=float(d.get("wins", 0.0)),
                win_rate=float(d.get("win_rate", 0.5)),
            )
            for d in data["snapshots"]
        ]


__all__ = ["OpponentPool", "Snapshot"]

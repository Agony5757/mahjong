"""Global Reward Prediction (GRP) and placement-reward calculation.

This is a faithful port of Mortal's ``GRP`` network + ``RewardCalculator``
(see https://github.com/Equim-chan/Mortal ``mortal/model.py`` /
``mortal/reward_calculator.py``), adapted to drive reward shaping for the
Mortal-style value learner that reuses this project's Douzero network.

Mortal converts the *sparse, end-of-hanchan placement* into a per-kyoku
reward by tracking how the **expected final placement points** of a seat
change from one kyoku to the next.  The reward attributed to kyoku ``k``
is::

    reward[k] = E[pts | state after kyoku k] - E[pts | state before kyoku k]

where ``pts`` is the placement-point vector (default ``[3, 1, -1, -3]``)
and the expectation is over the final-ranking distribution.

Three ways to estimate the ranking distribution are supported via
``reward_kind``:

* ``"grp"``      -- a trained :class:`GRP` GRU predicts ``P(final rank)``
  from the running per-kyoku score sequence (most faithful to Mortal;
  needs a trained GRP checkpoint).
* ``"placement"`` -- a *provisional* deterministic ranking taken from the
  current scores at each kyoku boundary (placement-aware, **needs no
  training**).  This is the default.
* ``"points"``   -- the raw per-kyoku score delta in 25k units (Mortal's
  ``calc_delta_points``); optimises points rather than placement.

The per-kyoku rewards (one scalar per seat per kyoku) are then fed to the
Monte-Carlo Q-target ``gamma ** steps_to_done * kyoku_reward`` exactly as
Mortal does.
"""

from __future__ import annotations

from itertools import permutations
from typing import List, Optional, Sequence

import numpy as np

try:
    import torch
    from torch import Tensor, nn
    from torch.nn.utils.rnn import pack_padded_sequence, pad_sequence
except Exception:  # noqa: BLE001 -- torch optional
    torch = None  # type: ignore
    nn = object  # type: ignore
    Tensor = object  # type: ignore


# GRP input layout per kyoku boundary:
#   [grand_kyoku, honba, kyotaku, s0, s1, s2, s3]
# grand_kyoku: E1=0 .. S4=7 .. W4=11; s[i] = score of seat i / 1e4 (2.5 at E1).
GRP_SIZE: int = 7

_WIND_TO_ROUND = {"east": 0, "south": 1, "west": 2, "north": 3}
DEFAULT_PTS = (3.0, 1.0, -1.0, -3.0)


# ---------------------------------------------------------------------------
# GRP network (faithful Mortal port)
# ---------------------------------------------------------------------------


if torch is not None:

    class GRP(nn.Module):
        """GRU that predicts the final-ranking permutation distribution.

        Output is a 24-way logit (one per permutation of the 4 seats'
        final ranks).  :meth:`calc_matrix` marginalises these into a
        ``(N, seat, rank)`` probability matrix.
        """

        def __init__(self, hidden_size: int = 64, num_layers: int = 2):
            super().__init__()
            self.rnn = nn.GRU(
                input_size=GRP_SIZE,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
            )
            self.fc = nn.Sequential(
                nn.Linear(hidden_size * num_layers, hidden_size * num_layers),
                nn.ReLU(inplace=True),
                nn.Linear(hidden_size * num_layers, 24),
            )
            for mod in self.modules():
                if isinstance(mod, (nn.Linear, nn.GRU)):
                    mod.to(torch.float64)

            perms = torch.tensor(list(permutations(range(4))))
            self.register_buffer("perms", perms)             # (24, 4)
            self.register_buffer("perms_t", perms.transpose(0, 1))  # (4, 24)

        def forward(self, inputs: List[Tensor]) -> Tensor:
            lengths = torch.tensor([t.shape[0] for t in inputs], dtype=torch.int64)
            padded = pad_sequence(inputs, batch_first=True)
            packed = pack_padded_sequence(
                padded, lengths, batch_first=True, enforce_sorted=False
            )
            return self.forward_packed(packed)

        def forward_packed(self, packed_inputs) -> Tensor:
            _, state = self.rnn(packed_inputs)
            state = state.transpose(0, 1).flatten(1)
            return self.fc(state)

        def calc_matrix(self, logits: Tensor) -> Tensor:
            """``(N, 24) -> (N, seat, rank)`` probability matrix."""
            batch_size = logits.shape[0]
            probs = logits.softmax(-1)
            matrix = torch.zeros(batch_size, 4, 4, dtype=probs.dtype, device=probs.device)
            for player in range(4):
                for rank in range(4):
                    cond = self.perms_t[player] == rank
                    matrix[:, player, rank] = probs[:, cond].sum(-1)
            return matrix

        def get_label(self, rank_by_player: Tensor) -> Tensor:
            """``(N, 4) rank_by_player -> (N,)`` permutation index label."""
            batch_size = rank_by_player.shape[0]
            perms = self.perms.expand(batch_size, -1, -1).transpose(0, 1)
            mappings = (perms == rank_by_player).all(-1).nonzero()
            labels = torch.zeros(batch_size, dtype=torch.int64, device=mappings.device)
            labels[mappings[:, 1]] = mappings[:, 0]
            return labels

else:  # pragma: no cover - torch missing

    class GRP:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("torch is required to construct a GRP network")


# ---------------------------------------------------------------------------
# Feature builders (from HanchanEnv results)
# ---------------------------------------------------------------------------


def build_grp_feature(
    kyoku_history: Sequence,
    init_scores: Optional[Sequence[int]] = None,
) -> np.ndarray:
    """Build the ``(T, GRP_SIZE)`` GRP feature from a hanchan's kyoku list.

    Each row is the *pre-kyoku* state (matching Mortal's convention where
    ``s`` is ``2.5`` at the very first East-1 state).

    Args:
        kyoku_history: list of ``KyokuResult`` (needs ``bakaze``,
            ``kyoku_idx``, ``honba``, ``kyoutaku_start``, ``scores_after``).
        init_scores: starting scores (default ``25000`` each).

    Returns:
        ``(T, 7)`` float64 array.
    """
    init = list(init_scores) if init_scores is not None else [25_000] * 4
    rows: List[List[float]] = []
    scores_before = [float(s) for s in init]
    for kr in kyoku_history:
        grand_kyoku = _WIND_TO_ROUND.get(str(kr.bakaze).lower(), 0) * 4 + int(kr.kyoku_idx)
        row = [
            float(grand_kyoku),
            float(kr.honba),
            float(kr.kyoutaku_start),
            scores_before[0] / 1e4,
            scores_before[1] / 1e4,
            scores_before[2] / 1e4,
            scores_before[3] / 1e4,
        ]
        rows.append(row)
        scores_before = [float(s) for s in kr.scores_after]
    return np.asarray(rows, dtype=np.float64).reshape(-1, GRP_SIZE)


def _score_states(
    kyoku_history: Sequence,
    final_scores: Sequence[int],
    init_scores: Optional[Sequence[int]] = None,
) -> np.ndarray:
    """``(T+1, 4)`` score vectors at each kyoku boundary (incl. start + final)."""
    init = list(init_scores) if init_scores is not None else [25_000] * 4
    states: List[List[float]] = [[float(s) for s in init]]
    for kr in kyoku_history:
        states.append([float(s) for s in kr.scores_after])
    # Replace the trailing state with the authoritative final scores
    # (handles leftover-kyoutaku redistribution at hanchan end).
    if len(states) >= 1:
        states[-1] = [float(s) for s in final_scores]
    return np.asarray(states, dtype=np.float64).reshape(-1, 4)


def _placement_exp_pts(scores_row: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Per-seat expected placement points from a score vector.

    Seats are ranked by descending score; **tied seats share the average
    of their rank slots' points** (so an all-equal score state — e.g.
    East-1 start — gives every seat the mean of ``pts`` = 0 for the
    default symmetric vector, matching Mortal's uniform initialisation).
    """
    order = sorted(range(4), key=lambda i: -scores_row[i])
    exp = np.zeros(4, dtype=np.float64)
    i = 0
    while i < 4:
        j = i
        while j < 4 and scores_row[order[j]] == scores_row[order[i]]:
            j += 1
        avg = float(pts[i:j].mean())
        for k in range(i, j):
            exp[order[k]] = avg
        i = j
    return exp


# ---------------------------------------------------------------------------
# Reward calculator
# ---------------------------------------------------------------------------


class RewardCalculator:
    """Compute per-kyoku, per-seat rewards for a finished hanchan.

    Args:
        reward_kind: ``"placement"`` (default, deterministic provisional
            placement), ``"grp"`` (trained GRP net), or ``"points"`` (raw
            per-kyoku score delta).
        grp: a trained :class:`GRP` network; required when
            ``reward_kind == "grp"``.
        pts: placement-point vector for ranks ``[1st, 2nd, 3rd, 4th]``.
        points_scale: divisor applied to the ``"points"`` reward so it
            shares the 25k scale used elsewhere (default ``25000``).
        device: torch device for the GRP forward pass.
    """

    def __init__(
        self,
        reward_kind: str = "placement",
        grp: Optional["GRP"] = None,
        pts: Sequence[float] = DEFAULT_PTS,
        points_scale: float = 25_000.0,
        device: str = "cpu",
    ):
        if reward_kind not in {"placement", "grp", "points"}:
            raise ValueError(f"unknown reward_kind: {reward_kind!r}")
        if reward_kind == "grp" and grp is None:
            raise ValueError("reward_kind='grp' requires a trained GRP network")
        self.reward_kind = reward_kind
        self.grp = grp
        self.pts = np.asarray(pts, dtype=np.float64)
        self.points_scale = float(points_scale)
        self.device = device
        if grp is not None and torch is not None:
            self.grp = grp.to(torch.device(device)).eval()

    # -- public API --------------------------------------------------------

    def kyoku_rewards(
        self,
        kyoku_history: Sequence,
        ranks: Sequence[int],
        final_scores: Sequence[int],
        init_scores: Optional[Sequence[int]] = None,
    ) -> np.ndarray:
        """Return a ``(T, 4)`` array: reward of each seat for each kyoku.

        ``T = len(kyoku_history)``.  Row ``k`` is the reward attributed to
        kyoku ``k`` for all four seats.
        """
        T = len(kyoku_history)
        if T == 0:
            return np.zeros((0, 4), dtype=np.float32)
        if self.reward_kind == "points":
            return self._points_rewards(kyoku_history, final_scores, init_scores)
        if self.reward_kind == "placement":
            return self._placement_rewards(kyoku_history, final_scores, init_scores)
        return self._grp_rewards(kyoku_history, ranks, init_scores)

    # -- reward kinds ------------------------------------------------------

    def _points_rewards(self, kyoku_history, final_scores, init_scores) -> np.ndarray:
        states = _score_states(kyoku_history, final_scores, init_scores)  # (T+1, 4)
        deltas = (states[1:] - states[:-1]) / self.points_scale           # (T, 4)
        return deltas.astype(np.float32)

    def _placement_rewards(self, kyoku_history, final_scores, init_scores) -> np.ndarray:
        states = _score_states(kyoku_history, final_scores, init_scores)  # (T+1, 4)
        exp_pts = np.zeros((states.shape[0], 4), dtype=np.float64)        # (T+1, 4)
        for t in range(states.shape[0]):
            exp_pts[t] = _placement_exp_pts(states[t], self.pts)
        rewards = exp_pts[1:] - exp_pts[:-1]                              # (T, 4)
        return rewards.astype(np.float32)

    def _grp_rewards(self, kyoku_history, ranks, init_scores) -> np.ndarray:
        if torch is None:
            raise RuntimeError("torch is required for reward_kind='grp'")
        grp_feature = build_grp_feature(kyoku_history, init_scores)       # (T, 7)
        rank_by_player = np.asarray(ranks, dtype=np.int64)
        T = grp_feature.shape[0]
        rewards = np.zeros((T, 4), dtype=np.float32)
        matrix = self._calc_grp_matrix(grp_feature)                      # (T, seat, rank)
        pts_t = torch.as_tensor(self.pts, dtype=torch.float64)
        for player in range(4):
            final_one_hot = torch.zeros((1, 4), dtype=torch.float64)
            final_one_hot[0, int(rank_by_player[player])] = 1.0
            rank_prob = torch.cat((matrix[:, player], final_one_hot))    # (T+1, 4)
            exp_pts = rank_prob @ pts_t                                   # (T+1,)
            reward = (exp_pts[1:] - exp_pts[:-1]).cpu().numpy()           # (T,)
            rewards[:, player] = reward.astype(np.float32)
        return rewards

    def _calc_grp_matrix(self, grp_feature: np.ndarray):
        dev = torch.device(self.device)
        seq = [
            torch.as_tensor(grp_feature[: idx + 1], dtype=torch.float64, device=dev)
            for idx in range(grp_feature.shape[0])
        ]
        with torch.inference_mode():
            logits = self.grp(seq)
            matrix = self.grp.calc_matrix(logits)
        return matrix.cpu()


__all__ = [
    "GRP",
    "GRP_SIZE",
    "DEFAULT_PTS",
    "RewardCalculator",
    "build_grp_feature",
]

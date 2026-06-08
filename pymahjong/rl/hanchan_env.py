"""Hanchan (半庄) wrapper over :class:`MultiAgentEnv`.

A *hanchan* is a full Mahjong session of multiple kyoku (hands), with
score / oya / honba / kyoutaku state carrying over between hands.  The
underlying :class:`MultiAgentEnv` (and the C++ engine) is a single-hand
state machine, so this wrapper drives the inter-hand state transitions.

Standard Tenhou ari-ari rules supported here:

* **East round**: kyoku 1..4 (oya = 0, 1, 2, 3)
* **South round**: kyoku 1..4 (oya cycles again)
* **Renchan (連荘)**: dealer continues (kyoku-index does NOT advance) if
  any of:
    - dealer is among the winners (RonAgari/TsumoAgari);
    - ryuukyoku (NoTileRyuuKyoku) and dealer is tenpai.
* **Honba (本場)**: ``+1`` on renchan or ryuukyoku-advance, reset to ``0``
  on a clean non-dealer agari advance.
* **Kyoutaku (供託)**: riichi sticks carry over on ryuukyoku, are taken
  by the agari winner.
* **West-round extension (西入)**: if no player has ≥ ``oka_threshold``
  (default 30 000) at end of South-4, continue into the West round.
  Stop at the first hand where some player crosses the threshold, or
  at the end of West-4 regardless.
* **Tobi (飛び)**: any player score < 0 → hanchan ends immediately.
* **Leftover kyoutaku** at hanchan end goes to the highest-score player
  (Tenhou convention; tie goes to the lower seat number).

API mirrors :class:`MultiAgentEnv`'s per-kyoku interface but adds the
hanchan-level lifecycle::

    env = HanchanEnv()
    obs = env.reset(seed=0)
    while not env.is_hanchan_over():
        while not env.is_kyoku_over():
            obs, payoffs, done, info = env.kyoku_step(action_picked_from(obs))
        # kyoku ended — record paipu, inspect, etc.
        recorder.record_hand(env.get_inner_table(), seed=...)
        if not env.is_hanchan_over():
            obs = env.advance_to_next_kyoku()

The class deliberately does *not* auto-record paipu or auto-call any
policy — those are the caller's responsibility, so the same wrapper
works for evaluation, training, and human play.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import MahjongPyWrapper as pm
except ImportError:
    pm = None

from .env import MultiAgentEnv


_WIND_NAMES = ["east", "south", "west", "north"]


@dataclass
class KyokuResult:
    """Summary of a single finished kyoku."""

    bakaze: str                      # "east" | "south" | "west" | "north"
    kyoku_idx: int                   # 0..3 within the bakaze round
    oya: int                         # 0..3
    honba: int                       # start-of-kyoku honba
    kyoutaku_start: int              # riichi-sticks on the table at start
    result_type: str                 # e.g. "RonAgari", "NoTileRyuuKyoku"
    winners: List[int] = field(default_factory=list)
    is_agari: bool = False
    is_dealer_renchan: bool = False
    is_ryuukyoku: bool = False
    score_changes_25k: List[float] = field(default_factory=list)  # 4-vector
    scores_after: List[int] = field(default_factory=list)         # 4-vector
    steps: int = 0
    seed: Optional[int] = None


@dataclass
class HanchanResult:
    """Summary of one finished hanchan."""

    final_scores: List[int] = field(default_factory=list)
    ranks: List[int] = field(default_factory=list)       # 0=1st .. 3=4th
    n_kyoku: int = 0
    n_agari: int = 0                                     # total kyoku ending in agari
    n_ryuukyoku: int = 0
    n_dealer_renchan: int = 0
    termination_reason: str = ""                         # "south_4" | "west_4" | "agariyame" | "tobi" | "max_kyoku"
    per_seat_agari: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    per_seat_houjuu: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    kyoku: List[KyokuResult] = field(default_factory=list)


class HanchanEnv:
    """Hanchan-loop wrapper around :class:`MultiAgentEnv`.

    Args:
        max_seq_len: passed to the inner V4 env.
        init_scores: starting scores (4-vector, default ``25000`` each).
        oka_threshold: trigger for ending past South-4 and for the West
            round.  Default 30 000.
        starting_oya: dealer for the very first kyoku.  Default 0.
        use_west_round: if True, when no one is ≥ ``oka_threshold`` at
            end of South-4, play continues into West round until threshold
            is reached or West-4 ends.  Default True.
        max_extra_kyoku: hard cap on extra kyoku to prevent infinite
            renchan / extension loops.  Default 16.
        tobi: if True, hanchan ends as soon as any player < 0.
        leftover_kyoutaku_to_first: if True, the kyoutaku stick(s) left
            on the table at hanchan end are awarded to the leader.
    """

    def __init__(
        self,
        *,
        max_seq_len: int = 512,
        init_scores: Optional[List[int]] = None,
        oka_threshold: int = 30_000,
        starting_oya: int = 0,
        use_west_round: bool = True,
        max_extra_kyoku: int = 16,
        tobi: bool = True,
        leftover_kyoutaku_to_first: bool = True,
    ):
        if pm is None:
            raise RuntimeError("MahjongPyWrapper not importable")
        self.max_seq_len = max_seq_len
        self._init_scores = list(init_scores) if init_scores else [25_000] * 4
        self._oka_threshold = oka_threshold
        self._starting_oya = starting_oya
        self._use_west_round = use_west_round
        self._max_extra_kyoku = max_extra_kyoku
        self._tobi = tobi
        self._leftover_to_first = leftover_kyoutaku_to_first
        self._inner: Optional[MultiAgentEnv] = None

    # --------------------------------------------------------------- lifecycle

    def reset(self, seed: Optional[int] = None) -> Dict[str, Any]:
        """Start a new hanchan; return the first kyoku's first observation."""
        self._scores: List[int] = list(self._init_scores)
        self._oya: int = self._starting_oya
        self._kyoku_idx_in_round: int = 0       # 0..3 within the current round
        self._bakaze_idx: int = 0                # 0=East, 1=South, 2=West
        self._honba: int = 0
        self._kyoutaku: int = 0
        self._kyoku_seq: int = 0                 # global kyoku counter (0-based)
        self._extra_kyoku_count: int = 0
        self._hanchan_over: bool = False
        self._termination_reason: str = ""
        self._last_kyoku_result: Optional[KyokuResult] = None
        self._kyoku_history: List[KyokuResult] = []
        self._kyoku_seed: Optional[int] = seed
        self._kyoku_step_count: int = 0
        return self._start_kyoku()

    def _start_kyoku(self) -> Dict[str, Any]:
        """Construct a fresh MultiAgentEnv at the current bakaze/oya/etc."""
        self._inner = MultiAgentEnv(max_seq_len=self.max_seq_len)
        try:
            obs = self._inner.reset(
                seed=self._kyoku_seed,
                oya=self._oya,
                game_wind=_WIND_NAMES[self._bakaze_idx],
                scores=list(self._scores),
                honba=self._honba,
                kyoutaku=self._kyoutaku,
            )
        except Exception as e:
            # If the engine refuses to start the kyoku (rare seed edge case),
            # mark the hanchan as terminated so the outer loop bails cleanly.
            self._hanchan_over = True
            self._termination_reason = f"engine_refused_start: {e!r}"
            return {
                "features": np.zeros((1, 100), dtype=np.bool_),
                "attention_mask": np.zeros((1,), dtype=np.bool_),
                "action_mask": np.zeros((54,), dtype=np.bool_),
            }
        self._kyoku_step_count = 0
        return obs

    # --------------------------------------------------------------- per-kyoku I/O

    def observe(self) -> Dict[str, Any]:
        if self._inner is None:
            raise RuntimeError("Call reset() before observe().")
        return self._inner.observe()

    @property
    def current_player(self) -> int:
        if self._inner is None:
            raise RuntimeError("Call reset() before current_player.")
        return self._inner.current_player

    def is_kyoku_over(self) -> bool:
        return self._inner is None or self._inner.is_over()

    def kyoku_step(self, action: int):
        """Step the current kyoku.

        Returns:
            ``(obs, payoffs, kyoku_done, info)`` — same shape as
            :meth:`MultiAgentEnv.step`.  ``payoffs`` is the per-kyoku
            ``info["payoffs"]/25000`` array when ``kyoku_done`` is True,
            else ``None``.

        After ``kyoku_done`` becomes True, call
        :meth:`advance_to_next_kyoku` to start the next hand (or check
        :meth:`is_hanchan_over` first).
        """
        if self._inner is None:
            raise RuntimeError("Call reset() before kyoku_step().")
        if self._hanchan_over:
            raise RuntimeError("hanchan is over; nothing to step")
        obs, payoffs, done, info = self._inner.step(action)
        self._kyoku_step_count += 1
        if done:
            self._finalize_kyoku(payoffs, info)
        return obs, payoffs, done, info

    def advance_to_next_kyoku(self) -> Dict[str, Any]:
        """Apply renchan/advance rules; start the next kyoku."""
        if self._hanchan_over:
            raise RuntimeError("hanchan is over; cannot advance")
        if self._last_kyoku_result is None:
            raise RuntimeError("call kyoku_step until done before advancing")

        result = self._last_kyoku_result
        self._scores = list(result.scores_after)

        # Update the on-table riichi-stick (kyoutaku) count to its
        # POST-hand value *before* any hanchan-termination branch, so the
        # leftover-stick distribution at hanchan end uses the correct
        # count.  ``t.get_result().n_riichibo`` is the post-distribution
        # stick count (0 on agari since the winner collected, may be >0 on
        # ryuukyoku from carry-over + new riichis this hand).  Falling
        # back to counting RiichiSuccess from the gamelog if the result
        # was uninitialised.
        try:
            n_riichi_end = int(self.get_inner_table().get_result().n_riichibo)
        except Exception:
            n_riichi_end = -1
        if n_riichi_end < 0:
            try:
                logs = list(self.get_inner_table().gamelog.logs)
                n_new_riichi = sum(
                    1 for e in logs if e.action == pm.LogAction.RiichiSuccess
                )
                if result.is_agari:
                    n_riichi_end = 0  # winner took all sticks
                else:
                    n_riichi_end = self._kyoutaku + n_new_riichi
            except Exception:
                n_riichi_end = 0
        self._kyoutaku = max(0, int(n_riichi_end))

        # Tobi: end immediately if any player < 0.
        if self._tobi and any(s < 0 for s in self._scores):
            self._hanchan_over = True
            self._termination_reason = "tobi"
            self._distribute_leftover_kyoutaku()
            return self._dummy_obs()

        # Renchan vs advance.
        if result.is_dealer_renchan:
            self._honba = result.honba + 1
            # kyoku_idx and oya stay
        else:
            self._honba = (
                result.honba + 1 if result.is_ryuukyoku else 0
            )
            self._oya = (self._oya + 1) % 4
            self._kyoku_idx_in_round += 1
            # Round transition.
            if self._kyoku_idx_in_round >= 4:
                self._kyoku_idx_in_round = 0
                self._bakaze_idx += 1
                # Decide whether to end the hanchan.
                if self._bakaze_idx >= 2:
                    # Past South-4: enter West only if extension allowed and
                    # no one has reached the oka threshold yet.
                    if (
                        self._bakaze_idx == 2
                        and self._use_west_round
                        and max(self._scores) < self._oka_threshold
                    ):
                        pass  # continue into West
                    else:
                        self._hanchan_over = True
                        self._termination_reason = (
                            "west_4" if self._bakaze_idx > 2 else "south_4"
                        )
                        self._distribute_leftover_kyoutaku()
                        return self._dummy_obs()

        # West-round mid-stop: end as soon as any player reaches oka.
        if (
            self._bakaze_idx == 2
            and max(self._scores) >= self._oka_threshold
        ):
            self._hanchan_over = True
            self._termination_reason = "west_oka_reached"
            self._distribute_leftover_kyoutaku()
            return self._dummy_obs()

        # Safety: cap total kyoku to prevent infinite renchan loops.
        self._kyoku_seq += 1
        if result.is_dealer_renchan or result.is_ryuukyoku:
            self._extra_kyoku_count += 1
        if self._extra_kyoku_count >= self._max_extra_kyoku:
            self._hanchan_over = True
            self._termination_reason = "max_kyoku"
            self._distribute_leftover_kyoutaku()
            return self._dummy_obs()

        # Bump seed deterministically (each kyoku gets a unique seed
        # derived from the hanchan's base seed + kyoku index).
        if self._kyoku_seed is not None:
            self._kyoku_seed += 1

        return self._start_kyoku()

    # --------------------------------------------------------------- introspection

    def is_hanchan_over(self) -> bool:
        return self._hanchan_over

    def get_inner_table(self):
        """Return the underlying pm.Table for paipu recording / inspection."""
        if self._inner is None:
            raise RuntimeError("no inner env (call reset() first)")
        return self._inner._inner.t

    def get_inner_env(self) -> MultiAgentEnv:
        if self._inner is None:
            raise RuntimeError("no inner env (call reset() first)")
        return self._inner

    @property
    def state(self) -> Dict[str, Any]:
        """Snapshot of inter-kyoku hanchan state."""
        return {
            "bakaze": _WIND_NAMES[self._bakaze_idx],
            "bakaze_idx": self._bakaze_idx,
            "kyoku_idx_in_round": self._kyoku_idx_in_round,
            "global_kyoku_seq": self._kyoku_seq,
            "oya": self._oya,
            "honba": self._honba,
            "kyoutaku": self._kyoutaku,
            "scores": list(self._scores),
            "hanchan_over": self._hanchan_over,
            "termination_reason": self._termination_reason,
            "kyoku_step_count": self._kyoku_step_count,
        }

    def get_hanchan_result(self) -> HanchanResult:
        """Compute the aggregated hanchan summary (call after hanchan ends)."""
        # Ranks: index of each seat in descending order of final score.
        order = sorted(range(4), key=lambda i: (-self._scores[i], i))
        ranks = [0, 0, 0, 0]
        for rank, seat in enumerate(order):
            ranks[seat] = rank
        per_seat_agari = [0, 0, 0, 0]
        per_seat_houjuu = [0, 0, 0, 0]
        n_agari = 0
        n_ryuu = 0
        n_renchan = 0
        for k in self._kyoku_history:
            if k.is_agari:
                n_agari += 1
                for w in k.winners:
                    if 0 <= w < 4:
                        per_seat_agari[w] += 1
                if k.result_type == "RonAgari":
                    # Houjuu seat = the one with the *most negative* delta among non-winners.
                    losers = [
                        i for i in range(4) if i not in k.winners
                    ]
                    if losers:
                        worst = min(losers, key=lambda i: k.score_changes_25k[i])
                        per_seat_houjuu[worst] += 1
            elif k.is_ryuukyoku:
                n_ryuu += 1
            if k.is_dealer_renchan:
                n_renchan += 1
        return HanchanResult(
            final_scores=list(self._scores),
            ranks=ranks,
            n_kyoku=len(self._kyoku_history),
            n_agari=n_agari,
            n_ryuukyoku=n_ryuu,
            n_dealer_renchan=n_renchan,
            termination_reason=self._termination_reason or "in_progress",
            per_seat_agari=per_seat_agari,
            per_seat_houjuu=per_seat_houjuu,
            kyoku=copy.copy(self._kyoku_history),
        )

    # --------------------------------------------------------------- internals

    def _dummy_obs(self) -> Dict[str, Any]:
        return {
            "features": np.zeros((1, 100), dtype=np.bool_),
            "attention_mask": np.zeros((1,), dtype=np.bool_),
            "action_mask": np.zeros((54,), dtype=np.bool_),
        }

    def _finalize_kyoku(
        self, payoffs: Optional[np.ndarray], info: Dict[str, Any]
    ) -> None:
        """Record kyoku result + decide renchan; called at kyoku end."""
        t = self.get_inner_table()

        # IMPORTANT: ``t.get_scores()`` returns ``players[i].score`` which
        # is NOT updated for tenpai-noten settlement at ryuukyoku.
        # ``t.get_result().score`` is the authoritative post-settlement
        # score per seat.  When the engine's ``result`` is uninitialised
        # (rare forced-end edge case) we reconstruct from ``payoffs``
        # which MultiAgentEnv produced from ``get_payoffs()``.
        res = t.get_result()
        result_score = list(res.score)
        if all(s == 0 for s in result_score) and payoffs is not None:
            # Result not populated → reconstruct: start_scores + payoffs*25000.
            result_score = [
                int(self._scores[i] + float(payoffs[i]) * 25000.0)
                for i in range(4)
            ]
        scores_after = result_score

        if payoffs is None:
            score_changes = [
                (scores_after[i] - self._scores[i]) / 25000.0 for i in range(4)
            ]
        else:
            score_changes = list(payoffs)

        # Result type — fall back if the engine left result_type=Error.
        rt_obj = res.result_type
        try:
            rt_str = str(rt_obj).split(".")[-1] if rt_obj is not None else "Unknown"
        except Exception:
            rt_str = "Unknown"
        if rt_str == "???":
            rt_str = "ForcedEnd"

        is_agari = bool(info.get("is_agari", False))
        winners: List[int] = list(info.get("winners", []) or [])
        is_ryuukyoku = (not is_agari) or (rt_str == "NoTileRyuuKyoku")

        # Renchan logic.
        is_dealer_renchan = False
        if is_agari and self._oya in winners:
            is_dealer_renchan = True
        elif is_ryuukyoku:
            try:
                if t.players[self._oya].is_tenpai():
                    is_dealer_renchan = True
            except Exception:
                pass

        self._last_kyoku_result = KyokuResult(
            bakaze=_WIND_NAMES[self._bakaze_idx],
            kyoku_idx=self._kyoku_idx_in_round,
            oya=self._oya,
            honba=self._honba,
            kyoutaku_start=self._kyoutaku,
            result_type=rt_str,
            winners=winners,
            is_agari=is_agari,
            is_dealer_renchan=is_dealer_renchan,
            is_ryuukyoku=is_ryuukyoku,
            score_changes_25k=score_changes,
            scores_after=scores_after,
            steps=self._kyoku_step_count,
            seed=self._kyoku_seed,
        )
        self._kyoku_history.append(self._last_kyoku_result)

    def _distribute_leftover_kyoutaku(self) -> None:
        """Award any sticks left on the table to the leader (Tenhou rule)."""
        if not self._leftover_to_first or self._kyoutaku <= 0:
            return
        # Use scores carried over from last kyoku.
        leader = int(np.argmax(self._scores))
        self._scores[leader] += self._kyoutaku * 1000
        self._kyoutaku = 0


__all__ = ["HanchanEnv", "KyokuResult", "HanchanResult"]

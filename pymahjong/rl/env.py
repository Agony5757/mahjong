"""Multi-agent Mahjong env wired to :class:`LiveEncoder`.

Produces real event-stream observations via a live event encoder that
mirrors the table.  The env maintains one :class:`pm.encv4_HandEncoder`
per episode (it already tracks all four per-seat event streams
internally) and produces real observations on every call to
:meth:`observe`.

The env supports:

* **Shared self-play** — every seat calls the learner policy.
* **Mixed self-play** — a per-seat ``policy_fn`` mapping; seats whose
  ``policy_fn`` is set (e.g., a frozen snapshot) act inline without
  generating learner transitions.

Reward convention:

* Intermediate steps yield ``reward = 0`` and ``done = False``.
* On terminal step, ``payoffs`` (length-4, dtype float32) is the per-seat
  reward in *units of 25 000 points*.
* The terminal ``info`` dict additionally exposes ``result_type``
  (e.g. ``"RonAgari"``, ``"TsumoAgari"``, ``"NoTileRyuuKyoku"``, ...)
  and ``winners`` (list of seat indices), so the training loop can
  apply optional reward shaping (e.g. a per-winner bootstrap bonus).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    import MahjongPyWrapper as pm  # type: ignore
except Exception:  # noqa: BLE001
    pm = None  # type: ignore

from .action_space import (
    ACTION_DIM,
    A_PASS_RIICHI,
    A_RIICHI,
    ActionEncoder,
)
from .live_encoder import LiveEncoder

PolicyFn = Callable[[Dict[str, Any], int], int]
"""Type alias: ``policy(obs_dict, seat) -> unified_action``."""


class MultiAgentEnv:
    """4-player Mahjong env producing real event-stream observations.

    Each episode is a single hand.  Construct once; call :meth:`reset` to
    start a new hand.  Within a hand, repeatedly call :meth:`observe`
    (returns the current acting seat's observation) followed by
    :meth:`step(action)`.

    Args:
        max_seq_len: pad/truncate the per-seat event stream to this many
            events for the model.  Must match the model's training-time
            ``MAX_SEQ_LEN``.
        opponent_policies: optional ``dict[seat -> PolicyFn]``.  Seats
            present in this dict are stepped *inline* via the supplied
            policy in :meth:`auto_step_opponents`, so the outer training
            loop only sees learner-seat transitions.  Leave ``None`` for
            pure shared self-play (default).
    """

    def __init__(
        self,
        max_seq_len: int = 512,
        opponent_policies: Optional[Dict[int, PolicyFn]] = None,
    ):
        if pm is None:
            raise RuntimeError("MahjongPyWrapper not importable")
        from pymahjong.env_pymahjong import MahjongEnv

        self._inner = MahjongEnv()
        self.max_seq_len = max_seq_len
        self.opponent_policies: Dict[int, PolicyFn] = dict(opponent_policies or {})
        self._enc: Optional[LiveEncoder] = None

    # Class-level flag so we warn at most once per process about the
    # rare legacy-mask-rejection fallback in :meth:`_execute_unified`.
    _fallback_warned: bool = False

    # ------------------------------------------------------------------ basics

    @property
    def current_player(self) -> int:
        return self._inner.get_curr_player_id()

    def is_over(self) -> bool:
        return self._inner.is_over()

    def get_result_info(self) -> dict:
        """Return terminal-hand result info.  Valid only after :meth:`is_over`."""
        return self._inner.get_result_info()

    def is_learner_seat(self, seat: int) -> bool:
        """Return True if *seat* is controlled by the learner (no fixed policy)."""
        return seat not in self.opponent_policies

    def set_opponent_policies(self, policies: Optional[Dict[int, PolicyFn]]) -> None:
        """Replace the seat→policy mapping for the next episode/step."""
        self.opponent_policies = dict(policies or {})

    # ------------------------------------------------------------------ lifecycle

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        oya: Optional[int] = None,
        game_wind: Optional[str] = None,
        scores: Optional[List[int]] = None,
        honba: int = 0,
        kyoutaku: int = 0,
    ) -> Dict[str, Any]:
        """Start a new hand and return the first acting seat's observation.

        Returns the observation for ``current_player`` (i.e., for whoever
        is *first* required to make a non-forced decision).
        """
        self._inner.reset(
            seed=seed,
            oya=oya,
            game_wind=game_wind,
            scores=scores,
            honba=honba,
            kyoutaku=kyoutaku,
        )
        # New pm.Table() — must construct a fresh LiveEncoder bound to it.
        self._enc = LiveEncoder(self._inner.t)
        self._enc.start_hand()

        # Step through any forced-only opening moves (engine sometimes
        # produces a single legal action which neither the learner nor a
        # human would meaningfully "choose").
        self._skip_forced()
        return self.observe()

    # ------------------------------------------------------------------ observation

    def observe(self) -> Dict[str, Any]:
        """Snapshot the current acting seat's observation.

        The returned ``action_mask`` uses the *legacy* mask from
        :meth:`MahjongEnv.get_valid_actions` instead of the
        engine-iteration mask.  The legacy mask is the single source of
        truth that :meth:`MahjongEnv.step` validates against — keeping
        the two in sync avoids "Not an action in available actions"
        ValueErrors that arise from the mask permitting actions the
        legacy mask rejects (red-dora variants, riichi_stage2, chi
        disambiguation, etc.).
        """
        if self._enc is None:
            raise RuntimeError("Call reset() before observe().")
        seat = self.current_player
        # Always keep the encoder in sync before snapshotting.
        obs = self._enc.observation_for(
            seat,
            register_decide=True,
            max_seq_len=self.max_seq_len,
        )
        # Override with the legacy mask so the model only ever samples
        # actions that MahjongEnv.step will accept.
        legacy_mask = np.asarray(
            self._inner.get_valid_actions(nhot=True), dtype=bool
        )
        if legacy_mask.shape[0] != ACTION_DIM:
            # Pad / truncate defensively.
            fixed = np.zeros(ACTION_DIM, dtype=bool)
            n = min(ACTION_DIM, legacy_mask.shape[0])
            fixed[:n] = legacy_mask[:n]
            legacy_mask = fixed
        obs = dict(obs)
        obs["action_mask"] = legacy_mask
        return obs

    def observe_seat(self, seat: int) -> Dict[str, Any]:
        """Snapshot *seat*'s observation without writing a DECIDE event.

        Useful for evaluation or value-network bootstrapping at episode end
        where we want every seat's terminal state but don't want extra
        DECIDE markers on tracks that aren't actually about to act.
        """
        if self._enc is None:
            raise RuntimeError("Call reset() before observe_seat().")
        return self._enc.observation_for(
            seat,
            register_decide=False,
            max_seq_len=self.max_seq_len,
        )

    # ------------------------------------------------------------------ stepping

    def step(self, action: int) -> Tuple[Optional[Dict[str, Any]], np.ndarray, bool, dict]:
        """Execute *action* for the current acting seat.

        Mirrors the shared :class:`EncodingMultiAgentEnv.step` semantics:
        intermediate rewards are zero, terminal rewards are the per-seat
        payoff in units of 25 000 points.  After execution, the env may
        auto-skip forced moves and inline-step seats in
        ``opponent_policies`` so the returned observation belongs to the
        *next learner seat to act* (or ``None`` if the episode ended).

        Returns:
            ``(next_obs_or_None, payoffs (4,), done, info)``.  ``info``
            always includes ``"acting_seat"``; on terminal step it also
            includes ``"result_type"`` (str), ``"winners"`` (list[int]),
            and ``"is_agari"`` (bool) — see
            :meth:`pymahjong.env_pymahjong.MahjongEnv.get_result_info`.
        """
        if self._enc is None:
            raise RuntimeError("Call reset() before step().")

        acting_seat = self.current_player
        self._execute_unified(int(action))
        self._enc.sync()
        self._skip_forced()
        self._auto_step_opponents()

        done = self._inner.is_over()
        if done:
            payoffs = self._inner.get_payoffs().astype(np.float32) / 25000.0
            next_obs = None
            info: dict = {"acting_seat": acting_seat}
            info.update(self._inner.get_result_info())
        else:
            payoffs = np.zeros(4, dtype=np.float32)
            next_obs = self.observe()
            info = {"acting_seat": acting_seat}
        return next_obs, payoffs, done, info

    # ------------------------------------------------------------------ internals

    def _execute_unified(self, action: int) -> None:
        """Execute a unified 54-action via the legacy :class:`MahjongEnv.step`.

        Delegating to :meth:`MahjongEnv.step` is the simplest correct way
        to handle the full action space, including the Riichi two-step,
        red-5 disambiguation, Chi/Pon tile selection, and the internal
        :meth:`_proceed` to skip single-legal-action phases.
        """
        seat = self._inner.get_curr_player_id()
        try:
            self._inner.step(seat, int(action))
        except ValueError as e:
            if "Not an action in available actions" in str(e):
                # The legacy mask rejected our action.  Falls back to the
                # first legal action so a multi-hour training run isn't
                # lost.  Warning is emitted only once per process (the
                # underlying drift is rare and benign for training).
                fallback = int(self._inner.get_valid_actions(nhot=False)[0])
                if not MultiAgentEnv._fallback_warned:
                    import warnings
                    warnings.warn(
                        f"env: legacy mask rejected unified action={action} "
                        f"at seat={seat}; falling back to legal action={fallback}. "
                        f"Further drifts will be silently coerced.  This usually "
                        f"indicates rare engine vs encv1 mask drift; training "
                        f"continues unaffected.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    MultiAgentEnv._fallback_warned = True
                self._inner.step(seat, fallback)
            else:
                raise

    def _skip_forced(self) -> None:
        """Auto-advance through phases where only a single action is legal."""
        while not self._inner.is_over():
            valid = self._inner.get_valid_actions(nhot=False)
            if len(valid) > 1:
                return
            # Single legal engine-level action — execute it directly.
            self._inner.step(self.current_player, int(valid[0]))
            if self._enc is not None:
                self._enc.sync()

    def _auto_step_opponents(self) -> None:
        """Inline-step seats that have a fixed (non-learner) policy."""
        if not self.opponent_policies:
            return
        guard = 0
        while (
            not self._inner.is_over()
            and self.current_player in self.opponent_policies
        ):
            guard += 1
            if guard > 256:
                raise RuntimeError(
                    "Opponent auto-step exceeded 256 iterations — likely a bug."
                )
            seat = self.current_player
            obs = self.observe()  # writes DECIDE on opponent's own track
            policy = self.opponent_policies[seat]
            action = int(policy(obs, seat))
            # Coerce to a valid masked action defensively.
            mask = obs["action_mask"]
            if not bool(mask[action]):
                valid_idx = np.flatnonzero(mask)
                if valid_idx.size == 0:
                    raise RuntimeError(f"No valid actions for seat {seat}")
                action = int(valid_idx[0])
            self._execute_unified(action)
            if self._enc is not None:
                self._enc.sync()
            self._skip_forced()


__all__ = ["MultiAgentEnv", "PolicyFn"]

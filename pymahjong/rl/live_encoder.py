"""Live encoder for online inference.

Maintains a :class:`pm.encv4_HandEncoder` that stays in sync with a
running :class:`pm.Table`. Use it to produce real-time observations
for a trained model during interactive play.

Typical usage (per session, per hand)::

    enc = LiveEncoder(table)
    enc.start_hand()        # call right after game_init_with_config

    # ... game proceeds; the application drives table.make_selection ...
    enc.sync()              # call after every make_selection (cheap)

    # When the model needs to act:
    obs = enc.observation_for(player_id)
    # obs = {"features": (L, 100) float32,
    #        "attention_mask": (L,) bool,
    #        "action_mask": (54,) bool}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

try:
    import MahjongPyWrapper as pm  # type: ignore
except Exception:  # noqa: BLE001
    pm = None  # type: ignore

from .tokenization import (
    EVENT_DIM,
    _engine_action_label,
    _engine_action_mask,
    _route_gamelog_entries,
)


class LiveEncoder:
    """Stateful encoder that mirrors a running :class:`pm.Table`.

    Hand boundary handling: call :meth:`start_hand` once after each
    ``game_init_with_config`` (or whatever the host's "new hand" hook
    is). Within a hand, call :meth:`sync` after every ``make_selection``
    so newly-logged events get routed to the encoder. The cost of
    :meth:`sync` is O(new gamelog entries) — typically one or two.

    Each of the four per-player tracks is an independent view of the
    visible game: public events (discards / calls / dora reveal) are
    broadcast to all four tracks, draws only enter the drawing
    player's own track, and DECIDE events are written only to the
    deciding player's own track. This matches
    :func:`encode_paipu_file` so training and inference see the
    same per-track event stream.
    """

    def __init__(self, table):
        if pm is None:
            raise RuntimeError("MahjongPyWrapper not importable")
        self.table = table
        self._encoder = None
        self._last_gamelog_len = 0

    # ----------------------------------------------------------------- lifecycle

    def start_hand(self) -> None:
        """Re-initialize the underlying encoder for a fresh hand.

        Reads the table's current state (assumes ``game_init_with_config``
        was just called) and fires INIT_HAND events for all four players.
        """
        self._encoder = pm.encv4_HandEncoder(self.table)
        self._encoder.encode_init()
        # game_init_with_config writes some initial log entries (the 4
        # log_draw calls for the 13th/14th tiles). encode_init already
        # captured them via the table snapshot, so skip them on sync.
        self._last_gamelog_len = len(self.table.gamelog.logs)

    def sync(self) -> None:
        """Route any new gamelog entries to the encoder."""
        if self._encoder is None:
            return
        gl = self.table.gamelog
        n = len(gl.logs)
        if n <= self._last_gamelog_len:
            return
        new_entries = gl.logs[self._last_gamelog_len:n]
        _route_gamelog_entries(self._encoder, new_entries)
        self._last_gamelog_len = n

    # ---------------------------------------------------------------- observation

    def observation_for(
        self,
        player_id: int,
        *,
        register_decide: bool = True,
        max_seq_len: int = 512,
    ) -> Dict[str, Any]:
        """Snapshot the per-player event stream for a model forward pass.

        Args:
            player_id: seat (0-3) currently being asked to act.
            register_decide: if True (default), emit a DECIDE event to
                this player's own track before snapshotting so the
                model sees the same per-decision marker it was trained
                against. Only that player's track is touched.
            max_seq_len: pad/truncate the stream to this many events.

        Returns:
            dict with ``features``, ``attention_mask``, ``action_mask``.
        """
        if self._encoder is None:
            self.start_hand()
        # Make sure we're caught up with the table.
        self.sync()

        action_mask = _engine_action_mask(self.table, player_id).astype(bool)
        if register_decide:
            self._encoder.on_decide(player_id, action_mask, 0)

        track = self._encoder.track(player_id)
        events = np.asarray(track.events(), dtype=np.bool_)
        seq_len = int(events.shape[0])
        if seq_len > max_seq_len:
            events = events[-max_seq_len:]
            seq_len = max_seq_len

        features = np.zeros((seq_len, EVENT_DIM), dtype=np.float32)
        features[:seq_len] = events
        attention_mask = np.ones((seq_len,), dtype=np.bool_)

        return {
            "features": features,
            "attention_mask": attention_mask,
            "action_mask": action_mask,
        }


__all__ = ["LiveEncoder"]

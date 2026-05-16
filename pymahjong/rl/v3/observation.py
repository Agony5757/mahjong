"""V3 observation space and action resolution helpers."""

from __future__ import annotations

import numpy as np
from gymnasium.spaces import Box, Dict as DictSpace

from ..action_space import ActionEncoder, ACTION_DIM
from .tokenization import MAX_SEQ_LEN, SCALAR_DIM, TOKEN_FEATURES


def _build_observation_space(max_seq_len: int = MAX_SEQ_LEN) -> DictSpace:
    return DictSpace(
        {
            "tokens": Box(
                low=0,
                high=255,
                shape=(max_seq_len, TOKEN_FEATURES),
                dtype=np.int32,
            ),
            "scalars": Box(
                low=-np.inf,
                high=np.inf,
                shape=(max_seq_len, SCALAR_DIM),
                dtype=np.float32,
            ),
            "attention_mask": Box(low=0, high=1, shape=(max_seq_len,), dtype=bool),
            "action_mask": Box(low=0, high=1, shape=(ACTION_DIM,), dtype=bool),
            "seq_len": Box(low=0, high=max_seq_len, shape=(), dtype=np.int32),
            "current_player": Box(low=0, high=3, shape=(), dtype=np.int32),
            "phase": Box(low=0, high=31, shape=(), dtype=np.int32),
        }
    )


def _resolve_action(env, action: int) -> int:
    """Translate a 54-action index into an engine ``make_selection`` index."""
    table = env._inner.t  # type: ignore[attr-defined]
    return ActionEncoder.unified_to_engine(table, action)

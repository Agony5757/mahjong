"""Modern Gymnasium environments using the tokenized encoding.

.. deprecated::
    Use :mod:`pymahjong.rl.envs` instead.  ``TokenizedMahjongEnv`` and
    ``TokenizedMultiAgentEnv`` are thin wrappers that delegate to
    :class:`~pymahjong.rl.envs.EncodingMahjongEnv` and
    :class:`~pymahjong.rl.envs.EncodingMultiAgentEnv` with ``encoding="v3"``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, Dict as DictSpace, Discrete

from .action_space import ActionEncoder, ACTION_DIM
from .tokenization import (
    MAX_SEQ_LEN,
    MahjongTokenizer,
    SCALAR_DIM,
    TOKEN_FEATURES,
    A_RIICHI,
    A_PASS_RIICHI,
)

try:  # pragma: no cover
    import MahjongPyWrapper as pm
except Exception:  # noqa: BLE001
    pm = None  # type: ignore


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


# ---------------------------------------------------------------------------
# Action translation: 54-action discrete → engine selection index
# ---------------------------------------------------------------------------

def _resolve_action(env, action: int) -> int:
    """Translate a 54-action index into an engine ``make_selection`` index.

    Delegates to :meth:`ActionEncoder.unified_to_engine` which uses
    centralized action encoding logic.
    """
    table = env._inner.t  # type: ignore[attr-defined]
    return ActionEncoder.unified_to_engine(table, action)


# ---------------------------------------------------------------------------
# Single-agent env (deprecated -- use EncodingMahjongEnv)
# ---------------------------------------------------------------------------

import warnings

from .envs import EncodingMahjongEnv, EncodingMultiAgentEnv


class TokenizedMahjongEnv(EncodingMahjongEnv):
    """Single-agent env with V3 tokenized observations.

    .. deprecated::
        Use ``EncodingMahjongEnv(encoding="v3")`` instead.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "TokenizedMahjongEnv is deprecated; use EncodingMahjongEnv(encoding='v3')",
            DeprecationWarning,
            stacklevel=2,
        )
        kwargs.setdefault("encoding", "v3")
        super().__init__(*args, **kwargs)


# ---------------------------------------------------------------------------
# Multi-agent env (deprecated -- use EncodingMultiAgentEnv)
# ---------------------------------------------------------------------------


class TokenizedMultiAgentEnv(EncodingMultiAgentEnv):
    """4-player self-play env with V3 tokenized observations.

    .. deprecated::
        Use ``EncodingMultiAgentEnv(encoding="v3")`` instead.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "TokenizedMultiAgentEnv is deprecated; use EncodingMultiAgentEnv(encoding='v3')",
            DeprecationWarning,
            stacklevel=2,
        )
        kwargs.setdefault("encoding", "v3")
        super().__init__(*args, **kwargs)

"""Modern Gymnasium environments using the tokenized encoding.

.. deprecated::
    Use :mod:`pymahjong.rl.envs` instead.  ``TokenizedMahjongEnv`` and
    ``TokenizedMultiAgentEnv`` are thin wrappers that delegate to
    :class:`~pymahjong.rl.envs.EncodingMahjongEnv` and
    :class:`~pymahjong.rl.envs.EncodingMultiAgentEnv` with ``encoding="v3"``.
"""

from __future__ import annotations

import warnings

# Re-export V3 helpers for backward compatibility.
from .v3.observation import _build_observation_space, _resolve_action  # noqa: F401

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

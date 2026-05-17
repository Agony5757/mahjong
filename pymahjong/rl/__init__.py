"""Modern Transformer-based RL stack for pymahjong.

This subpackage provides encoding-agnostic environments, training
utilities, and a strategy registry that lets you switch between V1-V4
observation encodings at runtime:

* :class:`EncodingVersion` -- enum of supported encodings.
* :func:`get_strategy` -- retrieve an :class:`EncodingStrategy` by version.
* :class:`EncodingMahjongEnv` / :class:`EncodingMultiAgentEnv` --
  encoding-agnostic gymnasium environments.
* :class:`ActionEncoder` -- unified 54-action space.
* :func:`train_bc`, :func:`train_ppo` -- top-level training entry points.

Legacy aliases are preserved for backward compatibility:
* :class:`TokenizedMahjongEnv` / :class:`TokenizedMultiAgentEnv`
* :class:`MahjongTokenizer`, :class:`MahjongTransformer`
"""

from .action_space import ActionEncoder, ACTION_DIM
from .encoding import EncodingVersion, get_strategy, available_versions
from .envs import EncodingMahjongEnv, EncodingMultiAgentEnv
from .v3.tokenization import (
    MahjongTokenizer,
    SegmentType,
    TILE_PAD,
    TILE_VOCAB_SIZE,
    NUM_SEGMENTS,
    MAX_SEQ_LEN,
    SCALAR_DIM,
    state_to_string,
    tokens_to_string,
)
from .env_v2 import TokenizedMahjongEnv, TokenizedMultiAgentEnv
from .v3.cache import (
    CACHE_SCHEMA_VERSION,
    CacheManifest,
    ShardWriter,
    load_manifest,
    rebuild_manifest,
    save_manifest,
)

# Trigger strategy registration.
from . import encodings  # noqa: F401

__all__ = [
    # Core API
    "EncodingVersion",
    "get_strategy",
    "available_versions",
    "EncodingMahjongEnv",
    "EncodingMultiAgentEnv",
    "ActionEncoder",
    "ACTION_DIM",
    # Tokenizer (V3)
    "MahjongTokenizer",
    "SegmentType",
    "TILE_PAD",
    "TILE_VOCAB_SIZE",
    "NUM_SEGMENTS",
    "MAX_SEQ_LEN",
    "SCALAR_DIM",
    "state_to_string",
    "tokens_to_string",
    # Legacy aliases
    "TokenizedMahjongEnv",
    "TokenizedMultiAgentEnv",
    # Cache
    "CACHE_SCHEMA_VERSION",
    "CacheManifest",
    "ShardWriter",
    "load_manifest",
    "rebuild_manifest",
    "save_manifest",
]


def _torch_only(name):
    def _factory(*args, **kwargs):
        try:
            import torch  # noqa: F401
        except ImportError as exc:  # pragma: no cover - import-time only
            raise ImportError(
                f"{name} requires PyTorch. Install with `pip install torch`."
            ) from exc
        if name == "MahjongTransformer":
            from .v3.model import MahjongTransformer
            return MahjongTransformer(*args, **kwargs)
        if name == "train_bc":
            from .bc import train_bc
            return train_bc(*args, **kwargs)
        if name == "train_ppo":
            from .ppo import train_ppo
            return train_ppo(*args, **kwargs)
        if name == "train_selfplay_v4":
            from .v4.selfplay import train_selfplay_v4
            return train_selfplay_v4(*args, **kwargs)
        raise AssertionError(f"unknown lazy target {name}")
    return _factory


MahjongTransformer = _torch_only("MahjongTransformer")
train_bc = _torch_only("train_bc")
train_ppo = _torch_only("train_ppo")
train_selfplay_v4 = _torch_only("train_selfplay_v4")

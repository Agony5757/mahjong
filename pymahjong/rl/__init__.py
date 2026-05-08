"""Modern Transformer-based RL stack for pymahjong.

This subpackage provides a fully Python-side, transformer-friendly
encoding of Mahjong game states + action spaces, a Gymnasium-compatible
environment exposing structured (Dict) observations, and two-stage
training utilities:

* Stage 1 (supervised): :mod:`pymahjong.rl.bc` — behavior cloning.
* Stage 2 (reinforcement): :mod:`pymahjong.rl.ppo` — masked PPO with
  multi-agent self-play.

Top-level imports:

* :class:`MahjongTokenizer` -- builds tokenized observations from the
  C++-engine ``pm.Table``.
* :class:`TokenizedMahjongEnv` -- single-agent gymnasium env.
* :class:`TokenizedMultiAgentEnv` -- 4-player multi-agent env wrapper.
* :class:`MahjongTransformer` -- transformer policy/value model (torch).
* :func:`train_bc`, :func:`train_ppo` -- top-level training entry points.

The encoding deliberately avoids depending on the C++ V1/V2 dense matrix
encoders (``encv1_*``, ``TableEncoder``) so that researchers can extend
the feature set in pure Python.
"""

from .tokenization import (
    MahjongTokenizer,
    SegmentType,
    TILE_PAD,
    TILE_VOCAB_SIZE,
    NUM_SEGMENTS,
    MAX_SEQ_LEN,
)
from .env_v2 import TokenizedMahjongEnv, TokenizedMultiAgentEnv
from .cache import (
    CACHE_SCHEMA_VERSION,
    CacheManifest,
    ShardWriter,
    load_manifest,
    rebuild_manifest,
    save_manifest,
)

__all__ = [
    "MahjongTokenizer",
    "SegmentType",
    "TILE_PAD",
    "TILE_VOCAB_SIZE",
    "NUM_SEGMENTS",
    "MAX_SEQ_LEN",
    "TokenizedMahjongEnv",
    "TokenizedMultiAgentEnv",
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
            from .model import MahjongTransformer
            return MahjongTransformer(*args, **kwargs)
        if name == "train_bc":
            from .bc import train_bc
            return train_bc(*args, **kwargs)
        if name == "train_ppo":
            from .ppo import train_ppo
            return train_ppo(*args, **kwargs)
        raise AssertionError(f"unknown lazy target {name}")
    return _factory


MahjongTransformer = _torch_only("MahjongTransformer")
train_bc = _torch_only("train_bc")
train_ppo = _torch_only("train_ppo")

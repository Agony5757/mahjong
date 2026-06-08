"""MajNova v0 — Transformer-based RL stack for pymahjong.

A flat, single-encoder training stack built around:

* :class:`ActionEncoder` — unified 54-action space.
* :class:`MultiAgentEnv` / :class:`HanchanEnv` — per-hand / per-hanchan
  Mahjong environments (event-stream observations).
* :class:`EventStreamTransformer` / :class:`DouzeroTransformer` —
  state encoder + Douzero per-legal-action scoring head.
* :class:`MortalQNet` — Mortal-style value learner reusing the same
  encoder; trained via :func:`train_mortal`.
* :func:`train_bc` — behavior cloning trainer (Douzero head, event cache).
* :class:`ShardWriter` / :class:`CachedEventDataset` — on-disk packbits
  shards and mmap-friendly map-style dataset.
* :class:`OpponentPool` — historical snapshot pool for self-play.

Torch-dependent symbols are lazily imported so the core engine remains
importable without PyTorch.
"""

from .action_space import ActionEncoder, ACTION_DIM
from ._manifest import (
    CacheManifest,
    ShardEntry,
    load_manifest,
    manifest_path,
    save_manifest,
)

__all__ = [
    # Core action space
    "ActionEncoder",
    "ACTION_DIM",
    # Cache I/O
    "CacheManifest",
    "ShardEntry",
    "load_manifest",
    "manifest_path",
    "save_manifest",
    # Lazy torch-only symbols (see __getattr__)
    "train_bc",
    "train_mortal",
    "EventStreamTransformer",
    "DouzeroTransformer",
    "MortalQNet",
    "MultiAgentEnv",
    "HanchanEnv",
    "LiveEncoder",
    "OpponentPool",
    "ShardWriter",
    "CachedEventDataset",
    "selfplay_eval",
]


_TORCH_LAZY_MAP = {
    "train_bc":              ("bc",            "train_bc"),
    "train_mortal":          ("mortal",        "train_mortal"),
    "EventStreamTransformer":("transformer",   "EventStreamTransformer"),
    "DouzeroTransformer":    ("douzero",       "DouzeroTransformer"),
    "MortalQNet":            ("mortal_qnet",   "MortalQNet"),
    "MultiAgentEnv":         ("env",           "MultiAgentEnv"),
    "HanchanEnv":            ("hanchan_env",   "HanchanEnv"),
    "LiveEncoder":           ("live_encoder",  "LiveEncoder"),
    "OpponentPool":          ("opponent_pool", "OpponentPool"),
    "ShardWriter":           ("cache",         "ShardWriter"),
    "CachedEventDataset":    ("cached_dataset","CachedEventDataset"),
    "selfplay_eval":         ("selfplay_eval", "selfplay_eval"),
}


def __getattr__(name):
    if name in _TORCH_LAZY_MAP:
        module_name, symbol = _TORCH_LAZY_MAP[name]
        try:
            import torch  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                f"pymahjong.rl.{name} requires PyTorch. "
                f"Install with `pip install torch`."
            ) from exc
        import importlib
        mod = importlib.import_module(f"pymahjong.rl.{module_name}")
        return getattr(mod, symbol)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

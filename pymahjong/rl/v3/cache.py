"""On-disk cache format for tokenized BC training data.

A cache directory looks like::

    cache_dir/
        index.json              # global manifest
        shard_00000/
            tokens.npy          # (N, L, 5) uint8
            attention_mask.npy  # (N, L)    uint8 (0/1)
            action_mask.npy     # (N, A)    uint8 (0/1)
            labels.npy          # (N,)      int16
            meta.json           # per-shard metadata
        shard_00001/
            ...

All numpy arrays are saved with ``np.save`` so they can be opened
zero-copy via ``np.load(..., mmap_mode='r')``. Field values are bounded
by :data:`pymahjong.rl.tokenization.FIELD_VOCAB` (all <= 256), so
``uint8`` is sufficient. Labels (engine 54-action indices) fit easily in
``int16``.

The manifest contains a tokenizer "schema fingerprint" that downstream
loaders **must** check against the live :mod:`pymahjong.rl.tokenization`
to refuse silently-incompatible caches.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

import numpy as np

from .tokenization import (
    ACTION_DIM,
    FIELD_VOCAB,
    MAX_SEQ_LEN,
    SCALAR_DIM,
    TOKEN_FEATURES,
)

# Bump whenever the tokenizer output layout changes in a way that
# invalidates previously written caches.
CACHE_SCHEMA_VERSION = 3


# ---------------------------------------------------------------------------
# Schema fingerprint
# ---------------------------------------------------------------------------


def schema_fingerprint(max_seq_len: int = MAX_SEQ_LEN) -> Dict:
    """Return a dict that uniquely identifies the on-wire cache layout."""
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "max_seq_len": int(max_seq_len),
        "token_features": int(TOKEN_FEATURES),
        "scalar_dim": int(SCALAR_DIM),
        "action_dim": int(ACTION_DIM),
        "field_vocab": {k: int(v) for k, v in FIELD_VOCAB.items()},
        "dtypes": {
            "tokens": "uint8",
            "scalars": "float32",
            "attention_mask": "uint8",
            "action_mask": "uint8",
            "labels": "int16",
        },
    }


def assert_schema_compatible(loaded: Dict, max_seq_len: int = MAX_SEQ_LEN) -> None:
    """Raise ValueError if a cache's manifest does not match the current code."""
    expected = schema_fingerprint(max_seq_len)
    for key in (
        "schema_version", "token_features", "scalar_dim",
        "action_dim", "field_vocab", "dtypes",
    ):
        if loaded.get(key) != expected[key]:
            raise ValueError(
                f"cache schema mismatch on '{key}': "
                f"cache={loaded.get(key)!r} code={expected[key]!r}. "
                "Re-encode the cache with the current tokenizer."
            )
    if loaded.get("max_seq_len", expected["max_seq_len"]) > expected["max_seq_len"]:
        raise ValueError(
            f"cache max_seq_len={loaded.get('max_seq_len')} > "
            f"current max_seq_len={expected['max_seq_len']}"
        )


# ---------------------------------------------------------------------------
# Manifest dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ShardEntry:
    path: str            # relative to cache_dir
    n_rows: int
    cumulative: int      # cumulative row count *including* this shard


@dataclass
class CacheManifest:
    schema: Dict
    total_rows: int
    shards: List[ShardEntry]

    def to_dict(self) -> Dict:
        return {
            "schema": self.schema,
            "total_rows": int(self.total_rows),
            "shards": [asdict(s) for s in self.shards],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CacheManifest":
        return cls(
            schema=d["schema"],
            total_rows=int(d["total_rows"]),
            shards=[ShardEntry(**s) for s in d["shards"]],
        )


def manifest_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "index.json")


def load_manifest(cache_dir: str) -> CacheManifest:
    with open(manifest_path(cache_dir), "r") as f:
        return CacheManifest.from_dict(json.load(f))


def save_manifest(cache_dir: str, manifest: CacheManifest) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    tmp = manifest_path(cache_dir) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    os.replace(tmp, manifest_path(cache_dir))


# ---------------------------------------------------------------------------
# Shard writer
# ---------------------------------------------------------------------------


class ShardWriter:
    """Buffered writer for one shard.

    Use as a context manager. ``add(sample)`` accepts dicts with the
    same keys as the tokenizer output. Call :meth:`close` (or exit the
    context) to flush to disk and return a :class:`ShardEntry` (with
    ``cumulative=0``; the caller is responsible for filling it in).
    """

    def __init__(self, shard_dir: str, max_seq_len: int = MAX_SEQ_LEN):
        self.shard_dir = shard_dir
        self.max_seq_len = int(max_seq_len)
        self._tokens: List[np.ndarray] = []
        self._scalars: List[np.ndarray] = []
        self._attn: List[np.ndarray] = []
        self._amask: List[np.ndarray] = []
        self._labels: List[int] = []

    def __enter__(self) -> "ShardWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()

    @property
    def n_rows(self) -> int:
        return len(self._labels)

    def add(self, sample: Dict) -> None:
        tokens = np.asarray(sample["tokens"])
        scalars = np.asarray(sample["scalars"])
        attn = np.asarray(sample["attention_mask"])
        amask = np.asarray(sample["action_mask"])
        if tokens.shape != (self.max_seq_len, TOKEN_FEATURES):
            raise ValueError(
                f"tokens shape {tokens.shape} != "
                f"({self.max_seq_len}, {TOKEN_FEATURES})"
            )
        if scalars.shape != (self.max_seq_len, SCALAR_DIM):
            raise ValueError(
                f"scalars shape {scalars.shape} != "
                f"({self.max_seq_len}, {SCALAR_DIM})"
            )
        if attn.shape != (self.max_seq_len,):
            raise ValueError(f"attention_mask shape {attn.shape}")
        if amask.shape != (ACTION_DIM,):
            raise ValueError(f"action_mask shape {amask.shape}")
        if tokens.min() < 0 or tokens.max() > 255:
            raise ValueError("token value out of uint8 range")
        self._tokens.append(tokens.astype(np.uint8, copy=True))
        self._scalars.append(scalars.astype(np.float32, copy=True))
        self._attn.append(attn.astype(np.uint8, copy=True))
        self._amask.append(amask.astype(np.uint8, copy=True))
        self._labels.append(int(sample["action"]))

    def close(self) -> ShardEntry:
        if self.n_rows == 0:
            return ShardEntry(path=os.path.basename(self.shard_dir), n_rows=0, cumulative=0)
        os.makedirs(self.shard_dir, exist_ok=True)
        tokens = np.stack(self._tokens, axis=0)
        scalars = np.stack(self._scalars, axis=0)
        attn = np.stack(self._attn, axis=0)
        amask = np.stack(self._amask, axis=0)
        labels = np.asarray(self._labels, dtype=np.int16)

        np.save(os.path.join(self.shard_dir, "tokens.npy"), tokens)
        np.save(os.path.join(self.shard_dir, "scalars.npy"), scalars)
        np.save(os.path.join(self.shard_dir, "attention_mask.npy"), attn)
        np.save(os.path.join(self.shard_dir, "action_mask.npy"), amask)
        np.save(os.path.join(self.shard_dir, "labels.npy"), labels)

        meta = {
            "n_rows": int(self.n_rows),
            "max_seq_len": int(self.max_seq_len),
            "schema_version": CACHE_SCHEMA_VERSION,
        }
        with open(os.path.join(self.shard_dir, "meta.json"), "w") as f:
            json.dump(meta, f)

        self._tokens.clear()
        self._scalars.clear()
        self._attn.clear()
        self._amask.clear()
        self._labels.clear()

        return ShardEntry(
            path=os.path.basename(self.shard_dir),
            n_rows=int(tokens.shape[0]),
            cumulative=0,
        )


# ---------------------------------------------------------------------------
# Manifest helpers (post-hoc rebuild from disk)
# ---------------------------------------------------------------------------


def rebuild_manifest(
    cache_dir: str,
    max_seq_len: int = MAX_SEQ_LEN,
    schema_fn=None,
) -> CacheManifest:
    """Scan ``cache_dir`` for ``shard_*`` directories and rewrite ``index.json``.

    Useful after parallel writers have produced shards independently.

    Args:
        cache_dir: path to the cache root.
        max_seq_len: forwarded to the default ``schema_fingerprint``.
        schema_fn: optional callable returning the schema dict.  Defaults
            to ``schema_fingerprint(max_seq_len)`` (V3).  V4 callers
            pass their own ``schema_fingerprint``.
    """
    entries: List[ShardEntry] = []
    cum = 0
    for name in sorted(os.listdir(cache_dir)):
        sub = os.path.join(cache_dir, name)
        if not (name.startswith("shard_") and os.path.isdir(sub)):
            continue
        try:
            with open(os.path.join(sub, "meta.json")) as f:
                m = json.load(f)
        except FileNotFoundError:
            continue
        n = int(m.get("n_rows", 0))
        if n <= 0:
            continue
        cum += n
        entries.append(ShardEntry(path=name, n_rows=n, cumulative=cum))

    if schema_fn is not None:
        schema = schema_fn()
    else:
        schema = schema_fingerprint(max_seq_len)

    manifest = CacheManifest(
        schema=schema,
        total_rows=cum,
        shards=entries,
    )
    save_manifest(cache_dir, manifest)
    return manifest


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------


def open_shard_arrays(cache_dir: str, shard_path: str) -> Dict[str, np.ndarray]:
    """Open a shard's arrays as memory-mapped read-only numpy views."""
    sub = os.path.join(cache_dir, shard_path)
    return {
        "tokens": np.load(os.path.join(sub, "tokens.npy"), mmap_mode="r"),
        "scalars": np.load(os.path.join(sub, "scalars.npy"), mmap_mode="r"),
        "attention_mask": np.load(
            os.path.join(sub, "attention_mask.npy"), mmap_mode="r"
        ),
        "action_mask": np.load(
            os.path.join(sub, "action_mask.npy"), mmap_mode="r"
        ),
        "labels": np.load(os.path.join(sub, "labels.npy"), mmap_mode="r"),
    }


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "CacheManifest",
    "ShardEntry",
    "ShardWriter",
    "schema_fingerprint",
    "assert_schema_compatible",
    "load_manifest",
    "save_manifest",
    "rebuild_manifest",
    "open_shard_arrays",
    "manifest_path",
]

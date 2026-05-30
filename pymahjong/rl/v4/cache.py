"""On-disk cache for V4 autoregressive event-stream encoded samples.

A cache directory looks like::

    cache_dir/
        index.json              # manifest
        shard_00000/
            features.packbits.npy  # (N_total_events, ceil(EVENT_DIM/8)) uint8
            lengths.npy            # (N_samples,) int32
            action_mask.packbits.npy  # (N_samples, ceil(54/8)) uint8
            labels.npy             # (N_samples,)  int16
            track_ids.npy          # (N_samples,)  int64
            meta.json
        shard_00001/
            ...

Features for all samples in a shard are concatenated into a single flat
array along axis 0, with ``lengths.npy`` recording the per-sample event
count.  Bool arrays (features, action_mask) are packed with ``np.packbits``
to save 8x disk space; ``open_shard_arrays_v4`` transparently unpacks them.
Original (unpacked) shapes are stored in ``meta.json["packed"]``.

Loading uses ``np.load(..., mmap_mode='r')`` for zero-copy access.
Individual samples are sliced out via cumulative-sum indexing over
``lengths``.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import numpy as np

from ..v3.cache import (
    CacheManifest,
    ShardEntry,
    load_manifest,
    manifest_path,
    save_manifest,
    rebuild_manifest as _rebuild_base,
)
from .tokenization import EVENT_DIM

CACHE_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Packbits helpers
# ---------------------------------------------------------------------------


def pack_bool(arr: np.ndarray) -> np.ndarray:
    """Pack a bool array into uint8 via ``np.packbits`` (last axis)."""
    return np.packbits(arr, axis=-1)


def unpack_bool(packed: np.ndarray, orig_shape: tuple) -> np.ndarray:
    """Reverse ``np.packbits`` and truncate to *orig_shape*."""
    flat = np.unpackbits(packed, axis=-1)
    # orig_shape[1] may not be a multiple of 8; unpackbits pads with zeros
    return flat[..., : orig_shape[1]].reshape(orig_shape).astype(np.bool_)


class _LazyUnpackedArray:
    """Mmap-backed packbits array with on-demand per-row unpacking.

    Behaves like a 2-D bool array of shape ``orig_shape`` but only
    materializes the bits that are actually indexed. Required because
    a fully-unpacked shard for a big month would be tens of GiB.
    """

    __slots__ = ("_packed", "_orig_shape")

    def __init__(self, packed: np.ndarray, orig_shape: tuple):
        self._packed = packed
        self._orig_shape = tuple(orig_shape)

    @property
    def shape(self) -> tuple:
        return self._orig_shape

    @property
    def dtype(self):
        return np.dtype(np.bool_)

    def __len__(self) -> int:
        return self._orig_shape[0]

    def __getitem__(self, key):
        # Slice the packed bytes along axis 0, then unpack & truncate.
        sub = self._packed[key]
        if sub.ndim == 1:
            # Single row -> shape (1-D,) after slice. Unpack and trim.
            bits = np.unpackbits(sub, axis=-1)
            return bits[: self._orig_shape[1]].astype(np.bool_)
        n = sub.shape[0]
        bits = np.unpackbits(sub, axis=-1)
        return bits[..., : self._orig_shape[1]].reshape(
            n, self._orig_shape[1]
        ).astype(np.bool_)


def schema_fingerprint() -> Dict:
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "event_dim": int(EVENT_DIM),
        "action_dim": 54,
    }


def assert_schema_compatible(loaded: Dict) -> None:
    expected = schema_fingerprint()
    for key in ("schema_version", "event_dim", "action_dim"):
        if loaded.get(key) != expected[key]:
            raise ValueError(
                f"V4 cache schema mismatch on '{key}': "
                f"cache={loaded.get(key)!r} code={expected[key]!r}"
            )


# Manifest helpers are imported from cache.py (ShardEntry, CacheManifest,
# manifest_path, load_manifest, save_manifest).


# ---------------------------------------------------------------------------
# Shard writer
# ---------------------------------------------------------------------------


class V4ShardWriter:
    """Buffered writer for one V4 shard.

    Accepts variable-length sample dicts from ``encode_paipu_file_v4``.
    Features are accumulated per-sample and concatenated on flush.
    """

    def __init__(self, shard_dir: str):
        self.shard_dir = shard_dir
        self._features: List[np.ndarray] = []
        self._action_masks: List[np.ndarray] = []
        self._labels: List[int] = []
        self._track_ids: List[int] = []
        self._game_ids: List[int] = []

    def __enter__(self) -> "V4ShardWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()

    @property
    def n_rows(self) -> int:
        return len(self._labels)

    def add(self, sample: Dict) -> None:
        feat = np.asarray(sample["features"])
        amask = np.asarray(sample["action_mask"])
        assert feat.ndim == 2 and feat.shape[1] == EVENT_DIM, \
            f"features shape {feat.shape}, expected (*, {EVENT_DIM})"
        assert amask.shape == (54,), f"action_mask shape {amask.shape}"
        self._features.append(feat.astype(np.bool_, copy=True))
        self._action_masks.append(amask.astype(np.bool_, copy=True))
        self._labels.append(int(sample["action"]))
        self._track_ids.append(int(sample["track_id"]))
        # Backward-compat: fall back to track_id when game_id isn't supplied
        # so older sample producers still work (game_id will then mix games).
        self._game_ids.append(int(sample.get("game_id", sample["track_id"])))

    def close(self) -> ShardEntry:
        if self.n_rows == 0:
            return ShardEntry(
                path=os.path.basename(self.shard_dir), n_rows=0, cumulative=0
            )
        os.makedirs(self.shard_dir, exist_ok=True)

        # Snapshot the count before we clear the buffers — the returned
        # ShardEntry must reflect what was actually written.
        n_rows_written = self.n_rows

        features = np.concatenate(self._features, axis=0)
        lengths = np.array([f.shape[0] for f in self._features], dtype=np.int32)
        action_masks = np.stack(self._action_masks, axis=0)
        labels = np.asarray(self._labels, dtype=np.int16)
        track_ids = np.asarray(self._track_ids, dtype=np.int64)
        game_ids = np.asarray(self._game_ids, dtype=np.int64)

        np.save(os.path.join(self.shard_dir, "features.packbits.npy"),
                pack_bool(features))
        np.save(os.path.join(self.shard_dir, "lengths.npy"), lengths)
        np.save(os.path.join(self.shard_dir, "action_mask.packbits.npy"),
                pack_bool(action_masks))
        np.save(os.path.join(self.shard_dir, "labels.npy"), labels)
        np.save(os.path.join(self.shard_dir, "track_ids.npy"), track_ids)
        np.save(os.path.join(self.shard_dir, "game_ids.npy"), game_ids)

        meta = {
            "n_rows": int(n_rows_written),
            "schema_version": CACHE_SCHEMA_VERSION,
            "total_events": int(features.shape[0]),
            "packed": {
                "features.orig_shape": list(features.shape),
                "action_mask.orig_shape": list(action_masks.shape),
            },
        }
        with open(os.path.join(self.shard_dir, "meta.json"), "w") as f:
            json.dump(meta, f)

        self._features.clear()
        self._action_masks.clear()
        self._labels.clear()
        self._track_ids.clear()
        self._game_ids.clear()

        return ShardEntry(
            path=os.path.basename(self.shard_dir),
            n_rows=int(n_rows_written),
            cumulative=0,
        )


# ---------------------------------------------------------------------------
# Rebuild manifest from disk
# ---------------------------------------------------------------------------


def rebuild_manifest(cache_dir: str) -> CacheManifest:
    """Rebuild V4 manifest, delegating to the shared implementation."""
    return _rebuild_base(cache_dir, schema_fn=schema_fingerprint)


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------


def open_shard_arrays_v4(cache_dir: str, shard_path: str) -> Dict[str, np.ndarray]:
    """Load all shard arrays, lazily unpacking packbits files per-row.

    Unpacked features for big shards (e.g. 8.76M rows × 469M events)
    can exceed 40 GiB, so packed mmaps are wrapped in
    :class:`_LazyUnpackedArray` and only the slice you index is unpacked.
    """
    sub = os.path.join(cache_dir, shard_path)

    with open(os.path.join(sub, "meta.json")) as f:
        meta = json.load(f)
    packed = meta.get("packed", {})

    def _load_bool(raw_name: str, packed_name: str, orig_key: str):
        pk_path = os.path.join(sub, packed_name)
        if os.path.exists(pk_path):
            return _LazyUnpackedArray(
                np.load(pk_path, mmap_mode="r"),
                tuple(packed[orig_key]),
            )
        return np.load(os.path.join(sub, raw_name), mmap_mode="r")

    return {
        "features":    _load_bool("features.npy",    "features.packbits.npy",
                                  "features.orig_shape"),
        "action_mask": _load_bool("action_mask.npy", "action_mask.packbits.npy",
                                  "action_mask.orig_shape"),
        "lengths":     np.load(os.path.join(sub, "lengths.npy"),     mmap_mode="r"),
        "labels":      np.load(os.path.join(sub, "labels.npy"),      mmap_mode="r"),
        "track_ids":   np.load(os.path.join(sub, "track_ids.npy"),   mmap_mode="r"),
        # ``game_ids.npy`` was added later (May 2026) to support
        # game-level splits without cross-seat leakage. Old shards lack
        # this file → fall back to track_ids so callers can still load.
        "game_ids":    (np.load(os.path.join(sub, "game_ids.npy"), mmap_mode="r")
                        if os.path.exists(os.path.join(sub, "game_ids.npy"))
                        else np.load(os.path.join(sub, "track_ids.npy"), mmap_mode="r")),
    }


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "CacheManifest",
    "ShardEntry",
    "V4ShardWriter",
    "pack_bool",
    "unpack_bool",
    "schema_fingerprint",
    "assert_schema_compatible",
    "load_manifest",
    "save_manifest",
    "rebuild_manifest",
    "open_shard_arrays_v4",
    "manifest_path",
]

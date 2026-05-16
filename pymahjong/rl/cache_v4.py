"""On-disk cache for V4 autoregressive event-stream encoded samples.

A cache directory looks like::

    cache_dir/
        index.json              # manifest
        shard_00000/
            features.npy        # (N_total_events, EVENT_DIM) bool — concatenated
            lengths.npy         # (N_samples,) int32 — event count per sample
            action_mask.npy     # (N_samples, 54)     bool
            labels.npy          # (N_samples,)         int16
            track_ids.npy       # (N_samples,)         int64
            meta.json
        shard_00001/
            ...

Features for all samples in a shard are concatenated into a single flat
array along axis 0, with ``lengths.npy`` recording the per-sample event
count.  This avoids the massive memory waste of padding variable-length
sequences to a fixed max length.

Loading uses ``np.load(..., mmap_mode='r')`` for zero-copy access.
Individual samples are sliced out via cumulative-sum indexing over
``lengths``.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

import numpy as np

from .tokenization_v4 import EVENT_DIM

CACHE_SCHEMA_VERSION = 1


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


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass
class ShardEntry:
    path: str
    n_rows: int
    cumulative: int


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

    def close(self) -> ShardEntry:
        if self.n_rows == 0:
            return ShardEntry(
                path=os.path.basename(self.shard_dir), n_rows=0, cumulative=0
            )
        os.makedirs(self.shard_dir, exist_ok=True)

        features = np.concatenate(self._features, axis=0)
        lengths = np.array([f.shape[0] for f in self._features], dtype=np.int32)
        action_masks = np.stack(self._action_masks, axis=0)
        labels = np.asarray(self._labels, dtype=np.int16)
        track_ids = np.asarray(self._track_ids, dtype=np.int64)

        np.save(os.path.join(self.shard_dir, "features.npy"), features)
        np.save(os.path.join(self.shard_dir, "lengths.npy"), lengths)
        np.save(os.path.join(self.shard_dir, "action_mask.npy"), action_masks)
        np.save(os.path.join(self.shard_dir, "labels.npy"), labels)
        np.save(os.path.join(self.shard_dir, "track_ids.npy"), track_ids)

        meta = {
            "n_rows": int(self.n_rows),
            "schema_version": CACHE_SCHEMA_VERSION,
            "total_events": int(features.shape[0]),
        }
        with open(os.path.join(self.shard_dir, "meta.json"), "w") as f:
            json.dump(meta, f)

        self._features.clear()
        self._action_masks.clear()
        self._labels.clear()
        self._track_ids.clear()

        return ShardEntry(
            path=os.path.basename(self.shard_dir),
            n_rows=int(self.n_rows),
            cumulative=0,
        )


# ---------------------------------------------------------------------------
# Rebuild manifest from disk
# ---------------------------------------------------------------------------


def rebuild_manifest(cache_dir: str) -> CacheManifest:
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

    manifest = CacheManifest(
        schema=schema_fingerprint(),
        total_rows=cum,
        shards=entries,
    )
    save_manifest(cache_dir, manifest)
    return manifest


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------


def open_shard_arrays_v4(cache_dir: str, shard_path: str) -> Dict[str, np.ndarray]:
    sub = os.path.join(cache_dir, shard_path)
    return {
        "features": np.load(os.path.join(sub, "features.npy"), mmap_mode="r"),
        "lengths": np.load(os.path.join(sub, "lengths.npy"), mmap_mode="r"),
        "action_mask": np.load(os.path.join(sub, "action_mask.npy"), mmap_mode="r"),
        "labels": np.load(os.path.join(sub, "labels.npy"), mmap_mode="r"),
        "track_ids": np.load(os.path.join(sub, "track_ids.npy"), mmap_mode="r"),
    }


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "CacheManifest",
    "ShardEntry",
    "V4ShardWriter",
    "schema_fingerprint",
    "assert_schema_compatible",
    "load_manifest",
    "save_manifest",
    "rebuild_manifest",
    "open_shard_arrays_v4",
    "manifest_path",
]

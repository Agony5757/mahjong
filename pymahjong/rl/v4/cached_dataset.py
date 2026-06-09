"""Map-style :class:`torch.utils.data.Dataset` over a V4 on-disk cache.

V4 caches store variable-length event-stream features with packbits
compression.  Unlike V3 (fixed-length token sequences), V4 features
are concatenated into a flat array with a per-sample ``lengths`` array
for random access via cumulative-sum indexing.
"""

from __future__ import annotations

import bisect
import os
from typing import Dict, List

import numpy as np
import torch
from torch.utils.data import Dataset

from .cache import (
    CacheManifest,
    assert_schema_compatible,
    load_manifest,
    open_shard_arrays_v4,
)


class CachedEventDataset(Dataset):
    """Random-access dataset over a V4 packbits cache directory.

    Args:
        cache_dir: directory written by
            :class:`pymahjong.rl.cache_v4.V4ShardWriter`
            (must contain ``index.json``).
    """

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir

        manifest: CacheManifest = load_manifest(cache_dir)
        assert_schema_compatible(manifest.schema)

        self._shards: List[str] = [s.path for s in manifest.shards if s.n_rows > 0]
        self._cum: List[int] = [s.cumulative for s in manifest.shards if s.n_rows > 0]
        self._n_rows: List[int] = [s.n_rows for s in manifest.shards if s.n_rows > 0]
        self._total = int(manifest.total_rows)

        # Per-worker shard arrays (lazy open).
        self._open: Dict[int, Dict[str, np.ndarray]] = {}

    def __len__(self) -> int:
        return self._total

    # ------------------------------------------------------------------ I/O

    def _arrays_for(self, shard_idx: int) -> Dict[str, np.ndarray]:
        cached = self._open.get(shard_idx)
        if cached is None:
            cached = open_shard_arrays_v4(self.cache_dir, self._shards[shard_idx])
            # Pre-compute event-offset table so per-sample indexing is O(1).
            lengths = np.asarray(cached["lengths"], dtype=np.int64)
            offsets = np.empty(lengths.shape[0] + 1, dtype=np.int64)
            offsets[0] = 0
            np.cumsum(lengths, out=offsets[1:])
            cached["_event_offsets"] = offsets
            self._open[shard_idx] = cached
        return cached

    def _locate(self, idx: int):
        if idx < 0:
            idx += self._total
        if idx < 0 or idx >= self._total:
            raise IndexError(idx)
        shard_idx = bisect.bisect_right(self._cum, idx)
        prev_cum = self._cum[shard_idx - 1] if shard_idx > 0 else 0
        local = idx - prev_cum
        return shard_idx, local

    # ------------------------------------------------------------ getitem

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        shard_idx, local = self._locate(idx)
        arrays = self._arrays_for(shard_idx)

        offsets = arrays["_event_offsets"]
        event_start = int(offsets[local])
        event_end = int(offsets[local + 1])

        features = np.asarray(
            arrays["features"][event_start:event_end], dtype=np.bool_
        )
        amask = np.asarray(arrays["action_mask"][local], dtype=np.bool_)
        label = int(arrays["labels"][local])

        seq_len = features.shape[0]

        out = {
            "features": torch.from_numpy(np.ascontiguousarray(features)),
            "attention_mask": torch.ones(seq_len, dtype=torch.bool),
            "action_mask": torch.from_numpy(np.ascontiguousarray(amask)),
            "action": torch.tensor(label, dtype=torch.long),
            "seq_len": torch.tensor(seq_len, dtype=torch.long),
        }
        # Mortal offline-RL targets, when the cache was built with them.
        if arrays.get("rewards") is not None:
            out["q_reward"] = torch.tensor(float(arrays["rewards"][local]), dtype=torch.float32)
            out["player_rank"] = torch.tensor(int(arrays["ranks"][local]), dtype=torch.long)
            out["steps_to_done"] = torch.tensor(int(arrays["steps_to_done"][local]), dtype=torch.long)
        return out


def cached_event_collate(batch):
    """Collate variable-length V4 samples by padding to max seq_len."""
    max_len = max(int(b["seq_len"]) for b in batch)
    event_dim = batch[0]["features"].shape[1]

    B = len(batch)
    features = torch.zeros(B, max_len, event_dim, dtype=torch.bool)
    attention_mask = torch.zeros(B, max_len, dtype=torch.bool)

    for i, b in enumerate(batch):
        L = int(b["seq_len"])
        features[i, :L] = b["features"]
        attention_mask[i, :L] = b["attention_mask"]

    out = {
        "features": features,
        "attention_mask": attention_mask,
        "action_mask": torch.stack([b["action_mask"] for b in batch], dim=0),
        "action": torch.stack([b["action"] for b in batch], dim=0),
    }
    if "q_reward" in batch[0]:
        out["q_reward"] = torch.stack([b["q_reward"] for b in batch], dim=0)
        out["player_rank"] = torch.stack([b["player_rank"] for b in batch], dim=0)
        out["steps_to_done"] = torch.stack([b["steps_to_done"] for b in batch], dim=0)
    return out


__all__ = ["CachedEventDataset", "cached_event_collate"]

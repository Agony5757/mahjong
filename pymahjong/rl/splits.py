"""Train/val/test splits for V4 cached datasets.

Two strategies are provided:

* :func:`split_by_shard` — assign whole shards to train/val/test. With
  per-month shards this is a time-based split: train on past months,
  validate / test on later months. **No** game-level leakage possible.
* :func:`split_by_track_id` — split samples uniformly by hashing their
  ``track_id``. Easy to use, but the same game's four player tracks
  have different ``track_id``s so a fraction of cross-seat leakage is
  unavoidable. Prefer :func:`split_by_shard` when shard layout allows.

Both return lightweight :class:`Subset`-style wrappers that share the
same underlying mmap'd cache (no data copying).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset

from .cache import CacheManifest, load_manifest, open_shard_arrays_v4
from .cached_dataset import CachedEventDataset


class _SubsetDataset(Dataset):
    """Map-style view over a CachedEventDataset using an explicit index array."""

    def __init__(self, base: CachedEventDataset, indices: np.ndarray, name: str = ""):
        if indices.dtype != np.int64:
            indices = indices.astype(np.int64, copy=False)
        self._base = base
        self._indices = indices
        self.name = name

    def __len__(self) -> int:
        return int(self._indices.shape[0])

    def __getitem__(self, idx: int):
        return self._base[int(self._indices[idx])]


@dataclass
class SplitResult:
    train: _SubsetDataset
    val: _SubsetDataset
    test: _SubsetDataset

    def __iter__(self):
        return iter((self.train, self.val, self.test))

    def summary(self) -> str:
        return (f"train={len(self.train):,}  "
                f"val={len(self.val):,}  "
                f"test={len(self.test):,}")


# ---------------------------------------------------------------------------
# Shard-based split (recommended)
# ---------------------------------------------------------------------------


def _shard_offsets(base: CachedEventDataset) -> List[Tuple[str, int, int]]:
    """Return ``[(shard_name, start_idx, end_idx_exclusive), ...]``."""
    out: List[Tuple[str, int, int]] = []
    prev = 0
    for name, n_rows, cum in zip(base._shards, base._n_rows, base._cum):
        out.append((name, prev, cum))
        prev = cum
    return out


def split_by_shard(
    base: CachedEventDataset,
    train_shards: Sequence[str],
    val_shards: Sequence[str],
    test_shards: Sequence[str],
) -> SplitResult:
    """Build train/val/test by listing which shards go where.

    Shard names should match what was written on disk (typically
    ``shard_YYYYMM``). Any shard not mentioned in any of the three
    lists is silently excluded — useful for excluding small or
    suspect months without re-encoding.

    Raises ValueError if a name appears in more than one list, or
    references a shard not present in the cache manifest.
    """
    available = {s.path for s in load_manifest(base.cache_dir).shards
                 if s.n_rows > 0}

    train_set = set(train_shards)
    val_set = set(val_shards)
    test_set = set(test_shards)
    overlap = (train_set & val_set) | (train_set & test_set) | (val_set & test_set)
    if overlap:
        raise ValueError(f"shards appear in multiple splits: {sorted(overlap)}")
    unknown = (train_set | val_set | test_set) - available
    if unknown:
        raise ValueError(
            f"unknown shards: {sorted(unknown)}; available: {sorted(available)}"
        )

    offsets = _shard_offsets(base)

    def _idx_for(want: set) -> np.ndarray:
        parts = []
        for name, start, end in offsets:
            if name in want:
                parts.append(np.arange(start, end, dtype=np.int64))
        return np.concatenate(parts) if parts else np.empty(0, dtype=np.int64)

    return SplitResult(
        train=_SubsetDataset(base, _idx_for(train_set), name="train"),
        val=_SubsetDataset(base, _idx_for(val_set), name="val"),
        test=_SubsetDataset(base, _idx_for(test_set), name="test"),
    )


# ---------------------------------------------------------------------------
# Hash-based split (random but deterministic)
# ---------------------------------------------------------------------------


def _all_track_ids(base: CachedEventDataset) -> np.ndarray:
    """Concatenate per-shard track_ids into one ``int64`` array of length len(base)."""
    parts = []
    for shard in base._shards:
        arr = open_shard_arrays_v4(base.cache_dir, shard)
        parts.append(np.asarray(arr["track_ids"], dtype=np.int64))
    return np.concatenate(parts, axis=0) if parts else np.empty(0, dtype=np.int64)


def _all_game_ids(base: CachedEventDataset) -> np.ndarray:
    """Concatenate per-shard game_ids into one ``int64`` array of length len(base).

    Older shards (pre-May-2026) that lack ``game_ids.npy`` are silently
    backfilled with ``track_ids`` by :func:`open_shard_arrays_v4`, in which
    case :func:`split_by_game_id` degrades to :func:`split_by_track_id`.
    """
    parts = []
    for shard in base._shards:
        arr = open_shard_arrays_v4(base.cache_dir, shard)
        parts.append(np.asarray(arr["game_ids"], dtype=np.int64))
    return np.concatenate(parts, axis=0) if parts else np.empty(0, dtype=np.int64)


def _splitmix_to_unit(values: np.ndarray, seed: int) -> np.ndarray:
    """Map int64 ids to deterministic uniform [0, 1) floats via splitmix64."""
    mixed = (values ^ np.int64(seed)).astype(np.uint64)
    h = mixed ^ (mixed >> np.uint64(30))
    h = (h * np.uint64(0xBF58476D1CE4E5B9)) & np.uint64((1 << 64) - 1)
    h ^= h >> np.uint64(27)
    h = (h * np.uint64(0x94D049BB133111EB)) & np.uint64((1 << 64) - 1)
    h ^= h >> np.uint64(31)
    return (h / np.float64(1 << 64)).astype(np.float64)


def split_by_track_id(
    base: CachedEventDataset,
    ratios: Tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
) -> SplitResult:
    """Split samples deterministically by hashing ``track_id``.

    Same ``track_id`` → always lands in the same split. Stratified by
    ratios via a hash bucket in [0, 1).

    Warning: samples encoded from the same (game, hand) but different
    player seats have *different* ``track_id``s, so this split allows
    a small amount of cross-seat leakage. Prefer
    :func:`split_by_game_id` (no cross-seat leak) or
    :func:`split_by_shard` (no leak at all) when possible.
    """
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"ratios must sum to 1.0, got {ratios}")
    if any(r < 0 for r in ratios):
        raise ValueError(f"ratios must be non-negative, got {ratios}")
    r_train, r_val, _r_test = ratios
    boundary_train = r_train
    boundary_val = r_train + r_val

    track_ids = _all_track_ids(base)
    frac = _splitmix_to_unit(track_ids, seed)

    train_mask = frac < boundary_train
    val_mask = (frac >= boundary_train) & (frac < boundary_val)
    test_mask = frac >= boundary_val

    all_idx = np.arange(len(base), dtype=np.int64)
    return SplitResult(
        train=_SubsetDataset(base, all_idx[train_mask], name="train"),
        val=_SubsetDataset(base, all_idx[val_mask], name="val"),
        test=_SubsetDataset(base, all_idx[test_mask], name="test"),
    )


def split_by_game_id(
    base: CachedEventDataset,
    ratios: Tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
) -> SplitResult:
    """Split samples by hashing ``game_id`` (paipu file stem).

    All four seats × all hands × all decision points belonging to the
    same hanchan land in the **same** split. This eliminates the
    cross-seat leakage that :func:`split_by_track_id` allows, where
    four players in one game share wall tiles / dora indicators / dice /
    hand context but get distinct ``track_id`` s.

    Requires shards written by post-May-2026 :class:`ShardWriter`
    which persist ``game_ids.npy``.  Older shards transparently fall
    back to ``track_ids`` (see :func:`_all_game_ids`), so on legacy
    caches this function silently behaves like :func:`split_by_track_id`.
    """
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"ratios must sum to 1.0, got {ratios}")
    if any(r < 0 for r in ratios):
        raise ValueError(f"ratios must be non-negative, got {ratios}")
    r_train, r_val, _r_test = ratios
    boundary_train = r_train
    boundary_val = r_train + r_val

    game_ids = _all_game_ids(base)
    frac = _splitmix_to_unit(game_ids, seed)

    train_mask = frac < boundary_train
    val_mask = (frac >= boundary_train) & (frac < boundary_val)
    test_mask = frac >= boundary_val

    all_idx = np.arange(len(base), dtype=np.int64)
    return SplitResult(
        train=_SubsetDataset(base, all_idx[train_mask], name="train"),
        val=_SubsetDataset(base, all_idx[val_mask], name="val"),
        test=_SubsetDataset(base, all_idx[test_mask], name="test"),
    )


__all__ = [
    "SplitResult",
    "split_by_shard",
    "split_by_track_id",
    "split_by_game_id",
]

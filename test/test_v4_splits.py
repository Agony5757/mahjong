"""Unit tests for V4 train/val/test splits.

Synthesizes a tiny on-disk V4 cache (no engine dependency) then exercises
both ``split_by_shard`` and ``split_by_track_id``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")  # splits.py imports torch

from pymahjong.rl.v4.cache import V4ShardWriter, rebuild_manifest
from pymahjong.rl.v4.cached_dataset import CachedEventDataset
from pymahjong.rl.v4.splits import split_by_shard, split_by_track_id


def _fake_sample(track_id: int, action: int, seq_len: int = 4) -> dict:
    rng = np.random.default_rng(track_id ^ action)
    return {
        "features": rng.integers(0, 2, size=(seq_len, 100), dtype=np.uint8).astype(bool),
        "action_mask": np.array(
            [i == action or i == (action + 1) % 54 for i in range(54)],
            dtype=bool,
        ),
        "action": action,
        "track_id": track_id,
    }


def _build_cache(tmp_path: Path, shards: dict[str, int]) -> Path:
    """Build a V4 cache with ``{shard_name: n_samples}``."""
    for name, n in shards.items():
        w = V4ShardWriter(str(tmp_path / name))
        for i in range(n):
            tid = hash((name, i)) & ((1 << 60) - 1)
            w.add(_fake_sample(tid, action=i % 54))
        w.close()
    rebuild_manifest(str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# split_by_shard
# ---------------------------------------------------------------------------


def test_split_by_shard_basic(tmp_path):
    cache_dir = _build_cache(tmp_path / "c1", {
        "shard_202401": 50, "shard_202402": 30, "shard_202403": 20,
    })
    base = CachedEventDataset(str(cache_dir))
    assert len(base) == 100

    split = split_by_shard(
        base,
        train_shards=["shard_202401"],
        val_shards=["shard_202402"],
        test_shards=["shard_202403"],
    )
    assert len(split.train) == 50
    assert len(split.val) == 30
    assert len(split.test) == 20

    # Items must be loadable and match expected shape.
    sample = split.train[0]
    assert sample["features"].dtype == torch.bool
    assert sample["action_mask"].shape == (54,)


def test_split_by_shard_omitted_shard_excluded(tmp_path):
    cache_dir = _build_cache(tmp_path / "c2", {
        "shard_A": 10, "shard_B": 10, "shard_C": 10,
    })
    base = CachedEventDataset(str(cache_dir))
    split = split_by_shard(
        base,
        train_shards=["shard_A"],
        val_shards=["shard_B"],
        test_shards=[],
    )
    assert len(split.train) + len(split.val) + len(split.test) == 20  # not 30


def test_split_by_shard_overlap_raises(tmp_path):
    cache_dir = _build_cache(tmp_path / "c3", {"shard_X": 5, "shard_Y": 5})
    base = CachedEventDataset(str(cache_dir))
    with pytest.raises(ValueError, match="multiple splits"):
        split_by_shard(base,
                       train_shards=["shard_X"],
                       val_shards=["shard_X"],
                       test_shards=["shard_Y"])


def test_split_by_shard_unknown_raises(tmp_path):
    cache_dir = _build_cache(tmp_path / "c4", {"shard_X": 5})
    base = CachedEventDataset(str(cache_dir))
    with pytest.raises(ValueError, match="unknown shards"):
        split_by_shard(base, train_shards=["shard_Q"],
                       val_shards=[], test_shards=[])


# ---------------------------------------------------------------------------
# split_by_track_id
# ---------------------------------------------------------------------------


def test_split_by_track_id_deterministic(tmp_path):
    cache_dir = _build_cache(tmp_path / "c5", {"shard_A": 1000, "shard_B": 500})
    base = CachedEventDataset(str(cache_dir))

    s1 = split_by_track_id(base, ratios=(0.7, 0.2, 0.1), seed=123)
    s2 = split_by_track_id(base, ratios=(0.7, 0.2, 0.1), seed=123)
    assert len(s1.train) == len(s2.train)
    assert len(s1.val) == len(s2.val)
    assert len(s1.test) == len(s2.test)
    np.testing.assert_array_equal(s1.train._indices, s2.train._indices)


def test_split_by_track_id_partitions_all(tmp_path):
    cache_dir = _build_cache(tmp_path / "c6", {"shard_A": 1000})
    base = CachedEventDataset(str(cache_dir))
    s = split_by_track_id(base, ratios=(0.8, 0.1, 0.1), seed=7)
    assert len(s.train) + len(s.val) + len(s.test) == len(base)
    # No duplicate sample across splits.
    all_idx = np.concatenate([s.train._indices, s.val._indices, s.test._indices])
    assert np.unique(all_idx).shape[0] == all_idx.shape[0]


def test_split_by_track_id_ratios_roughly_match(tmp_path):
    cache_dir = _build_cache(tmp_path / "c7", {"shard_A": 5000})
    base = CachedEventDataset(str(cache_dir))
    s = split_by_track_id(base, ratios=(0.7, 0.2, 0.1), seed=0)
    n = len(base)
    assert abs(len(s.train) / n - 0.7) < 0.05
    assert abs(len(s.val) / n - 0.2) < 0.05
    assert abs(len(s.test) / n - 0.1) < 0.05


def test_split_by_track_id_bad_ratios(tmp_path):
    cache_dir = _build_cache(tmp_path / "c8", {"shard_A": 10})
    base = CachedEventDataset(str(cache_dir))
    with pytest.raises(ValueError, match="sum to 1.0"):
        split_by_track_id(base, ratios=(0.5, 0.4, 0.2))
    with pytest.raises(ValueError, match="non-negative"):
        split_by_track_id(base, ratios=(1.2, -0.2, 0.0))

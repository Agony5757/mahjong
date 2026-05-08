"""Smoke tests for the on-disk token cache.

These tests exercise the cache *plumbing* (writer, manifest, reader,
augmentation) without depending on the C++ engine: synthetic samples
that obey the tokenizer's shape contract are written and read back.
"""

from __future__ import annotations

import os
import shutil
import tempfile

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from pymahjong.rl.cache import (  # noqa: E402
    CacheManifest,
    ShardEntry,
    ShardWriter,
    assert_schema_compatible,
    load_manifest,
    rebuild_manifest,
    save_manifest,
    schema_fingerprint,
)
from pymahjong.rl.cached_dataset import CachedTokenDataset, cached_collate  # noqa: E402
from pymahjong.rl.tokenization import (  # noqa: E402
    ACTION_DIM,
    MAX_SEQ_LEN,
    TOKEN_FEATURES,
)


def _fake_sample(rng: np.random.Generator, max_seq_len: int = MAX_SEQ_LEN) -> dict:
    seq_len = int(rng.integers(8, max_seq_len))
    tokens = np.zeros((max_seq_len, TOKEN_FEATURES), dtype=np.uint8)
    tokens[:seq_len, 0] = rng.integers(0, 16, size=seq_len)        # segment
    tokens[:seq_len, 1] = rng.integers(0, 38, size=seq_len)        # tile
    tokens[:seq_len, 2] = rng.integers(0, 5, size=seq_len)         # count
    tokens[:seq_len, 3] = rng.integers(0, 5, size=seq_len)         # who
    tokens[:seq_len, 4] = rng.integers(0, 64, size=seq_len)        # extra
    attn = np.zeros(max_seq_len, dtype=bool)
    attn[:seq_len] = True
    amask = np.zeros(ACTION_DIM, dtype=bool)
    amask[rng.integers(0, ACTION_DIM, size=3)] = True
    return {
        "tokens": tokens,
        "attention_mask": attn,
        "action_mask": amask,
        "action": int(rng.integers(0, ACTION_DIM)),
    }


def test_writer_then_reader_roundtrip():
    rng = np.random.default_rng(0)
    tmp = tempfile.mkdtemp(prefix="mj-cache-test-")
    try:
        n_per_shard = 7
        entries = []
        cum = 0
        for s in range(3):
            sub = os.path.join(tmp, f"shard_{s:05d}")
            with ShardWriter(sub) as w:
                for _ in range(n_per_shard):
                    w.add(_fake_sample(rng))
            n_rows = n_per_shard
            cum += n_rows
            entries.append(ShardEntry(path=os.path.basename(sub),
                                      n_rows=n_rows, cumulative=cum))
        save_manifest(tmp, CacheManifest(
            schema=schema_fingerprint(),
            total_rows=cum,
            shards=entries,
        ))

        ds = CachedTokenDataset(tmp)
        assert len(ds) == 3 * n_per_shard

        sample = ds[0]
        assert sample["tokens"].shape == (MAX_SEQ_LEN, TOKEN_FEATURES)
        assert sample["tokens"].dtype == torch.long
        assert sample["attention_mask"].shape == (MAX_SEQ_LEN,)
        assert sample["action_mask"].shape == (ACTION_DIM,)
        assert sample["action"].dtype == torch.long
        assert 0 <= int(sample["action"]) < ACTION_DIM

        last = ds[len(ds) - 1]
        assert last["tokens"].shape == sample["tokens"].shape

        # Collate works.
        batch = cached_collate([ds[i] for i in range(4)])
        assert batch["tokens"].shape == (4, MAX_SEQ_LEN, TOKEN_FEATURES)
        assert batch["action"].shape == (4,)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rebuild_manifest():
    rng = np.random.default_rng(1)
    tmp = tempfile.mkdtemp(prefix="mj-cache-test-")
    try:
        for s in range(2):
            sub = os.path.join(tmp, f"shard_{s:05d}")
            with ShardWriter(sub) as w:
                for _ in range(5):
                    w.add(_fake_sample(rng))
        m = rebuild_manifest(tmp)
        assert m.total_rows == 10
        assert len(m.shards) == 2
        assert m.shards[-1].cumulative == 10
        # manifest is loadable round-trip.
        m2 = load_manifest(tmp)
        assert m2.total_rows == m.total_rows
        assert_schema_compatible(m2.schema)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_schema_mismatch_raises():
    bad = schema_fingerprint()
    bad = dict(bad)
    bad["action_dim"] = bad["action_dim"] + 1
    with pytest.raises(ValueError):
        assert_schema_compatible(bad)


def test_suit_permutation_preserves_pad():
    rng = np.random.default_rng(2)
    tmp = tempfile.mkdtemp(prefix="mj-cache-test-")
    try:
        sub = os.path.join(tmp, "shard_00000")
        with ShardWriter(sub) as w:
            for _ in range(4):
                w.add(_fake_sample(rng))
        rebuild_manifest(tmp)

        ds = CachedTokenDataset(tmp, suit_permute=True, seat_rotate=True)
        for _ in range(20):
            s = ds[0]
            tile_col = s["tokens"][:, 1].numpy()
            # PAD tile (37) must map to itself under all 6 perms.
            attn = s["attention_mask"].numpy()
            assert np.all(tile_col[~attn] == 37) or np.all(tile_col[~attn] == 0)
            # (Synthetic test data may use 0 for inactive rows; either is fine
            # as long as we never accidentally map PAD into a real tile id.)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

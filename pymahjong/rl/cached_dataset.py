"""Map-style :class:`torch.utils.data.Dataset` over an on-disk token cache.

This avoids re-running the (relatively slow) tokenizer during training:
the cache is produced once with :mod:`pymahjong.rl.cache` and then
opened zero-copy via ``np.load(..., mmap_mode='r')`` from each DataLoader
worker. With ``num_workers>0`` the OS page cache is shared across
workers, so this scales linearly until disk bandwidth dominates.
"""

from __future__ import annotations

import bisect
import os
from typing import Dict, List, Optional

import numpy as np
import torch
from torch.utils.data import Dataset

from .cache import (
    CacheManifest,
    assert_schema_compatible,
    load_manifest,
    open_shard_arrays,
)
from .tokenization import MAX_SEQ_LEN, TILE_VOCAB_SIZE


class CachedTokenDataset(Dataset):
    """Random-access dataset backed by a directory of memory-mapped shards.

    Args:
        cache_dir: directory written by :class:`pymahjong.rl.cache.ShardWriter`
            (must contain ``index.json``).
        max_seq_len: must be <= the cache's recorded max length.
        suit_permute: if True, sample a random permutation of the
            three numbered suits (man/pin/sou) per example to augment
            data 6x. Honors red-five tile ids and PAD.

    Note:
        Seat rotation is **intentionally not exposed** — round wind /
        seat wind / dealer position are decision-relevant in Riichi
        Mahjong, so rotating seat ids would silently corrupt labels.
        The token's ``who`` field is already viewer-relative (0=self,
        1=next, ...), so no rotation is needed for invariance.
    """

    def __init__(
        self,
        cache_dir: str,
        max_seq_len: int = MAX_SEQ_LEN,
        suit_permute: bool = False,
    ):
        self.cache_dir = cache_dir
        self.max_seq_len = int(max_seq_len)
        self.suit_permute = bool(suit_permute)

        manifest: CacheManifest = load_manifest(cache_dir)
        assert_schema_compatible(manifest.schema, max_seq_len=self.max_seq_len)

        self._shards: List[str] = [s.path for s in manifest.shards if s.n_rows > 0]
        self._cum: List[int] = [s.cumulative for s in manifest.shards if s.n_rows > 0]
        self._n_rows: List[int] = [s.n_rows for s in manifest.shards if s.n_rows > 0]
        self._total = int(manifest.total_rows)

        # Per-worker arrays (lazy open, since np.memmap handles don't
        # cross fork boundaries cleanly on every platform).
        self._open: Dict[int, Dict[str, np.ndarray]] = {}

        # Precompute suit-permutation lookup tables.
        # tile ids 0..8 = man, 9..17 = pin, 18..26 = sou, 27..33 = honor,
        # 34..36 = red5m/p/s, 37 = PAD.
        self._suit_perms = self._build_suit_perms()

    def __len__(self) -> int:
        return self._total

    # ------------------------------------------------------------------ I/O

    def _arrays_for(self, shard_idx: int) -> Dict[str, np.ndarray]:
        cached = self._open.get(shard_idx)
        if cached is None:
            cached = open_shard_arrays(self.cache_dir, self._shards[shard_idx])
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

        tokens = np.array(arrays["tokens"][local], dtype=np.int64, copy=True)
        attn = np.array(arrays["attention_mask"][local], dtype=np.bool_, copy=True)
        amask = np.array(arrays["action_mask"][local], dtype=np.bool_, copy=True)
        label = int(arrays["labels"][local])

        if self.suit_permute:
            self._apply_suit_permutation(tokens)

        return {
            "tokens": torch.from_numpy(tokens),
            "attention_mask": torch.from_numpy(attn),
            "action_mask": torch.from_numpy(amask),
            "action": torch.tensor(label, dtype=torch.long),
        }

    # ------------------------------------------------------------ augment

    @staticmethod
    def _build_suit_perms() -> List[np.ndarray]:
        """Return all 6 permutations of {man, pin, sou} as tile-id LUTs."""
        # Identity LUT covering 0..37 (vocab size).
        base = np.arange(TILE_VOCAB_SIZE, dtype=np.uint8)
        suit_blocks = [(0, 9), (9, 18), (18, 27)]   # numbered tiles
        red_ids = [34, 35, 36]                       # red5m, red5p, red5s
        perms = []
        from itertools import permutations
        for order in permutations(range(3)):
            lut = base.copy()
            # number tiles
            for src, dst in enumerate(order):
                s_lo, s_hi = suit_blocks[src]
                d_lo, _ = suit_blocks[dst]
                lut[s_lo:s_hi] = np.arange(d_lo, d_lo + 9, dtype=np.uint8)
            # red fives follow the same permutation
            for src, dst in enumerate(order):
                lut[red_ids[src]] = red_ids[dst]
            perms.append(lut)
        return perms

    def _apply_suit_permutation(self, tokens: np.ndarray) -> None:
        lut = self._suit_perms[np.random.randint(6)]
        # tile field is column 1
        tile_col = tokens[:, 1]
        # Only permute valid token rows; PAD rows have tile=37 (PAD) which
        # the LUT keeps fixed because lut[37] == 37.
        np.copyto(tile_col, lut[tile_col])


def cached_collate(batch):
    """Stack a list of dicts (already torch tensors) into a batched dict."""
    out = {
        "tokens": torch.stack([b["tokens"] for b in batch], dim=0),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch], dim=0),
        "action_mask": torch.stack([b["action_mask"] for b in batch], dim=0),
        "action": torch.stack([b["action"] for b in batch], dim=0),
    }
    return out


__all__ = ["CachedTokenDataset", "cached_collate"]

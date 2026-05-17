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
from .tokenization import MAX_SEQ_LEN, NUM_BASE_TILES, TILE_VOCAB_SIZE


class CachedTokenDataset(Dataset):
    """Random-access dataset backed by a directory of memory-mapped shards.

    Args:
        cache_dir: directory written by :class:`pymahjong.rl.cache.ShardWriter`
            (must contain ``index.json``).
        max_seq_len: must be <= the cache's recorded max length.
        suit_permute: if True, randomly swap man↔pin per example to
            augment data 2x. Sou is kept fixed due to 绿一色 (All Green).
            Honors and PAD are unchanged.

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
        scalars = np.array(arrays["scalars"][local], dtype=np.float32, copy=True)
        attn = np.array(arrays["attention_mask"][local], dtype=np.bool_, copy=True)
        amask = np.array(arrays["action_mask"][local], dtype=np.bool_, copy=True)
        label = int(arrays["labels"][local])

        if self.suit_permute:
            self._apply_suit_permutation(tokens)

        return {
            "tokens": torch.from_numpy(tokens),
            "scalars": torch.from_numpy(scalars),
            "attention_mask": torch.from_numpy(attn),
            "action_mask": torch.from_numpy(amask),
            "action": torch.tensor(label, dtype=torch.long),
        }

    # ------------------------------------------------------------ augment

    @staticmethod
    def _build_suit_perms() -> List[np.ndarray]:
        """Return tile-id LUTs that swap man↔pin only (keep sou fixed).

        Tile id layout (post-V2):
          0..8   = man (1m..9m)
          9..17  = pin
          18..26 = sou
          27..33 = honors (z; never permuted)
          34     = PAD
        Aka (red-five) is encoded as a *bit* in extra, so the LUT only
        needs to swap the suit ranges -- the aka bit moves with the tile
        automatically.

        Sou (bamboo) cannot be swapped with man/pin because of 绿一色
        (Ryuuiisou, "All Green" yaku) which only uses sou tiles
        (2s, 3s, 4s, 6s, 8s + hatsu).  Only man↔pin are fully symmetric.
        """
        base = np.arange(TILE_VOCAB_SIZE, dtype=np.uint8)
        perms = [base.copy()]  # identity
        swapped = base.copy()
        swapped[0:9] = np.arange(9, 18, dtype=np.uint8)   # man → pin
        swapped[9:18] = np.arange(0, 9, dtype=np.uint8)    # pin → man
        perms.append(swapped)
        return perms

    def _apply_suit_permutation(self, tokens: np.ndarray) -> None:
        lut = self._suit_perms[np.random.randint(2)]
        tile_col = tokens[:, 1]
        np.copyto(tile_col, lut[tile_col])


def cached_collate(batch):
    """Stack a list of dicts (already torch tensors) into a batched dict."""
    out = {
        "tokens": torch.stack([b["tokens"] for b in batch], dim=0),
        "scalars": torch.stack([b["scalars"] for b in batch], dim=0),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch], dim=0),
        "action_mask": torch.stack([b["action_mask"] for b in batch], dim=0),
        "action": torch.stack([b["action"] for b in batch], dim=0),
    }
    return out


__all__ = ["CachedTokenDataset", "cached_collate"]

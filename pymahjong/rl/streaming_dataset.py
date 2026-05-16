"""Streaming paipu dataset with background prefetch for BC training.

Encodes Tenhou paipu XML files on-the-fly using a background thread that
stays ``prefetch_n`` files ahead of the training loop.  All encoded data
lives in memory (no on-disk cache), bounded to approximately
``prefetch_n * ~400KB`` (typically 40-60 decision-point samples per file).

Usage::

    from pymahjong.rl.streaming_dataset import StreamingPaipuDataset

    dataset = StreamingPaipuDataset(
        paipu_paths=glob("paipuxmls/**/*.txt", recursive=True),
        prefetch_n=4,
        suit_permute=True,
    )
    loader = DataLoader(dataset, batch_size=64, collate_fn=streaming_collate)
    for batch in loader:
        ...
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import torch
from torch.utils.data import IterableDataset

from .tokenization import (
    ACTION_DIM,
    MAX_SEQ_LEN,
    NUM_BASE_TILES,
    TILE_VOCAB_SIZE,
    TOKEN_FEATURES,
    MahjongTokenizer,
)

try:
    import MahjongPyWrapper as pm
except Exception:
    pm = None

# ---------------------------------------------------------------------------
# Per-file encoding (extracted from paipu_pipeline._encode_one_paipu)
# ---------------------------------------------------------------------------

_proxy_lock = threading.Lock()


def _unsupported_game_type(xml_path: str) -> bool:
    """Return True if this XML's GO type is not a 4-player pro table."""
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(xml_path)
        for elem in tree.getroot():
            if elem.tag == "GO":
                t = int(elem.get("type", "0"))
                if t & 0x20 == 0 or t & 0x10 != 0 or t & 0x40 != 0:
                    return True
                return False
            if elem.tag not in ("SHUFFLE",):
                break
        return False
    except Exception:
        return False


def encode_paipu_file(
    path: str,
    tokenizer: MahjongTokenizer,
) -> Optional[List[dict]]:
    """Encode a single paipu file into a list of tokenized sample dicts.

    Returns ``None`` for unsupported game types, empty list for files that
    produce no samples.  Thread-safe via a module-level lock that serializes
    only the ``pm.PaipuReplayer`` monkey-patch window.
    """
    if pm is None:
        raise RuntimeError("MahjongPyWrapper not importable")

    from pymahjong import tenhou_paipu_check as tpc
    from pymahjong.rl.dataset import SelfPlayImitationDataset

    if _unsupported_game_type(path):
        return None

    samples: List[dict] = []

    class _Proxy:
        __slots__ = ("_inner",)

        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def make_selection(self, idx):
            t = self._inner.table
            phase = int(t.get_phase())
            if phase < 16:
                actions = (
                    t.get_self_actions() if phase < 4
                    else t.get_response_actions()
                )
                if len(actions) > 1:
                    seat = phase % 4
                    try:
                        tok = tokenizer.encode(t, current_player=seat)
                        unified = SelfPlayImitationDataset._engine_idx_to_unified(t, idx)
                        samples.append(
                            {
                                "tokens": tok.tokens.copy(),
                                "scalars": tok.scalars.copy(),
                                "attention_mask": tok.attention_mask.copy(),
                                "action_mask": tok.action_mask.copy(),
                                "action": int(unified),
                            }
                        )
                    except Exception:
                        pass
            return self._inner.make_selection(idx)

    xml_path = Path(path)
    with _proxy_lock:
        orig_ctor = pm.PaipuReplayer
        pm.PaipuReplayer = lambda *a, **kw: _Proxy(orig_ctor(*a, **kw))  # type: ignore[assignment]
        try:
            replay = tpc.PaipuReplay()
            replay.logger = tpc.Logger()
            replay.write_log = False
            replay._paipu_replay(str(xml_path.parent), xml_path.name)
        except Exception:
            pass
        finally:
            pm.PaipuReplayer = orig_ctor  # type: ignore[assignment]

    return samples


# ---------------------------------------------------------------------------
# Suit-permutation augmentation
# ---------------------------------------------------------------------------


def _build_suit_perms() -> List[np.ndarray]:
    """Build tile-id LUTs that swap man↔pin only (keep sou fixed).

    Sou (bamboo) cannot be swapped with man/pin because of 绿一色
    (Ryuuiisou, "All Green" yaku) which only uses sou tiles
    (2s, 3s, 4s, 6s, 8s + hatsu).  Swapping sou into man/pin would
    create invalid game states.  Only man↔pin are fully symmetric.
    """
    base = np.arange(TILE_VOCAB_SIZE, dtype=np.uint8)
    perms = [base.copy()]  # identity
    swapped = base.copy()
    swapped[0:9] = np.arange(9, 18, dtype=np.uint8)   # man → pin
    swapped[9:18] = np.arange(0, 9, dtype=np.uint8)    # pin → man
    perms.append(swapped)
    return perms


_SUIT_PERMS = _build_suit_perms()


def _apply_suit_permutation(tokens: np.ndarray, rng: np.random.Generator) -> None:
    lut = _SUIT_PERMS[int(rng.integers(2))]
    tile_col = tokens[:, 1]
    np.copyto(tile_col, lut[tile_col])


# ---------------------------------------------------------------------------
# Streaming dataset
# ---------------------------------------------------------------------------


class StreamingPaipuDataset(IterableDataset):
    """IterableDataset that streams tokenized paipu samples with background
    prefetch.

    A background thread encodes paipu files sequentially (``pm.Table`` is not
    thread-safe) and fills a bounded in-memory buffer.  The consumer yields
    individual sample dicts from the buffer.

    Args:
        paipu_paths: paths to Tenhou paipu XML/TXT files.
        prefetch_n: max number of paipu files to keep pre-encoded in the
            buffer (~``prefetch_n * 400KB``).
        oracle: include hidden information in tokenization.
        max_seq_len: tokenizer sequence length budget.
        suit_permute: randomly permute man/pin/sou per sample (6x augment).
        shuffle: shuffle paipu file order each epoch.
        seed: RNG seed for reproducible shuffling and augmentation.
    """

    collate_fn: object = None  # set after streaming_collate is defined

    def __init__(
        self,
        paipu_paths: Iterable[str],
        prefetch_n: int = 4,
        oracle: bool = False,
        max_seq_len: int = MAX_SEQ_LEN,
        suit_permute: bool = False,
        shuffle: bool = True,
        seed: Optional[int] = None,
    ):
        self.paths: List[str] = list(paipu_paths)
        self.prefetch_n = prefetch_n
        self.oracle = oracle
        self.max_seq_len = max_seq_len
        self.suit_permute = suit_permute
        self.shuffle = shuffle
        self.seed = seed

    def __iter__(self):
        paths = list(self.paths)
        rng = np.random.default_rng(self.seed)
        if self.shuffle:
            rng.shuffle(paths)

        buf: queue.Queue = queue.Queue(maxsize=self.prefetch_n)
        stop = threading.Event()
        _SENTINEL = object()

        def producer():
            tokenizer = MahjongTokenizer(
                max_seq_len=self.max_seq_len,
                include_oracle=self.oracle,
            )
            for path in paths:
                if stop.is_set():
                    break
                try:
                    result = encode_paipu_file(path, tokenizer)
                except Exception:
                    result = []
                if result:
                    buf.put(result)  # blocks when buffer is full
            buf.put(_SENTINEL)

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        sample_rng = np.random.default_rng(self.seed)
        try:
            while True:
                item = buf.get()
                if item is _SENTINEL:
                    break
                for s in item:
                    if self.suit_permute:
                        _apply_suit_permutation(s["tokens"], sample_rng)
                    yield s
        finally:
            stop.set()
            thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Collation
# ---------------------------------------------------------------------------


def streaming_collate(batch: List[Dict]) -> Dict[str, torch.Tensor]:
    """Stack a list of sample dicts into a batched tensor dict.

    Handles numpy arrays from ``StreamingPaipuDataset`` (which yields numpy,
    not torch tensors).
    """
    return {
        "tokens": torch.as_tensor(
            np.stack([b["tokens"] for b in batch]), dtype=torch.long
        ),
        "scalars": torch.as_tensor(
            np.stack([b["scalars"] for b in batch]), dtype=torch.float32
        ),
        "attention_mask": torch.as_tensor(
            np.stack([b["attention_mask"] for b in batch]), dtype=torch.bool
        ),
        "action_mask": torch.as_tensor(
            np.stack([b["action_mask"] for b in batch]), dtype=torch.bool
        ),
        "action": torch.as_tensor(
            np.stack([b["action"] for b in batch]), dtype=torch.long
        ),
    }


# Wire the class attribute after definition.
StreamingPaipuDataset.collate_fn = streaming_collate


__all__ = [
    "StreamingPaipuDataset",
    "encode_paipu_file",
    "streaming_collate",
]

"""V4 autoregressive event-stream encoding for BC training.

Wraps the C++ ``encv4_HandEncoder`` / ``encv4_TrackEncoder`` classes and
integrates with the paipu replay pipeline via a ``_Proxy`` on
``PaipuReplayer``.  After each ``make_selection``, new ``GameLog`` entries
are routed to the ``HandEncoder`` as events.  Decision points (where
``len(actions) > 1``) are recorded as ``DecidePoint`` structs.

At the end of each hand, per-track samples are extracted from the encoder
and returned as Python dicts suitable for ``streaming_collate_v4``.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import torch
from torch.utils.data import IterableDataset

try:
    import MahjongPyWrapper as pm
except Exception:
    pm = None

from .tokenization import ACTION_DIM, MAX_SEQ_LEN

# Re-export C++ constants
EVENT_DIM: int = getattr(pm, "encv4_EVENT_DIM", 100) if pm else 100

_proxy_lock = threading.Lock()


# ---------------------------------------------------------------
# GameLog → HandEncoder event routing
# ---------------------------------------------------------------

# LogAction enum values for comparison
_LA = {
    "DrawNormal": 0,
    "DrawRinshan": 0,
    "DiscardFromHand": 0,
    "DiscardFromTsumo": 0,
    "RiichiDiscardFromHand": 0,
    "RiichiDiscardFromTsumo": 0,
    "RiichiSuccess": 0,
    "Chi": 0,
    "Pon": 0,
    "Kan": 0,
    "AnKan": 0,
    "KaKan": 0,
    "DoraReveal": 0,
    "Ron": 0,
    "Tsumo": 0,
    "Kyushukyuhai": 0,
}


def _route_gamelog_entries(
    encoder,  # pm.encv4_HandEncoder
    entries,  # list of BaseGameLog
) -> None:
    """Route new GameLog entries to the HandEncoder."""
    for log in entries:
        action = log.action
        player = log.player
        tile = log.tile
        aka = tile.red_dora if tile else False
        basetile = tile.tile if tile else pm.BaseTile._1m  # pass BaseTile enum, not int

        if action == pm.LogAction.DrawNormal:
            encoder.on_draw(player, basetile, aka)
        elif action == pm.LogAction.DrawRinshan:
            encoder.on_draw(player, basetile, aka)
        elif action in (pm.LogAction.DiscardFromHand, pm.LogAction.DiscardFromTsumo):
            flags = 0x02 if action == pm.LogAction.DiscardFromHand else 0
            encoder.on_discard(player, basetile, aka, flags)
        elif action == pm.LogAction.RiichiDiscardFromHand:
            encoder.on_riichi(player, basetile, 0x02)
        elif action == pm.LogAction.RiichiDiscardFromTsumo:
            encoder.on_riichi(player, basetile, 0)
        elif action == pm.LogAction.RiichiSuccess:
            encoder.on_riichi_success(player)
        elif action == pm.LogAction.Chi:
            call_tiles = log.call_tiles
            from_who = log.player2
            lowest = basetile
            for ct in call_tiles:
                bt = ct.tile
                if int(bt) < int(lowest):
                    lowest = bt
            chi_type = int(basetile) - int(lowest)
            aka_bits = sum(1 for ct in call_tiles if ct.red_dora)
            encoder.on_chi(player, lowest, chi_type, from_who, aka_bits)
        elif action == pm.LogAction.Pon:
            from_who = log.player2
            encoder.on_pon(player, basetile, from_who, aka)
        elif action == pm.LogAction.Kan:
            from_who = log.player2
            encoder.on_daiminkan(player, basetile, from_who, aka)
        elif action == pm.LogAction.AnKan:
            encoder.on_ankan(player, basetile)
        elif action == pm.LogAction.KaKan:
            encoder.on_kakan(player, basetile, aka)
        elif action == pm.LogAction.DoraReveal:
            encoder.on_dora_reveal(basetile, aka)
        elif action == pm.LogAction.Ron:
            from_who = log.player2
            encoder.on_ron(player, from_who)
        elif action == pm.LogAction.Tsumo:
            encoder.on_tsumo(player)


def _unsupported_game_type(xml_path: str) -> bool:
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


def _engine_action_mask(table, player: int) -> np.ndarray:
    """Compute 54-dim action mask from table's current action list."""
    from pymahjong.rl.action_space import ActionEncoder
    mask = np.zeros(54, dtype=np.uint8)
    phase = table.get_phase()
    if phase < 4:
        actions = table.get_self_actions()
    else:
        actions = table.get_response_actions()
    for i in range(len(actions)):
        unified = ActionEncoder.engine_to_unified(table, i)
        if 0 <= unified < 54:
            mask[unified] = 1
    return mask


def _engine_action_label(table, engine_idx: int) -> int:
    """Convert engine action index to unified action label."""
    from pymahjong.rl.action_space import ActionEncoder
    return int(ActionEncoder.engine_to_unified(table, engine_idx))


# ---------------------------------------------------------------
# Per-file encoding
# ---------------------------------------------------------------


def encode_paipu_file_v4(
    path: str,
) -> Optional[List[dict]]:
    """Encode a single paipu file into V4 samples.

    Returns ``None`` for unsupported game types, empty list for files that
    produce no samples.  Thread-safe via module-level lock.

    Each hanchan may contain multiple hands (局). Each hand triggers an
    ``init()`` call.  Samples are extracted at every ``init()`` boundary
    (for the previous hand) and once more at the end.
    """
    if pm is None:
        raise RuntimeError("MahjongPyWrapper not importable")

    from pymahjong import tenhou_paipu_check as tpc

    if _unsupported_game_type(path):
        return None

    samples: List[dict] = []
    enc_holder: list = [None]
    hand_counter = [0]

    def _extract_hand_samples(game_id: str, hand_idx: int) -> None:
        """Extract samples from the current encoder state."""
        enc = enc_holder[0]
        if enc is None:
            return
        for p in range(4):
            track = enc.track(p)
            events = track.events()
            dpoints = track.decide_points()
            track_id = int(
                hashlib.md5(f"{game_id}:{hand_idx}:{p}".encode()).hexdigest()[:15], 16
            )
            for dp in dpoints:
                pos = dp["track_pos"]
                seq_len = pos + 1
                if seq_len > 512:
                    continue
                features = events[:seq_len].astype(np.float32)
                attention_mask = np.ones(seq_len, dtype=np.bool_)
                action_mask = np.array(dp["action_mask"], dtype=np.bool_)
                action_label = dp["action_label"]
                samples.append({
                    "track_id": track_id,
                    "features": features,
                    "attention_mask": attention_mask,
                    "action_mask": action_mask,
                    "action": action_label,
                })

    class _Proxy:
        __slots__ = ("_inner",)

        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def init(self, *args, **kwargs):
            # Extract samples from previous hand before reinitializing
            if enc_holder[0] is not None:
                _extract_hand_samples(Path(path).stem, hand_counter[0])
                hand_counter[0] += 1
            ret = self._inner.init(*args, **kwargs)
            enc_holder[0] = pm.encv4_HandEncoder(self._inner.table)
            enc_holder[0].encode_init()
            return ret

        def make_selection(self, idx):
            enc = enc_holder[0]
            if enc is None:
                return self._inner.make_selection(idx)
            t = self._inner.table
            phase = int(t.get_phase())
            if phase < 16:
                actions = (
                    t.get_self_actions() if phase < 4
                    else t.get_response_actions()
                )
                if len(actions) > 1:
                    seat = phase % 4
                    mask = _engine_action_mask(t, seat)
                    label = _engine_action_label(t, idx)
                    enc.on_decide(seat, mask, label)

            gl = t.gamelog
            n_before = len(gl.logs)
            ret = self._inner.make_selection(idx)
            new_entries = gl.logs[n_before:]
            _route_gamelog_entries(enc, new_entries)
            return ret

    xml_path = Path(path)
    with _proxy_lock:
        orig_ctor = pm.PaipuReplayer
        pm.PaipuReplayer = lambda *a, **kw: _Proxy(orig_ctor(*a, **kw))
        try:
            replay = tpc.PaipuReplay()
            replay.logger = tpc.Logger()
            replay.write_log = False
            try:
                replay._paipu_replay(str(xml_path.parent), xml_path.name)
            except Exception:
                pass

            # Extract samples from the last hand
            _extract_hand_samples(xml_path.stem, hand_counter[0])
        finally:
            pm.PaipuReplayer = orig_ctor

    return samples


# ---------------------------------------------------------------
# Streaming dataset
# ---------------------------------------------------------------


class StreamingPaipuDatasetV4(IterableDataset):
    """IterableDataset that streams V4-encoded paipu samples."""

    collate_fn: object = None

    def __init__(
        self,
        paipu_paths: Iterable[str],
        prefetch_n: int = 4,
        shuffle: bool = True,
        seed: Optional[int] = None,
    ):
        self.paths: List[str] = list(paipu_paths)
        self.prefetch_n = prefetch_n
        self.shuffle = shuffle
        self.seed = seed

    def __iter__(self):
        import queue

        paths = list(self.paths)
        rng = np.random.default_rng(self.seed)
        if self.shuffle:
            rng.shuffle(paths)

        buf: queue.Queue = queue.Queue(maxsize=self.prefetch_n)
        stop = threading.Event()
        _SENTINEL = object()

        def producer():
            for path in paths:
                if stop.is_set():
                    break
                try:
                    result = encode_paipu_file_v4(path)
                except Exception:
                    result = []
                if result:
                    buf.put(result)
            buf.put(_SENTINEL)

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        try:
            while True:
                item = buf.get()
                if item is _SENTINEL:
                    break
                for s in item:
                    yield s
        finally:
            stop.set()
            thread.join(timeout=5)


# ---------------------------------------------------------------
# Collation
# ---------------------------------------------------------------


def streaming_collate_v4(batch: List[Dict]) -> Dict[str, torch.Tensor]:
    """Stack a list of V4 sample dicts into a batched tensor dict."""
    # Pad features to max seq_len in batch
    max_len = max(s["features"].shape[0] for s in batch)
    feat_dim = batch[0]["features"].shape[1]

    features = np.zeros((len(batch), max_len, feat_dim), dtype=np.float32)
    attention_mask = np.zeros((len(batch), max_len), dtype=np.bool_)

    for i, s in enumerate(batch):
        sl = s["features"].shape[0]
        features[i, :sl] = s["features"]
        attention_mask[i, :sl] = s["attention_mask"]

    return {
        "features": torch.as_tensor(features),
        "attention_mask": torch.as_tensor(attention_mask),
        "action_mask": torch.as_tensor(
            np.stack([s["action_mask"] for s in batch])
        ),
        "action": torch.as_tensor(
            np.stack([s["action"] for s in batch]), dtype=torch.long
        ),
    }


StreamingPaipuDatasetV4.collate_fn = streaming_collate_v4

__all__ = [
    "EVENT_DIM",
    "encode_paipu_file_v4",
    "StreamingPaipuDatasetV4",
    "streaming_collate_v4",
]

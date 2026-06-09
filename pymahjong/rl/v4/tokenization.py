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

try:
    import torch
    from torch.utils.data import IterableDataset
    _HAS_TORCH = True
except Exception:  # torch is optional — only required for dataset/collate helpers
    torch = None  # type: ignore[assignment]
    IterableDataset = object  # type: ignore[assignment,misc]
    _HAS_TORCH = False

try:
    import MahjongPyWrapper as pm
except Exception:
    pm = None

from ..v3.tokenization import (
    ACTION_DIM,
    MAX_SEQ_LEN,
    _MELD_ANKAN,
    _MELD_CHI,
    _MELD_DAIMINKAN,
    _MELD_KAKAN,
    _MELD_PON,
    _TILE_STR,
    _WIND_STR,
    _fuuro_from_r,
    _safe,
    _tile_id_and_aka,
    tile_str,
)

# Re-export C++ constants
EVENT_DIM: int = getattr(pm, "encv4_EVENT_DIM", 100) if pm else 100

# ---------------------------------------------------------------------------
# V4 feature layout constants (matching TrainingDataEncodingV4.h)
# ---------------------------------------------------------------------------

OFF_EVENT_TYPE = 0;    FEAT_EVENT_TYPE = 19
OFF_TILE = 19;         FEAT_TILE = 34
OFF_AKA = 53;          FEAT_AKA = 1
OFF_WHO = 54;          FEAT_WHO = 4
OFF_SCORE = 58;        FEAT_SCORE = 16
OFF_GAME_WIND = 74;    FEAT_GAME_WIND = 4
OFF_SELF_WIND = 78;    FEAT_SELF_WIND = 4
OFF_OYA_REL = 82;      FEAT_OYA_REL = 4
OFF_RIICHI_ST = 86;    FEAT_RIICHI_ST = 4
OFF_CHI_TYPE = 90;     FEAT_CHI_TYPE = 3
OFF_RIICHI_FLAG = 93;  FEAT_RIICHI_FLAG = 1
OFF_FROM_HAND = 94;    FEAT_FROM_HAND = 1
OFF_HONBA = 95;        FEAT_HONBA = 4
OFF_SIGN = 99;         FEAT_SIGN = 1


class _ET:
    """Event types matching C++ EventType enum."""
    PAD = 0
    GAME_CONTEXT = 1
    PLAYER_SCORE = 2
    INIT_HAND = 3
    DORA_INDICATOR = 4
    DRAW = 5
    DISCARD = 6
    CHI = 7
    PON = 8
    DAIMINKAN = 9
    ANKAN = 10
    KAKAN = 11
    RIICHI_DECLARE = 12
    RIICHI_SUCCESS = 13
    RON = 14
    TSUMO = 15
    RYUUKYOKU = 16
    SCORE_CHANGE = 17
    DORA_REVEAL = 18


def _decode_onehot(bits, offset, length):
    for i in range(length):
        if bits[offset + i]:
            return i
    return -1


def _decode_binary(bits, offset, length):
    val = 0
    for i in range(length):
        if bits[offset + i]:
            val |= (1 << i)
    return val


def _decode_signed_binary(bits, offset, length):
    val = _decode_binary(bits, offset, length)
    if val >= (1 << (length - 1)):
        val -= (1 << length)
    return val


def _remove_from_hand(hand: list, basetile: int, aka: bool) -> None:
    for i, (bt, a) in enumerate(hand):
        if bt == basetile and a == aka:
            hand.pop(i)
            return
    for i, (bt, _) in enumerate(hand):
        if bt == basetile:
            hand.pop(i)
            return


def _remove_n_from_hand(hand: list, basetile: int, n: int) -> None:
    removed = 0
    for i in range(len(hand) - 1, -1, -1):
        if hand[i][0] == basetile:
            hand.pop(i)
            removed += 1
            if removed >= n:
                return


def _remove_chi_hand_tiles(hand: list, lowest: int, chi_type: int) -> None:
    chi_tiles = [lowest, lowest + 1, lowest + 2]
    for pos in range(3):
        if pos != chi_type:
            _remove_from_hand(hand, chi_tiles[pos], False)


# ---------------------------------------------------------------------------
# Round-trip canonical string functions
# ---------------------------------------------------------------------------


def state_to_string_v4(table, viewer: int) -> str:
    """Pretty-print engine state in V4 canonical format (viewer-relative)."""
    if pm is None:
        raise RuntimeError("MahjongPyWrapper not importable")

    players = table.players
    me = players[viewer]
    phase = int(table.get_phase())

    lines = []
    lines.append("== V4 STATE ==")
    lines.append(f"VIEWER: {viewer}")

    game_wind = int(table.game_wind)
    self_wind = int(me.wind)
    oya_rel = (int(table.oya) - viewer) % 4
    lines.append(
        f"GAME: wind={_WIND_STR[game_wind]} "
        f"self_wind={_WIND_STR[self_wind]} oya_rel={oya_rel}"
    )

    honba = int(getattr(table, "honba", 0))
    lines.append(f"HONBA: {honba}")

    scores = [int(players[(viewer + r) % 4].score) for r in range(4)]
    lines.append("SCORES: " + " ".join(str(s) for s in scores))

    riichi = [1 if players[(viewer + r) % 4].riichi else 0 for r in range(4)]
    lines.append("RIICHI: " + " ".join(str(v) for v in riichi))

    hand_tiles = list(me.hand)
    tsumo_tile = None
    if len(hand_tiles) > 0 and len(hand_tiles) % 3 == 2:
        # Only separate tsumo when the viewer is in a self-action phase
        # AND just drew a tile (last_action is Discard, not Chi/Pon/Kan).
        acting = phase % 4
        is_self_action = phase < 4
        no_call = table.last_action not in (
            pm.BaseAction.Chi, pm.BaseAction.Pon,
            pm.BaseAction.Kan, pm.BaseAction.AnKan, pm.BaseAction.KaKan,
        )
        if viewer == acting and is_self_action and no_call:
            tsumo_tile = hand_tiles[-1]
            hand_tiles = hand_tiles[:-1]
    hand_strs = sorted(_TILE_STR[int(t.tile)] for t in hand_tiles)
    lines.append("HAND: " + " ".join(hand_strs))
    if tsumo_tile is not None:
        b, a = _tile_id_and_aka(tsumo_tile)
        lines.append("TSUMO: " + tile_str(b, a))
    else:
        lines.append("TSUMO: -")

    n_active = int(getattr(table, "n_active_dora", 1))
    di_strs = [_TILE_STR[int(d.tile)] for d in list(table.dora_indicator)[:n_active]]
    lines.append("DORA_IND: " + (" ".join(di_strs) if di_strs else "-"))

    _MELD_NAMES = {
        _MELD_CHI: "Chi",
        _MELD_PON: "Pon",
        _MELD_DAIMINKAN: "DaiMinKan",
        _MELD_KAKAN: "KaKan",
        _MELD_ANKAN: "AnKan",
    }

    for r in range(4):
        seat = (viewer + r) % 4
        cgs = _safe(lambda s=seat: players[s].get_fuuros(), []) or []
        parts = []
        for cg in cgs:
            mt = int(cg.type)
            owner_from_r = _fuuro_from_r(mt, getattr(cg, "take", 0))
            viewer_from_r = -1 if mt == _MELD_ANKAN else (r + owner_from_r) % 4
            name = _MELD_NAMES.get(mt, f"?{mt}")

            if mt == _MELD_CHI:
                tile_strs = " ".join(_TILE_STR[int(t.tile)] for t in cg.tiles)
                parts.append(f"[{name} from_r={viewer_from_r} tiles={tile_strs}]")
            elif mt == _MELD_ANKAN:
                tile_bt = int(cg.tiles[0].tile)
                parts.append(f"[{name} tile={_TILE_STR[tile_bt]}]")
            else:
                tile_bt = int(cg.tiles[0].tile)
                parts.append(f"[{name} from_r={viewer_from_r} tile={_TILE_STR[tile_bt]}]")
        lines.append(f"FUURO[r={r}]: " + (" ".join(parts) if parts else "-"))

    for r in range(4):
        seat = (viewer + r) % 4
        river = _safe(lambda s=seat: players[s].get_river().river, []) or []
        parts = []
        for idx, rt in enumerate(river):
            base = int(rt.tile.tile)
            ri = "R" if rt.riichi else "."
            fh = "H" if rt.fromhand else "h"
            parts.append(f"{_TILE_STR[base]}#{idx}{ri}{fh}")
        lines.append(f"RIVER[r={r}]: " + (" ".join(parts) if parts else "-"))

    return "\n".join(lines)


def events_to_string_v4(events: np.ndarray, viewer: int) -> str:
    """Reconstruct canonical state string from V4 event sequence."""
    game_wind = -1
    self_wind = -1
    oya_rel = -1
    honba = 0
    scores = [0, 0, 0, 0]
    riichi_status = [0, 0, 0, 0]
    hand: list = []
    viewer_tsumo: Optional[tuple] = None
    fuuros = {0: [], 1: [], 2: [], 3: []}
    rivers = {0: [], 1: [], 2: [], 3: []}
    dora_indicators: list = []
    last_discard_who = -1
    # Tracks the global "last action" similar to ``Table::last_action``.  After
    # a call (chi/pon/kan/ankan/kakan) the engine does not separate the rinshan
    # tsumo from hand in state_to_string_v4, so we need to match that.
    last_action_was_call = False

    for i in range(events.shape[0]):
        e = events[i]
        et = _decode_onehot(e, OFF_EVENT_TYPE, FEAT_EVENT_TYPE)
        if et <= _ET.PAD:
            continue

        if et == _ET.GAME_CONTEXT:
            game_wind = _decode_onehot(e, OFF_GAME_WIND, FEAT_GAME_WIND)
            self_wind = _decode_onehot(e, OFF_SELF_WIND, FEAT_SELF_WIND)
            oya_rel = _decode_onehot(e, OFF_OYA_REL, FEAT_OYA_REL)
            honba = 0
            scores = [0, 0, 0, 0]
            riichi_status = [0, 0, 0, 0]
            hand = []
            viewer_tsumo = None
            fuuros = {0: [], 1: [], 2: [], 3: []}
            rivers = {0: [], 1: [], 2: [], 3: []}
            dora_indicators = []
            last_discard_who = -1
            last_action_was_call = False

        elif et == _ET.PLAYER_SCORE:
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            score_units = _decode_signed_binary(e, OFF_SCORE, FEAT_SCORE)
            honba = _decode_binary(e, OFF_HONBA, FEAT_HONBA)
            if 0 <= who < 4:
                scores[who] = score_units * 100 + 25000

        elif et == _ET.INIT_HAND:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            aka = bool(e[OFF_AKA])
            if tile >= 0:
                hand.append((tile, aka))
                # For the oya track, the 14th INIT_HAND is the dealer's
                # first draw.  Move it into ``viewer_tsumo`` so subsequent
                # tsumokiri (DISCARD with fh=False) consumes it correctly.
                if len(hand) == 14:
                    viewer_tsumo = hand.pop()

        elif et == _ET.DORA_INDICATOR:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            if tile >= 0:
                dora_indicators.append(tile)

        elif et == _ET.DRAW:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            aka = bool(e[OFF_AKA])
            # DRAW events only appear on the viewer's own track,
            # so every DRAW here belongs to the viewer.
            if tile >= 0:
                if viewer_tsumo is not None:
                    hand.append(viewer_tsumo)
                viewer_tsumo = (tile, aka)

        elif et == _ET.DISCARD:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            aka = bool(e[OFF_AKA])
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            rf = bool(e[OFF_RIICHI_FLAG])
            fh = bool(e[OFF_FROM_HAND])
            last_discard_who = who
            last_action_was_call = False
            if who == 0:
                if fh:
                    if viewer_tsumo is not None:
                        hand.append(viewer_tsumo)
                        viewer_tsumo = None
                    _remove_from_hand(hand, tile, aka)
                else:
                    viewer_tsumo = None
            if 0 <= who < 4 and tile >= 0:
                # Match engine semantics: River entry's riichi flag is
                # ``player.riichi || on_riichi`` — once a player has declared
                # riichi, all subsequent discards are marked riichi=True.
                rivers[who].append((tile, aka, rf or bool(riichi_status[who]), fh))

        elif et == _ET.RIICHI_DECLARE:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            aka = bool(e[OFF_AKA])
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            fh = bool(e[OFF_FROM_HAND])
            rf = bool(e[OFF_RIICHI_FLAG])
            # Note: player.riichi is set on RIICHI_SUCCESS, not declaration.
            last_discard_who = who
            last_action_was_call = False
            if who == 0:
                if fh:
                    if viewer_tsumo is not None:
                        hand.append(viewer_tsumo)
                        viewer_tsumo = None
                    _remove_from_hand(hand, tile, aka)
                else:
                    viewer_tsumo = None
            if 0 <= who < 4 and tile >= 0:
                rivers[who].append((tile, aka, rf, fh))

        elif et == _ET.RIICHI_SUCCESS:
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            if 0 <= who < 4:
                riichi_status[who] = 1

        elif et == _ET.CHI:
            lowest = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            chi_type = _decode_onehot(e, OFF_CHI_TYPE, FEAT_CHI_TYPE)
            from_r = (who + 3) % 4
            tiles = [lowest, lowest + 1, lowest + 2]
            if who == 0:
                _remove_chi_hand_tiles(hand, lowest, chi_type)
            fuuros[who].append({"type": "Chi", "from_r": from_r, "tiles": tiles})
            last_action_was_call = True

        elif et == _ET.PON:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            from_r = last_discard_who if last_discard_who >= 0 else -1
            if who == 0:
                _remove_n_from_hand(hand, tile, 2)
            fuuros[who].append({"type": "Pon", "from_r": from_r, "tile": tile})
            last_action_was_call = True

        elif et == _ET.DAIMINKAN:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            from_r = last_discard_who if last_discard_who >= 0 else -1
            if who == 0:
                _remove_n_from_hand(hand, tile, 3)
            fuuros[who].append(
                {"type": "DaiMinKan", "from_r": from_r, "tile": tile}
            )
            last_action_was_call = True

        elif et == _ET.ANKAN:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            if who == 0:
                # If the kan tile was just drawn (viewer_tsumo holds it), consume
                # it from viewer_tsumo first; the remaining 3 come from hand.
                need = 4
                if viewer_tsumo is not None and viewer_tsumo[0] == tile:
                    viewer_tsumo = None
                    need = 3
                _remove_n_from_hand(hand, tile, need)
            fuuros[who].append({"type": "AnKan", "from_r": -1, "tile": tile})
            last_action_was_call = True

        elif et == _ET.KAKAN:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            who = _decode_onehot(e, OFF_WHO, FEAT_WHO)
            if who == 0:
                # KaKan uses 1 tile, which may be the just-drawn viewer_tsumo.
                if viewer_tsumo is not None and viewer_tsumo[0] == tile:
                    viewer_tsumo = None
                else:
                    _remove_n_from_hand(hand, tile, 1)
            for fuuro in reversed(fuuros[who]):
                if fuuro["type"] == "Pon" and fuuro["tile"] == tile:
                    fuuro["type"] = "KaKan"
                    break
            last_action_was_call = True

        elif et == _ET.DORA_REVEAL:
            tile = _decode_onehot(e, OFF_TILE, FEAT_TILE)
            if tile >= 0:
                dora_indicators.append(tile)

    # Build output
    lines = []
    lines.append("== V4 STATE ==")
    lines.append(f"VIEWER: {viewer}")
    lines.append(
        f"GAME: wind={_WIND_STR[game_wind]} "
        f"self_wind={_WIND_STR[self_wind]} oya_rel={oya_rel}"
    )
    lines.append(f"HONBA: {honba}")
    lines.append("SCORES: " + " ".join(str(s) for s in scores))
    lines.append("RIICHI: " + " ".join(str(v) for v in riichi_status))

    # Use viewer_tsumo if available (from DRAW events).
    # Match state_to_string_v4: after a call (chi/pon/kan/ankan/kakan), the
    # engine doesn't separate the rinshan tsumo from hand — merge it back.
    display_hand = list(hand)
    show_tsumo = viewer_tsumo is not None and not last_action_was_call
    if not show_tsumo and viewer_tsumo is not None:
        display_hand.append(viewer_tsumo)
    display_hand_sorted = sorted(display_hand, key=lambda x: _TILE_STR[x[0]])
    lines.append("HAND: " + " ".join(_TILE_STR[bt] for bt, _ in display_hand_sorted))
    if show_tsumo:
        lines.append("TSUMO: " + tile_str(viewer_tsumo[0], viewer_tsumo[1]))
    else:
        lines.append("TSUMO: -")

    di_strs = [_TILE_STR[b] for b in dora_indicators]
    lines.append("DORA_IND: " + (" ".join(di_strs) if di_strs else "-"))

    for r in range(4):
        parts = []
        for f in fuuros[r]:
            if f["type"] == "Chi":
                ts = " ".join(_TILE_STR[t] for t in f["tiles"])
                parts.append(f"[Chi from_r={f['from_r']} tiles={ts}]")
            elif f["type"] == "AnKan":
                parts.append(f"[AnKan tile={_TILE_STR[f['tile']]}]")
            else:
                parts.append(
                    f"[{f['type']} from_r={f['from_r']} "
                    f"tile={_TILE_STR[f['tile']]}]"
                )
        lines.append(f"FUURO[r={r}]: " + (" ".join(parts) if parts else "-"))

    for r in range(4):
        parts = []
        for idx, (tile, _aka, rf, fh) in enumerate(rivers[r]):
            ri = "R" if rf else "."
            h = "H" if fh else "h"
            parts.append(f"{_TILE_STR[tile]}#{idx}{ri}{h}")
        lines.append(f"RIVER[r={r}]: " + (" ".join(parts) if parts else "-"))

    return "\n".join(lines)

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
    skip_draw: bool = False,
) -> None:
    """Route new GameLog entries to the HandEncoder."""
    for log in entries:
        action = log.action
        player = log.player
        tile = log.tile
        aka = tile.red_dora if tile else False
        basetile = tile.tile if tile else pm.BaseTile._1m  # pass BaseTile enum, not int

        if skip_draw and action in (pm.LogAction.DrawNormal, pm.LogAction.DrawRinshan):
            continue

        if action == pm.LogAction.DrawNormal:
            encoder.on_draw(player, basetile, aka)
        elif action == pm.LogAction.DrawRinshan:
            encoder.on_draw(player, basetile, aka)
        elif action in (pm.LogAction.DiscardFromHand, pm.LogAction.DiscardFromTsumo):
            flags = 0x02 if action == pm.LogAction.DiscardFromHand else 0
            encoder.on_discard(player, basetile, aka, flags)
        elif action == pm.LogAction.RiichiDiscardFromHand:
            encoder.on_riichi(player, basetile, aka, True)
        elif action == pm.LogAction.RiichiDiscardFromTsumo:
            encoder.on_riichi(player, basetile, aka, False)
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
            # AnKan logs ``tile=nullptr`` and stores the kan tiles in
            # ``call_tiles`` (see GameLog::log_ankan).  Use the first call
            # tile to recover the BaseTile.
            call_tiles = log.call_tiles
            if call_tiles:
                basetile = call_tiles[0].tile
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
    from ..action_space import ActionEncoder
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
    from ..action_space import ActionEncoder
    return int(ActionEncoder.engine_to_unified(table, engine_idx))


# ---------------------------------------------------------------
# Per-file encoding
# ---------------------------------------------------------------


def _table_scores(table) -> List[int]:
    """Best-effort read of the 4 players' current scores from a ``Table``."""
    try:
        players = table.players
        return [int(players[p].score) for p in range(4)]
    except Exception:  # noqa: BLE001
        return [25000, 25000, 25000, 25000]


def _annotate_rl_targets(
    samples: List[dict],
    hand_start_scores: List[List[int]],
    final_scores: List[int],
    pts: List[float],
) -> None:
    """Attach Mortal offline-RL targets (in place) to ``samples``.

    ``q_reward`` is the per-kyoku placement-delta (potential-difference of
    expected placement points, telescoping to the seat's final placement
    points), ``player_rank`` the seat's final rank (0=1st), ``steps_to_done``
    the seat's remaining decisions in the kyoku.
    """
    from ..v5.grp import _placement_exp_pts  # pure-numpy, no torch needed

    pts_arr = np.asarray(pts, dtype=np.float64)
    # Score states at each kyoku boundary: start-of-each-hand + final.
    states = [np.asarray(s, dtype=np.float64) for s in hand_start_scores]
    states.append(np.asarray(final_scores, dtype=np.float64))
    exp = [_placement_exp_pts(st, pts_arr) for st in states]      # (T+1, 4)
    rewards = [exp[k + 1] - exp[k] for k in range(len(exp) - 1)]  # (T, 4)

    fin = np.asarray(final_scores, dtype=np.float64)
    order = sorted(range(4), key=lambda i: (-fin[i], i))         # ties: lower seat first
    rank = [0, 0, 0, 0]
    for r, seat in enumerate(order):
        rank[seat] = r

    groups: Dict = {}
    for s in samples:
        groups.setdefault((s["_hand_idx"], s["_seat"]), []).append(s)
    for (k, seat), grp in groups.items():
        m = len(grp)
        r = float(rewards[k][seat]) if 0 <= k < len(rewards) else 0.0
        for pos, s in enumerate(grp):
            s["q_reward"] = r
            s["player_rank"] = int(rank[seat])
            s["steps_to_done"] = int(m - 1 - pos)


def encode_paipu_file_v4(
    path: str,
    pts: Optional[List[float]] = None,
) -> Optional[List[dict]]:
    """Encode a single paipu file into V4 samples.

    Returns ``None`` for unsupported game types, empty list for files that
    produce no samples.  Thread-safe via module-level lock.

    Each hanchan may contain multiple hands (局). Each hand triggers an
    ``init()`` call.  Samples are extracted at every ``init()`` boundary
    (for the previous hand) and once more at the end.

    When ``pts`` (a 4-vector of placement points for ranks [1st..4th]) is
    given, each sample is additionally annotated with **offline-RL targets**
    faithful to Mortal: ``q_reward`` (the per-kyoku placement-delta reward
    for that seat, GRP-free deterministic version), ``player_rank`` (the
    seat's final hanchan rank 0-3) and ``steps_to_done`` (own remaining
    decisions in the kyoku).  Mortal's ``q_target = gamma**steps_to_done *
    kyoku_reward``; with Mortal's ``gamma=1`` ``steps_to_done`` is unused but
    stored for generality.
    """
    if pm is None:
        raise RuntimeError("MahjongPyWrapper not importable")

    from pymahjong import tenhou_paipu_check as tpc

    if _unsupported_game_type(path):
        return None

    samples: List[dict] = []
    enc_holder: list = [None]
    hand_counter = [0]
    # Per-kyoku score progression for the offline-RL reward (only used when
    # ``pts`` is given).  ``hand_start_scores[k]`` = scores at the start of
    # hand k (== scores after hand k-1); ``last_scores[0]`` tracks the
    # running (final) scores.
    hand_start_scores: List[List[int]] = []
    last_scores: list = [[25000, 25000, 25000, 25000]]

    def _extract_hand_samples(game_id: str, hand_idx: int) -> None:
        """Extract samples from the current encoder state."""
        enc = enc_holder[0]
        if enc is None:
            return
        # Hash the game_id (paipu filename stem) once per hand: same paipu →
        # same game_hash for all four seats, so :func:`split_by_game_id` can
        # keep an entire hanchan in a single split (no cross-seat leakage of
        # game-shared context like wall, dora indicators, dice, hand_idx).
        game_hash = int(
            hashlib.md5(f"{game_id}".encode()).hexdigest()[:15], 16
        )
        for p in range(4):
            track = enc.track(p)
            events = track.events()
            dpoints = track.decide_points()
            track_id = int(
                hashlib.md5(f"{game_id}:{hand_idx}:{p}".encode()).hexdigest()[:15], 16
            )
            for dp in dpoints:
                pos = dp["track_pos"]
                # BUG FIX: ``track_pos`` is set in C++ as ``events_.size()``
                # at the moment of on_decide(), i.e. the index where the
                # *next* event will be written.  ``events[:pos + 1]`` would
                # then include the *first* event appended after on_decide —
                # which for a self-action decision is the player's own
                # discard/call event.  That leaks the expert label directly
                # into the input features (verified: removing the last
                # event drops V5 BC test acc from 96.7% to 42.1%).
                # The correct snapshot is ``events[:pos]`` — all events
                # that existed *before* on_decide was called, matching
                # what live.py / V4MultiAgentEnv expose at inference time.
                seq_len = pos
                if seq_len <= 0 or seq_len > 512:
                    continue
                features = events[:seq_len].astype(np.float32)
                attention_mask = np.ones(seq_len, dtype=np.bool_)
                action_mask = np.array(dp["action_mask"], dtype=np.bool_)
                action_label = dp["action_label"]
                samples.append({
                    "track_id": track_id,
                    "game_id": game_hash,
                    "features": features,
                    "attention_mask": attention_mask,
                    "action_mask": action_mask,
                    "action": action_label,
                    "_hand_idx": hand_idx,
                    "_seat": p,
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
            if pts is not None:
                hand_start_scores.append(_table_scores(self._inner.table))
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
            if pts is not None:
                last_scores[0] = _table_scores(t)
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

    if pts is not None and samples:
        try:
            _annotate_rl_targets(samples, hand_start_scores, last_scores[0], pts)
        except Exception:
            # On any failure leave neutral RL targets so the file's BC
            # samples remain usable.
            for s in samples:
                s.setdefault("q_reward", 0.0)
                s.setdefault("player_rank", 0)
                s.setdefault("steps_to_done", 0)

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


def streaming_collate_v4(batch: List[Dict]) -> Dict[str, "torch.Tensor"]:
    """Stack a list of V4 sample dicts into a batched tensor dict."""
    if not _HAS_TORCH:
        raise ImportError(
            "streaming_collate_v4 requires PyTorch; install torch to use it"
        )
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
    "state_to_string_v4",
    "events_to_string_v4",
]

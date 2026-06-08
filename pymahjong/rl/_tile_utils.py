"""Neutral tile / meld helpers shared across the RL stack.

These small utilities (tile string formatting, meld-type constants,
red-five detection, ``CallGroup`` source-seat inference, ...) are not
specific to any one observation encoding.  They originally lived in
``pymahjong/rl/v3/tokenization.py`` and were re-imported from the V4
event-stream encoder; this module is the single source of truth after
the V3/V4/V5 namespaces were flattened into MajNova v0.
"""

from __future__ import annotations

from typing import Tuple

# ---------------------------------------------------------------------------
# Tile vocabulary
# ---------------------------------------------------------------------------

NUM_BASE_TILES = 34          # 1-9m, 1-9p, 1-9s, 1-7z
TILE_PAD = 34                # padding / "no-tile" id
TILE_VOCAB_SIZE = 35         # 0..33 base + 34 pad

# Indices of the three red-5 base tiles (5m, 5p, 5s) in the BaseTile space.
RED5_BASE = {4, 13, 22}

# Tile string table (matches the engine's own ``TileToString`` ordering).
_TILE_STR = [
    "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
    "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
    "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s",
    "1z", "2z", "3z", "4z", "5z", "6z", "7z",
]
_WIND_STR = ["E", "S", "W", "N"]


def tile_str(tile_id: int, aka: int = 0) -> str:
    """Pretty-print a tile id (with aka marker)."""
    if tile_id == TILE_PAD:
        return "(pad)"
    s = _TILE_STR[tile_id]
    return s + ("*" if aka else "")


# ---------------------------------------------------------------------------
# Tile object helpers
# ---------------------------------------------------------------------------


def _tile_id_and_aka(tile_obj) -> Tuple[int, int]:
    """Return ``(base_tile_id, aka_flag)`` for a ``pm.Tile`` instance."""
    base = int(tile_obj.tile)
    aka = 1 if getattr(tile_obj, "red_dora", False) else 0
    return base, aka


def _basetile_id(bt) -> int:
    """Coerce a ``pm.BaseTile`` enum to its int id."""
    return int(bt)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


# ---------------------------------------------------------------------------
# Meld / call group helpers
# ---------------------------------------------------------------------------

# CallGroup::Type values (must match Mahjong/Tile.h).
_MELD_CHI = 0
_MELD_PON = 1
_MELD_DAIMINKAN = 2
_MELD_KAKAN = 3
_MELD_ANKAN = 4


def _fuuro_from_r(meld_type: int, take: int) -> int:
    """Infer the relative seat of the discarder for a call group.

    Riichi mahjong rules:
      - Chi can only be called from kamicha (上家, relative seat 3).
      - Pon / DaiMinKan / KaKan: ``take`` is the position of the called
        tile in the meld and uniquely identifies the source seat —
        0 = kamicha (r=3), 1 = toimen (r=2), 2 = shimocha (r=1).
        (KaKan is added on top of an existing pon, so the original
        pon's ``take`` still indicates the source.)
      - AnKan is concealed, so there is no source. We emit r=4
        (sentinel for "no source / unknown").
    """
    if meld_type == _MELD_CHI:
        return 3
    if meld_type == _MELD_ANKAN:
        return 4
    # Pon / DaiMinKan / KaKan: take ∈ {0,1,2} → r ∈ {3,2,1}
    return {0: 3, 1: 2, 2: 1}.get(int(take), 4)


# ---------------------------------------------------------------------------
# Phase classification helpers
# ---------------------------------------------------------------------------


def is_self_phase(phase: int) -> bool:
    return 0 <= phase < 4


def is_response_phase(phase: int) -> bool:
    return 4 <= phase < 8


def is_chankan_phase(phase: int) -> bool:
    return 8 <= phase < 16


def acting_player(phase: int) -> int:
    """Player whose turn it is during a self-action / response phase."""
    return phase % 4

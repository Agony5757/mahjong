"""Transformer-friendly tokenized state/action encoding for Mahjong (v2).

This is the post-V2-audit rewrite (see ``ENCODING.md``). Every token is a
small fixed-size feature tuple plus a parallel float scalar vector::

    token   = (segment_id, tile_id, count, who, extra)   # uint8s
    scalars = (s0, s1, s2, s3)                           # float32s

Categorical features (segment / tile / count / who / extra) go through
embedding tables; ``scalars`` carries normalized continuous quantities
(score / 25000, remaining / 70, ...) so the model sees true magnitudes
instead of bucketed embedding indices.

Action space stays compatible with :class:`pymahjong.env_pymahjong.MahjongEnv`
(``ACTION_DIM = 54``) so engine / paipu pipelines are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Sequence

import numpy as np

try:  # pragma: no cover - thin runtime guard
    import MahjongPyWrapper as pm
except Exception:  # noqa: BLE001
    pm = None  # type: ignore


# ---------------------------------------------------------------------------
# Tile vocabulary (red-5 fix: aka encoded as a *bit*, not a separate id)
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
# Segments (post-V2 audit -- 30 segment ids)
# ---------------------------------------------------------------------------

class SegmentType(IntEnum):
    PAD = 0
    SELF_HAND = 1            # closed hand of self
    SELF_TSUMO = 2           # the just-drawn tile (separate from rest of hand)
    SELF_FUURO = 3           # tiles in self's called melds
    OPP_FUURO = 4            # tiles in opponents' called melds
    SELF_RIVER = 5           # self's discards (in order)
    OPP_RIVER = 6            # opponents' discards
    DORA_INDICATOR = 7       # face-up dora indicator(s)
    URA_DORA_INDICATOR = 8   # uradora (only if revealed)
    ACTUAL_DORA = 9          # actual dora tiles (computed by engine)
    PLAYER_RIICHI = 10       # 1 token per player
    PLAYER_IPPATSU = 11
    PLAYER_MENZEN = 12
    PLAYER_SCORE = 13        # categorical bucket; precise value via scalars[0]
    GAME_WIND = 14
    SELF_WIND = 15
    HONBA = 16
    KYOUTAKU = 17
    REMAINING_TILES = 18
    SELF_TSUMO_TILE = 19     # context: tile we just drew (response variant)
    LAST_DISCARDED_TILE = 20 # context: tile someone just discarded
    PHASE = 21
    ACTION_HINT = 22         # 0=self_action, 1=response, 2=chankan, 3=other
    VISIBLE_COUNT = 23       # per tile_type: number of visible copies
    FURITEN_AREA = 24        # per (player, tile_type): is in player's discards?
    ROUND_INDEX = 25         # 0..3 (E1..E4 / S1..S4 within current wind)
    DEALER_SEAT = 26         # absolute oya seat 0..3
    FUURO_FROM = 27          # per call group: who it was taken from
    GAME_NUMBER = 28         # (game_wind - East) * 4 + oya, mirrors V2
    TURN_INDEX = 29          # current turn number


NUM_SEGMENTS = max(SegmentType) + 1

#: Maximum supported sequence length. Worst-case budget:
#:   hand 14 + tsumo 1 + 4*fuuro_tiles 4*4 + 4*fuuro_from 4 + 4*river 96
#:   + dora_ind 5 + ura 5 + actual_dora 5 + per-player flags 16 + globals 12
#:   + visible_count 34 + furiten 4*34 = 136 + 14 + 16 + 16 + 12 + 96 + 15 + 34
#:   + 136 ~= 350. Use 360 for safety.
MAX_SEQ_LEN = 360

#: Per-token feature vector (segment, tile, count, who, extra).
TOKEN_FEATURES = 5

#: Per-token scalar dimension.
SCALAR_DIM = 4


# ---------------------------------------------------------------------------
# Action space (mirrors env_pymahjong.MahjongEnv.ACTION_DIM = 54)
# ---------------------------------------------------------------------------

ACTION_DIM = 54

A_DISCARD_BASE = 0           # 0..33
A_DISCARD_RED5M = 34
A_DISCARD_RED5P = 35
A_DISCARD_RED5S = 36
A_CHILEFT = 37
A_CHIMIDDLE = 38
A_CHIRIGHT = 39
A_CHILEFT_USERED = 40
A_CHIMIDDLE_USERED = 41
A_CHIRIGHT_USERED = 42
A_PON = 43
A_PON_USERED = 44
A_ANKAN = 45
A_MINKAN = 46
A_KAKAN = 47
A_RIICHI = 48
A_RON = 49
A_TSUMO = 50
A_PUSH = 51                  # kyushukyuhai
A_PASS_RIICHI = 52
A_PASS_RESPONSE = 53


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tile_id_and_aka(tile_obj) -> tuple:
    """Return ``(base_tile_id, aka_bit)`` for a ``pm.Tile``.

    The base id is the engine's :class:`pm.BaseTile` (0..33). The red-dora
    flag is exposed as a *bit* in ``extra`` instead of a dedicated tile id,
    which mirrors V2's encoding and shrinks the tile vocabulary.
    """
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


# CallGroup::Type values (must match Mahjong/Tile.h)
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


def _norm_score(score: int) -> float:
    """Map a raw score to a roughly zero-mean float (0 at 25000, ~+/-1 around 0/50000)."""
    return (float(score) - 25000.0) / 25000.0


def _bucket_score(score: int) -> int:
    """Bucket score in 5k units, clamped to [0, 16] (~ -10000..70000)."""
    s = max(-10000, min(int(score), 70000))
    return int((s + 10000) // 5000)


# ---------------------------------------------------------------------------
# Action / phase classification helpers
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


# ---------------------------------------------------------------------------
# TokenizedObservation container
# ---------------------------------------------------------------------------

@dataclass
class TokenizedObservation:
    tokens: np.ndarray         # (MAX_SEQ_LEN, TOKEN_FEATURES) uint8
    scalars: np.ndarray        # (MAX_SEQ_LEN, SCALAR_DIM)  float32
    attention_mask: np.ndarray # (MAX_SEQ_LEN,) bool
    action_mask: np.ndarray    # (ACTION_DIM,) bool
    seq_len: int
    current_player: int
    phase: int

    def to_dict(self):
        return {
            "tokens": self.tokens,
            "scalars": self.scalars,
            "attention_mask": self.attention_mask,
            "action_mask": self.action_mask,
            "seq_len": np.int32(self.seq_len),
            "current_player": np.int32(self.current_player),
            "phase": np.int32(self.phase),
        }


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class MahjongTokenizer:
    """Build :class:`TokenizedObservation` from a ``pm.Table`` instance."""

    def __init__(
        self,
        max_seq_len: int = MAX_SEQ_LEN,
        include_oracle: bool = False,
    ):
        if max_seq_len > MAX_SEQ_LEN:
            raise ValueError(
                f"max_seq_len {max_seq_len} > MAX_SEQ_LEN {MAX_SEQ_LEN}"
            )
        self.max_seq_len = max_seq_len
        self.include_oracle = include_oracle
        self._tokens = np.zeros((max_seq_len, TOKEN_FEATURES), dtype=np.uint8)
        self._scalars = np.zeros((max_seq_len, SCALAR_DIM), dtype=np.float32)
        self._mask = np.zeros((max_seq_len,), dtype=bool)
        self._action_mask = np.zeros((ACTION_DIM,), dtype=bool)

    # -- low-level token push -------------------------------------------------

    def _push(
        self,
        idx: int,
        segment: int,
        tile: int,
        count: int,
        who: int,
        extra: int,
        scalars: Optional[Sequence[float]] = None,
    ) -> int:
        if idx >= self.max_seq_len:
            return idx
        t = self._tokens[idx]
        t[0] = segment & 0xFF
        t[1] = tile & 0xFF
        t[2] = count & 0xFF
        t[3] = who & 0xFF
        t[4] = extra & 0xFF
        if scalars is not None:
            for j, v in enumerate(scalars[:SCALAR_DIM]):
                self._scalars[idx, j] = v
        self._mask[idx] = True
        return idx + 1

    # -- main encoder --------------------------------------------------------

    def encode(
        self,
        table,
        current_player: int,
        riichi_stage2: bool = False,
    ) -> TokenizedObservation:
        if pm is None:
            raise RuntimeError(
                "MahjongPyWrapper not importable; install pymahjong first."
            )

        self._tokens.fill(0)
        self._scalars.fill(0)
        self._mask.fill(False)
        self._action_mask.fill(False)
        idx = 0

        players = table.players
        me = players[current_player]

        def rel(seat: int) -> int:
            return (seat - current_player) % 4

        phase = int(table.get_phase())
        in_response = is_response_phase(phase) or is_chankan_phase(phase)

        # ---------- 1. SELF HAND (separate the just-drawn tsumo tile) -------
        hand_tiles = list(me.hand)

        # Determine the "tsumo" tile (the one just drawn). For self-action
        # phases this is the most recently drawn tile -- the engine doesn't
        # mark it explicitly so we conservatively treat the *last* tile of
        # the hand as the tsumo when the current player is to move and the
        # hand size is 14 / 2 / 5 / 8 / 11 (multiples of 3 + 2 i.e. not just
        # discarded). We always emit it via SELF_TSUMO so the model can tell
        # them apart.
        tsumo_tile = None
        if (
            current_player == acting_player(phase)
            and is_self_phase(phase)
            and len(hand_tiles) % 3 == 2
        ):
            tsumo_tile = hand_tiles[-1]
            hand_tiles = hand_tiles[:-1]

        hand_counts = np.zeros((NUM_BASE_TILES, 2), dtype=np.int32)  # [tile][aka]
        for tile_obj in hand_tiles:
            b, a = _tile_id_and_aka(tile_obj)
            hand_counts[b, a] += 1
        for b in range(NUM_BASE_TILES):
            for a in (0, 1):
                c = int(hand_counts[b, a])
                if c > 0:
                    idx = self._push(idx, SegmentType.SELF_HAND, b, c, 0, a)

        if tsumo_tile is not None:
            b, a = _tile_id_and_aka(tsumo_tile)
            idx = self._push(idx, SegmentType.SELF_TSUMO, b, 1, 0, a)

        # ---------- 2. FUUROS ---------------------------------------------
        # For each call group emit:
        #   - one FUURO_FROM summary token (who=meld_owner_relative,
        #       count=meld_type, extra=from_relative)
        #   - one tile token per meld tile (SELF_FUURO / OPP_FUURO)
        for seat in range(4):
            p = players[seat]
            fuuros = _safe(p.get_fuuros, []) or []
            seg = SegmentType.SELF_FUURO if seat == current_player else SegmentType.OPP_FUURO
            owner_r = rel(seat)
            for cg in fuuros:
                meld_type = int(cg.type)
                from_r = _fuuro_from_r(meld_type, getattr(cg, "take", 0))
                idx = self._push(
                    idx,
                    SegmentType.FUURO_FROM,
                    TILE_PAD,
                    meld_type & 0xFF,
                    owner_r,
                    from_r,
                )
                for tile_obj in cg.tiles:
                    b, a = _tile_id_and_aka(tile_obj)
                    idx = self._push(idx, seg, b, 1, owner_r, a | (meld_type << 1))

        # ---------- 3. RIVERS ---------------------------------------------
        for seat in range(4):
            p = players[seat]
            river = _safe(lambda p=p: p.get_river().river, []) or []
            seg = SegmentType.SELF_RIVER if seat == current_player else SegmentType.OPP_RIVER
            r = rel(seat)
            for rt in river:
                base, aka = _tile_id_and_aka(rt.tile)
                # Pack the discard order (0..95 globally) into ``count``;
                # ``extra`` carries flags only.
                num = min(int(rt.number), 95)
                extra = aka | ((1 if rt.riichi else 0) << 1) | ((1 if rt.fromhand else 0) << 2)
                idx = self._push(idx, seg, base, num, r, extra)

        # ---------- 4. DORA INDICATORS / ACTUAL DORA / URA -----------------
        n_active = int(getattr(table, "n_active_dora", 1))
        for di in list(table.dora_indicator)[:n_active]:
            b, a = _tile_id_and_aka(di)
            idx = self._push(idx, SegmentType.DORA_INDICATOR, b, 1, 4, a)

        # Actual dora (engine-computed, 1 per indicator). pm exposes get_dora()
        # returning a list of pm.BaseTile.
        dora_list = _safe(table.get_dora, []) or []
        for bt in dora_list[:n_active]:
            idx = self._push(idx, SegmentType.ACTUAL_DORA, _basetile_id(bt), 1, 4, 0)

        # Uradora is only meaningful at game-end after a riichi win.
        ura_indicators = _safe(lambda: list(table.uradora_indicator), []) or []
        ura_dora = _safe(table.get_ura_dora, []) or []
        # Only reveal if engine says game over OR if explicitly enabled via me.riichi
        # Conservatively: only reveal if game over.
        if int(phase) == int(pm.PhaseEnum.GAME_OVER):
            for di in ura_indicators[:n_active]:
                b, a = _tile_id_and_aka(di)
                idx = self._push(idx, SegmentType.URA_DORA_INDICATOR, b, 1, 4, a)

        # ---------- 5. PER-PLAYER FLAGS / SCORES --------------------------
        scores = [int(players[s].score) for s in range(4)]
        max_other = max(s for i, s in enumerate(scores) if i != current_player)
        for seat in range(4):
            p = players[seat]
            r = rel(seat)
            idx = self._push(
                idx, SegmentType.PLAYER_RIICHI, TILE_PAD,
                1 if p.riichi else 0, r,
                1 if getattr(p, "double_riichi", False) else 0,
            )
            idx = self._push(
                idx, SegmentType.PLAYER_IPPATSU, TILE_PAD,
                1 if p.ippatsu else 0, r, 0,
            )
            idx = self._push(
                idx, SegmentType.PLAYER_MENZEN, TILE_PAD,
                1 if p.menzen else 0, r, 0,
            )
            score = int(p.score)
            score_norm = _norm_score(score)
            lead_gap = (score - max_other) / 25000.0 if seat == current_player else 0.0
            idx = self._push(
                idx, SegmentType.PLAYER_SCORE, TILE_PAD,
                _bucket_score(score), r, 0,
                scalars=(score_norm, lead_gap, 0.0, 0.0),
            )

        # ---------- 6. GLOBAL CONTEXT --------------------------------------
        game_wind = int(table.game_wind)
        idx = self._push(idx, SegmentType.GAME_WIND, TILE_PAD, game_wind, 4, 0)
        idx = self._push(idx, SegmentType.SELF_WIND, TILE_PAD, int(me.wind), 0, 0)
        oya = int(table.oya)
        # Round index = oya for the wind-round (East1..East4 -> 0..3)
        round_index = oya & 0x3
        # game_number mirrors V2: (wind - East)*4 + oya
        game_number = ((game_wind - int(pm.Wind.East)) * 4 + oya) & 0xFF
        idx = self._push(idx, SegmentType.ROUND_INDEX, TILE_PAD, round_index, 4, 0)
        idx = self._push(idx, SegmentType.DEALER_SEAT, TILE_PAD, oya, 4, rel(oya))
        idx = self._push(idx, SegmentType.GAME_NUMBER, TILE_PAD, game_number, 4, 0)

        honba = int(getattr(table, "honba", 0))
        kyoutaku = int(getattr(table, "riichibo", 0))
        idx = self._push(
            idx, SegmentType.HONBA, TILE_PAD, min(honba, 255), 4, 0,
            scalars=(honba / 8.0, 0.0, 0.0, 0.0),
        )
        idx = self._push(
            idx, SegmentType.KYOUTAKU, TILE_PAD, min(kyoutaku, 255), 4, 0,
            scalars=(kyoutaku / 4.0, 0.0, 0.0, 0.0),
        )

        remaining = int(_safe(table.get_remain_tile, 0) or 0)
        idx = self._push(
            idx, SegmentType.REMAINING_TILES, TILE_PAD, min(remaining, 255), 4, 0,
            scalars=(remaining / 70.0, 0.0, 0.0, 0.0),
        )

        turn = int(getattr(table, "turn", 0))
        idx = self._push(
            idx, SegmentType.TURN_INDEX, TILE_PAD, min(turn, 255), 4, 0,
            scalars=(turn / 18.0, 0.0, 0.0, 0.0),
        )

        # ---------- 7. CONTEXT TILES (split LAST_DISCARD into two) --------
        sel_tile = _safe(table.get_selected_action_tile, None)
        sel_who = int(_safe(table.who_make_selection, 0) or 0)
        if sel_tile is not None:
            b, a = _tile_id_and_aka(sel_tile)
            if in_response:
                # someone discarded -> we may respond
                idx = self._push(
                    idx, SegmentType.LAST_DISCARDED_TILE, b, 1, rel(sel_who), a,
                )
            elif current_player == sel_who and is_self_phase(phase) and tsumo_tile is None:
                # We just drew a tile (and SELF_TSUMO above wasn't emitted)
                idx = self._push(
                    idx, SegmentType.SELF_TSUMO_TILE, b, 1, 0, a,
                )

        idx = self._push(
            idx, SegmentType.PHASE, TILE_PAD, phase, 4, 1 if riichi_stage2 else 0,
        )
        action_hint = (
            0 if is_self_phase(phase)
            else 1 if is_response_phase(phase)
            else 2 if is_chankan_phase(phase)
            else 3
        )
        idx = self._push(idx, SegmentType.ACTION_HINT, TILE_PAD, action_hint, 4, 0)

        # ---------- 8. VISIBLE-COUNT (per tile_type, 0..4) ----------------
        visible = self._compute_visible_counts(table, players, me)
        for b in range(NUM_BASE_TILES):
            c = int(visible[b])
            if c > 0:
                idx = self._push(idx, SegmentType.VISIBLE_COUNT, b, c, 4, 0)

        # ---------- 9. FURITEN AREA (per player, set of discarded tiles) --
        for seat in range(4):
            p = players[seat]
            r = rel(seat)
            seen = set()
            river = _safe(lambda p=p: p.get_river().river, []) or []
            for rt in river:
                seen.add(int(rt.tile.tile))
            for b in sorted(seen):
                idx = self._push(idx, SegmentType.FURITEN_AREA, b, 1, r, 0)

        # ---------- 10. ORACLE (optional) ---------------------------------
        if self.include_oracle:
            for seat in range(4):
                if seat == current_player:
                    continue
                p = players[seat]
                opp_counts = np.zeros((NUM_BASE_TILES, 2), dtype=np.int32)
                for tile_obj in _safe(lambda p=p: list(p.hand), []) or []:
                    b, a = _tile_id_and_aka(tile_obj)
                    opp_counts[b, a] += 1
                r = rel(seat)
                for b in range(NUM_BASE_TILES):
                    for a in (0, 1):
                        c = int(opp_counts[b, a])
                        if c > 0:
                            idx = self._push(idx, SegmentType.SELF_HAND, b, c, r, a | 0x80)

        # ---------- 11. ACTION MASK ---------------------------------------
        self._fill_action_mask(table, current_player, riichi_stage2, sel_tile)

        return TokenizedObservation(
            tokens=self._tokens.copy(),
            scalars=self._scalars.copy(),
            attention_mask=self._mask.copy(),
            action_mask=self._action_mask.copy(),
            seq_len=idx,
            current_player=current_player,
            phase=phase,
        )

    # ------------------------------------------------------------------
    # Visible-count computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_visible_counts(table, players, me) -> np.ndarray:
        """Return a (34,) array with the number of *publicly visible* copies
        of each base tile, as in V2's pos_discarded_number_*.

        Visible = self's hand + everyone's rivers + everyone's fuuros + face-up
        dora indicators. (Other players' closed hands and the wall are hidden.)
        """
        v = np.zeros(NUM_BASE_TILES, dtype=np.int32)
        for tile_obj in list(me.hand):
            v[int(tile_obj.tile)] += 1
        n_active = int(getattr(table, "n_active_dora", 1))
        for di in list(table.dora_indicator)[:n_active]:
            v[int(di.tile)] += 1
        for seat in range(4):
            p = players[seat]
            for rt in _safe(lambda p=p: p.get_river().river, []) or []:
                v[int(rt.tile.tile)] += 1
            for cg in _safe(p.get_fuuros, []) or []:
                for tile_obj in cg.tiles:
                    v[int(tile_obj.tile)] += 1
        # Cap at 4 (an indicator could theoretically duplicate, but safety)
        np.clip(v, 0, 4, out=v)
        return v

    # ------------------------------------------------------------------
    # Action mask
    # ------------------------------------------------------------------

    def _fill_action_mask(self, table, current_player, riichi_stage2, last_discard_tile):
        m = self._action_mask
        if riichi_stage2:
            m[A_RIICHI] = True
            m[A_PASS_RIICHI] = True
            return

        phase = int(table.get_phase())
        if is_self_phase(phase):
            actions = table.get_self_actions()
            is_self = True
        elif is_response_phase(phase) or is_chankan_phase(phase):
            actions = table.get_response_actions()
            is_self = False
        else:
            return

        # last discarded tile (the one being responded to). For chi disambig:
        chi_tile_id = None
        if last_discard_tile is not None and not is_self:
            chi_tile_id = int(last_discard_tile.tile)

        for sel in actions:
            self._mask_one_action(sel, m, is_self=is_self, chi_tile_id=chi_tile_id)

    @staticmethod
    def _classify_chi(chi_tile_id: int, hand_tiles) -> int:
        """Return ChiLeft=0 / ChiMiddle=1 / ChiRight=2 from (taken, hand_pair).

        Mirrors :file:`Mahjong/Encoding/TrainingDataEncodingV1.cpp` line ~150::

            if (chi_tile > hand0) {
                if (chi_tile < hand1) middle
                else                  right
            } else                    left
        """
        h = sorted(int(t.tile) for t in hand_tiles)
        if chi_tile_id < h[0]:
            return 0  # left
        if chi_tile_id > h[1]:
            return 2  # right
        return 1  # middle

    def _mask_one_action(self, sel, m, is_self: bool, chi_tile_id: Optional[int]):
        try:
            base = int(sel.action)
            tiles = list(sel.correspond_tiles)
        except Exception:  # noqa: BLE001
            return
        BA = pm.BaseAction
        if is_self and base == int(BA.Discard):
            if not tiles:
                return
            t = tiles[0]
            base_t = int(t.tile)
            m[A_DISCARD_BASE + base_t] = True
            if getattr(t, "red_dora", False):
                if base_t == 4:
                    m[A_DISCARD_RED5M] = True
                elif base_t == 13:
                    m[A_DISCARD_RED5P] = True
                elif base_t == 22:
                    m[A_DISCARD_RED5S] = True
        elif base == int(BA.Chi):
            if chi_tile_id is None or len(tiles) < 2:
                # Conservatively allow all three chi variants
                m[A_CHILEFT] = m[A_CHIMIDDLE] = m[A_CHIRIGHT] = True
                if any(getattr(t, "red_dora", False) for t in tiles):
                    m[A_CHILEFT_USERED] = m[A_CHIMIDDLE_USERED] = m[A_CHIRIGHT_USERED] = True
                return
            kind = self._classify_chi(chi_tile_id, tiles)
            slot = (A_CHILEFT, A_CHIMIDDLE, A_CHIRIGHT)[kind]
            slot_red = (A_CHILEFT_USERED, A_CHIMIDDLE_USERED, A_CHIRIGHT_USERED)[kind]
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            if used_red:
                m[slot_red] = True
            else:
                m[slot] = True
        elif base == int(BA.Pon):
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            if used_red:
                m[A_PON_USERED] = True
            else:
                m[A_PON] = True
        elif base == int(BA.AnKan):
            m[A_ANKAN] = True
        elif base == int(BA.Kan):
            m[A_MINKAN] = True
        elif base == int(BA.KaKan):
            m[A_KAKAN] = True
        elif base == int(BA.Riichi):
            m[A_RIICHI] = True
        elif base == int(BA.Ron) or base == int(BA.ChanKan) or base == int(BA.ChanAnKan):
            m[A_RON] = True
        elif base == int(BA.Tsumo):
            m[A_TSUMO] = True
        elif base == int(BA.Kyushukyuhai):
            m[A_PUSH] = True
        elif base == int(BA.Pass):
            m[A_PASS_RESPONSE] = True


# ---------------------------------------------------------------------------
# Field vocabulary (used by the model's embedding tables AND by the cache
# schema fingerprint -- changes here invalidate any on-disk cache)
# ---------------------------------------------------------------------------

#: Maximum value the river-number bit-pack can hold (5 bits).
_MAX_RIVER_NUMBER = 32

FIELD_VOCAB = {
    "segment": NUM_SEGMENTS,
    "tile": TILE_VOCAB_SIZE,
    "count": 96,
    "who": 5,
    "extra": 256,
}


# ---------------------------------------------------------------------------
# to_string interfaces (for round-trip verification)
# ---------------------------------------------------------------------------

def _fmt_player_line(label: str, vals_by_player) -> str:
    return f"{label}: " + " ".join(str(int(v)) for v in vals_by_player)


def state_to_string(table, current_player: int, riichi_stage2: bool = False) -> str:
    """Pretty-print the *engine* state (relative to ``current_player``).

    This describes exactly the same set of facts that the tokenizer encodes,
    in a fixed canonical order. Pair with :func:`tokens_to_string` to verify
    that the encoding is lossless.
    """
    if pm is None:
        raise RuntimeError("MahjongPyWrapper not importable")

    players = table.players
    me = players[current_player]
    phase = int(table.get_phase())

    def rel(seat):
        return (seat - current_player) % 4

    lines = []
    lines.append("== STATE ==")
    lines.append(f"PLAYER: self={current_player}")
    lines.append(f"PHASE: {phase} riichi_stage2={int(riichi_stage2)}")

    game_wind = int(table.game_wind)
    oya = int(table.oya)
    round_index = oya & 3
    game_number = ((game_wind - int(pm.Wind.East)) * 4 + oya) & 0xFF
    honba = int(getattr(table, "honba", 0))
    kyoutaku = int(getattr(table, "riichibo", 0))
    remaining = int(_safe(table.get_remain_tile, 0) or 0)
    turn = int(getattr(table, "turn", 0))

    lines.append(
        f"ROUND: game_wind={_WIND_STR[game_wind]} round={round_index} "
        f"oya={oya} game_no={game_number} honba={honba} kyoutaku={kyoutaku}"
    )
    lines.append(f"COUNTERS: remaining={remaining} turn={turn}")
    lines.append(f"SELF_WIND: {_WIND_STR[int(me.wind)]}")

    scores = [int(players[s].score) for s in range(4)]
    lines.append("SCORES: " + " ".join(str(s) for s in scores))
    lines.append(_fmt_player_line(
        "RIICHI",
        [1 if players[s].riichi else 0 for s in range(4)],
    ))
    lines.append(_fmt_player_line(
        "IPPATSU",
        [1 if players[s].ippatsu else 0 for s in range(4)],
    ))
    lines.append(_fmt_player_line(
        "MENZEN",
        [1 if players[s].menzen else 0 for s in range(4)],
    ))

    # Hand (separate the tsumo tile, if any)
    hand_tiles = list(me.hand)
    tsumo_tile = None
    if (
        current_player == acting_player(phase)
        and is_self_phase(phase)
        and len(hand_tiles) % 3 == 2
    ):
        tsumo_tile = hand_tiles[-1]
        hand_tiles = hand_tiles[:-1]
    hand_strs = sorted(
        tile_str(*_tile_id_and_aka(t)) for t in hand_tiles
    )
    lines.append("HAND: " + " ".join(hand_strs))
    if tsumo_tile is not None:
        lines.append("TSUMO: " + tile_str(*_tile_id_and_aka(tsumo_tile)))
    else:
        lines.append("TSUMO: -")

    # Fuuros (iterate in relative-seat order to match tokens_to_string)
    for r in range(4):
        seat = (current_player + r) % 4
        p = players[seat]
        cgs = _safe(p.get_fuuros, []) or []
        parts = []
        for cg in cgs:
            mt = int(cg.type)
            # Infer source seat from CallGroup.take using riichi rules.
            from_r = _fuuro_from_r(mt, getattr(cg, "take", 0))
            tiles = " ".join(tile_str(*_tile_id_and_aka(t)) for t in cg.tiles)
            parts.append(f"[type={mt} from_r={from_r} tiles={tiles}]")
        lines.append(f"FUURO[r={r}]: " + (" ".join(parts) if parts else "-"))

    # Rivers (relative-seat order)
    for r in range(4):
        seat = (current_player + r) % 4
        p = players[seat]
        river = _safe(lambda p=p: p.get_river().river, []) or []
        parts = []
        for rt in river:
            base, aka = _tile_id_and_aka(rt.tile)
            ri = "R" if rt.riichi else "."
            fh = "H" if rt.fromhand else "h"
            parts.append(f"{tile_str(base, aka)}#{int(rt.number)}{ri}{fh}")
        lines.append(f"RIVER[r={r}]: " + (" ".join(parts) if parts else "-"))

    # Dora
    n_active = int(getattr(table, "n_active_dora", 1))
    di_strs = [tile_str(*_tile_id_and_aka(d))
               for d in list(table.dora_indicator)[:n_active]]
    lines.append("DORA_IND: " + " ".join(di_strs) if di_strs else "DORA_IND: -")
    dora_list = _safe(table.get_dora, []) or []
    da_strs = [tile_str(_basetile_id(b), 0) for b in dora_list[:n_active]]
    lines.append("DORA: " + " ".join(da_strs) if da_strs else "DORA: -")
    if int(phase) == int(pm.PhaseEnum.GAME_OVER):
        ura_indicators = _safe(lambda: list(table.uradora_indicator), []) or []
        ui_strs = [tile_str(*_tile_id_and_aka(d))
                   for d in ura_indicators[:n_active]]
        lines.append(
            "URA_DORA_IND: " + (" ".join(ui_strs) if ui_strs else "-")
        )

    # Visible count
    visible = MahjongTokenizer._compute_visible_counts(table, players, me)
    vis_parts = [f"{_TILE_STR[b]}={int(visible[b])}"
                 for b in range(NUM_BASE_TILES) if visible[b] > 0]
    lines.append("VISIBLE: " + (" ".join(vis_parts) if vis_parts else "-"))

    # Furiten area (per relative seat)
    for r in range(4):
        seat = (current_player + r) % 4
        p = players[seat]
        river = _safe(lambda p=p: p.get_river().river, []) or []
        seen = sorted(set(int(rt.tile.tile) for rt in river))
        parts = [_TILE_STR[b] for b in seen]
        lines.append(f"FURITEN[r={r}]: " + (" ".join(parts) if parts else "-"))

    # Context tiles
    sel_tile = _safe(table.get_selected_action_tile, None)
    sel_who = int(_safe(table.who_make_selection, 0) or 0)
    in_response = is_response_phase(phase) or is_chankan_phase(phase)
    if sel_tile is not None and in_response:
        b, a = _tile_id_and_aka(sel_tile)
        lines.append(
            f"LAST_DISCARDED: {tile_str(b, a)} from_r={rel(sel_who)}"
        )
    elif (
        sel_tile is not None
        and current_player == sel_who
        and is_self_phase(phase)
        and tsumo_tile is None
    ):
        b, a = _tile_id_and_aka(sel_tile)
        lines.append(f"SELF_TSUMO_TILE: {tile_str(b, a)}")

    return "\n".join(lines)


def tokens_to_string(obs: TokenizedObservation) -> str:
    """Reconstruct the canonical state string from a TokenizedObservation.

    Iterates the token sequence and groups by segment, producing exactly the
    text :func:`state_to_string` would have emitted. Used as a round-trip
    sanity check (encode -> decode -> compare).
    """
    seq = obs.tokens[: obs.seq_len]
    scalars = obs.scalars[: obs.seq_len]

    by_seg = {int(s): [] for s in SegmentType}
    for i, tok in enumerate(seq):
        s, t, c, w, e = (int(x) for x in tok)
        by_seg.setdefault(s, []).append((i, t, c, w, e))

    def first(seg):
        v = by_seg.get(int(seg), [])
        return v[0] if v else None

    lines = []
    lines.append("== STATE ==")

    lines.append(f"PLAYER: self={obs.current_player}")

    pf = first(SegmentType.PHASE)
    phase = int(pf[2]) if pf else int(obs.phase)
    rs2 = int(pf[4]) if pf else 0
    lines.append(f"PHASE: {phase} riichi_stage2={rs2}")

    gw = first(SegmentType.GAME_WIND)
    rd = first(SegmentType.ROUND_INDEX)
    ds = first(SegmentType.DEALER_SEAT)
    gn = first(SegmentType.GAME_NUMBER)
    hb = first(SegmentType.HONBA)
    ky = first(SegmentType.KYOUTAKU)
    rt_ = first(SegmentType.REMAINING_TILES)
    tn = first(SegmentType.TURN_INDEX)
    sw = first(SegmentType.SELF_WIND)

    game_wind = int(gw[2]) if gw else 0
    round_index = int(rd[2]) if rd else 0
    oya = int(ds[2]) if ds else 0
    game_number = int(gn[2]) if gn else 0
    honba = int(hb[2]) if hb else 0
    kyoutaku = int(ky[2]) if ky else 0
    remaining = int(rt_[2]) if rt_ else 0
    turn = int(tn[2]) if tn else 0
    self_wind = int(sw[2]) if sw else 0

    lines.append(
        f"ROUND: game_wind={_WIND_STR[game_wind]} round={round_index} "
        f"oya={oya} game_no={game_number} honba={honba} kyoutaku={kyoutaku}"
    )
    lines.append(f"COUNTERS: remaining={remaining} turn={turn}")
    lines.append(f"SELF_WIND: {_WIND_STR[self_wind]}")

    # Scores: PLAYER_SCORE tokens carry exact value via scalars[0]
    scores_by_r = {}
    for i, t, c, w, e in by_seg.get(int(SegmentType.PLAYER_SCORE), []):
        score_norm = float(scalars[i, 0])
        scores_by_r[w] = int(round(score_norm * 25000.0 + 25000.0))
    # Convert relative -> absolute order (current_player at r=0)
    cp = obs.current_player
    abs_scores = [0] * 4
    for r, sc in scores_by_r.items():
        abs_scores[(cp + r) % 4] = sc
    lines.append("SCORES: " + " ".join(str(s) for s in abs_scores))

    # Per-player flags (in absolute seat order)
    def flag_by_seat(seg, idx_field=2):
        out = [0] * 4
        for i, t, c, w, e in by_seg.get(int(seg), []):
            seat = (cp + w) % 4
            out[seat] = int(c if idx_field == 2 else e)
        return out

    lines.append(_fmt_player_line("RIICHI", flag_by_seat(SegmentType.PLAYER_RIICHI)))
    lines.append(_fmt_player_line("IPPATSU", flag_by_seat(SegmentType.PLAYER_IPPATSU)))
    lines.append(_fmt_player_line("MENZEN", flag_by_seat(SegmentType.PLAYER_MENZEN)))

    # Hand
    hand_strs = []
    for i, t, c, w, e in by_seg.get(int(SegmentType.SELF_HAND), []):
        if w != 0:
            continue  # oracle entry
        for _ in range(c):
            hand_strs.append(tile_str(t, e & 1))
    hand_strs.sort()
    lines.append("HAND: " + " ".join(hand_strs))

    ts = first(SegmentType.SELF_TSUMO)
    if ts is not None:
        _, t, c, w, e = ts
        lines.append("TSUMO: " + tile_str(t, e & 1))
    else:
        lines.append("TSUMO: -")

    # Fuuros - need to combine FUURO_FROM tokens with SELF_FUURO/OPP_FUURO tile tokens
    # by their relative position in the stream (FUURO_FROM precedes its tiles)
    # We rebuild per-relative-seat list of [(meld_type, from_r, [(tile, aka), ...])]
    fuuro_groups = {0: [], 1: [], 2: [], 3: []}
    cur_owner = None
    cur_group = None
    for i, tok in enumerate(seq):
        s, t, c, w, e = (int(x) for x in tok)
        if s == int(SegmentType.FUURO_FROM):
            cur_owner = w
            cur_group = (c, e, [])  # (meld_type, from_r, tiles)
            fuuro_groups[cur_owner].append(cur_group)
        elif s in (int(SegmentType.SELF_FUURO), int(SegmentType.OPP_FUURO)):
            if cur_group is not None and w == cur_owner:
                cur_group[2].append((t, e & 1))

    for r in range(4):
        parts = []
        for mt, from_r, tiles in fuuro_groups[r]:
            ts_ = " ".join(tile_str(b, a) for b, a in tiles)
            parts.append(f"[type={mt} from_r={from_r} tiles={ts_}]")
        lines.append(f"FUURO[r={r}]: " + (" ".join(parts) if parts else "-"))

    # Rivers - per relative seat, sort by stored number (in ``count`` field)
    river_by_r = {0: [], 1: [], 2: [], 3: []}
    for seg in (SegmentType.SELF_RIVER, SegmentType.OPP_RIVER):
        for i, t, c, w, e in by_seg.get(int(seg), []):
            num = c
            aka = e & 1
            riichi = (e >> 1) & 1
            fromhand = (e >> 2) & 1
            river_by_r[w].append((num, t, aka, riichi, fromhand))
    for r in range(4):
        river_by_r[r].sort(key=lambda x: x[0])
        parts = []
        for num, t, aka, riichi, fromhand in river_by_r[r]:
            ri = "R" if riichi else "."
            fh = "H" if fromhand else "h"
            parts.append(f"{tile_str(t, aka)}#{num}{ri}{fh}")
        lines.append(f"RIVER[r={r}]: " + (" ".join(parts) if parts else "-"))

    # Dora
    di_strs = [tile_str(t, e & 1) for i, t, c, w, e in by_seg.get(int(SegmentType.DORA_INDICATOR), [])]
    lines.append("DORA_IND: " + (" ".join(di_strs) if di_strs else "-"))
    da_strs = [tile_str(t, 0) for i, t, c, w, e in by_seg.get(int(SegmentType.ACTUAL_DORA), [])]
    lines.append("DORA: " + (" ".join(da_strs) if da_strs else "-"))
    ura = by_seg.get(int(SegmentType.URA_DORA_INDICATOR), [])
    if ura:
        ui_strs = [tile_str(t, e & 1) for i, t, c, w, e in ura]
        lines.append("URA_DORA_IND: " + " ".join(ui_strs))

    # Visible count
    vc = by_seg.get(int(SegmentType.VISIBLE_COUNT), [])
    vc.sort(key=lambda x: x[1])
    vis_parts = [f"{_TILE_STR[t]}={c}" for i, t, c, w, e in vc]
    lines.append("VISIBLE: " + (" ".join(vis_parts) if vis_parts else "-"))

    # Furiten (per relative seat)
    fur_by_r = {0: [], 1: [], 2: [], 3: []}
    for i, t, c, w, e in by_seg.get(int(SegmentType.FURITEN_AREA), []):
        fur_by_r[w].append(t)
    for r in range(4):
        seen = sorted(fur_by_r[r])
        parts = [_TILE_STR[b] for b in seen]
        lines.append(f"FURITEN[r={r}]: " + (" ".join(parts) if parts else "-"))

    # Context tiles
    ld = first(SegmentType.LAST_DISCARDED_TILE)
    if ld is not None:
        i, t, c, w, e = ld
        lines.append(f"LAST_DISCARDED: {tile_str(t, e & 1)} from_r={w}")
    st = first(SegmentType.SELF_TSUMO_TILE)
    if st is not None:
        i, t, c, w, e = st
        lines.append(f"SELF_TSUMO_TILE: {tile_str(t, e & 1)}")

    return "\n".join(lines)

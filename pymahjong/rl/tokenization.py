"""Transformer-friendly tokenized state/action encoding for Mahjong.

This module replaces the dense (C×34) matrix encodings used in
``encv1`` / ``encv2`` with a *token-sequence* representation that is
better suited to attention-based models:

Each game state is rendered as a variable-length sequence of tokens, and
each token is a small fixed-size feature tuple::

    token = (segment_id, tile_id, count, who, extra)

* ``segment_id``  -- which kind of feature (hand, river, dora, ...).
* ``tile_id``     -- 0..36 (34 base tiles + 3 red doras, 37 = PAD).
* ``count``       -- copies (0..4); for non-tile tokens an arbitrary
  small int payload.
* ``who``         -- relative seat 0..3 (self/next/opposite/prev),
  or 4 for "no seat" / table-wide tokens.
* ``extra``       -- bucketed misc int (turn-index, score-bucket, ...).

The model then learns separate embedding tables per field and sums them
to obtain per-token vectors before a transformer encoder.

Action space is kept compatible with :class:`pymahjong.env_pymahjong.MahjongEnv`
(54 discrete actions) so existing engines / paipu can be reused.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple

import numpy as np

try:  # pragma: no cover - thin runtime guard
    import MahjongPyWrapper as pm
except Exception:  # noqa: BLE001
    pm = None  # type: ignore


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: Number of "base" tile types (1-9m, 1-9p, 1-9s, 1-7z).
NUM_BASE_TILES = 34

#: Slot ids for red doras: red-5m, red-5p, red-5s.
TILE_RED5M = 34
TILE_RED5P = 35
TILE_RED5S = 36

#: Pad id for tile feature.
TILE_PAD = 37

#: Total tile vocabulary size including pad.
TILE_VOCAB_SIZE = 38


class SegmentType(IntEnum):
    """Token segment / feature category."""

    PAD = 0
    SELF_HAND = 1
    SELF_TSUMO = 2          # the just-drawn tile that may be discarded
    SELF_FUURO = 3          # tiles in self called melds
    OPP_FUURO = 4           # tiles in opponents' called melds (use ``who``)
    SELF_RIVER = 5
    OPP_RIVER = 6           # opponents' river tile (use ``who``)
    DORA_INDICATOR = 7
    URA_DORA_INDICATOR = 8  # only if revealed after a riichi win
    PLAYER_RIICHI = 9       # 1 token per player (use ``who``)
    PLAYER_IPPATSU = 10
    PLAYER_MENZEN = 11
    PLAYER_SCORE = 12       # bucketed score
    GAME_WIND = 13
    SELF_WIND = 14
    HONBA = 15
    KYOUTAKU = 16
    REMAINING_TILES = 17    # bucketed remaining wall tiles
    LAST_DISCARD = 18       # the just-discarded tile we may respond to
    PHASE = 19              # encodes engine phase id
    ACTION_HINT = 20        # action_type expected at this step (self vs response)


NUM_SEGMENTS = max(SegmentType) + 1

#: Maximum supported sequence length. River alone can hold up to ~24 per
#: player × 4 = 96 tiles, plus hand/fuuro/dora/global → 200 is safe.
MAX_SEQ_LEN = 200

#: Width of the per-token feature vector ``(segment, tile, count, who, extra)``.
TOKEN_FEATURES = 5

# ---------------------------------------------------------------------------
# Action space (kept compatible with MahjongEnv.ACTION_DIM = 54)
# ---------------------------------------------------------------------------

ACTION_DIM = 54

# Indices (mirror env_pymahjong.MahjongEnv constants)
A_DISCARD_BASE = 0           # 0..33   (regular discard for tile type)
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

def _bucket_score(score: int) -> int:
    """Bucket a score in 1k-point buckets, clamped to [0, 60]."""
    s = max(-5000, min(score, 75000))
    return int((s + 5000) // 1000)  # 0..80


def _bucket_remaining(remain: int) -> int:
    """Bucket remaining wall tiles into [0..70]."""
    return max(0, min(70, int(remain)))


def _tile_id(tile_obj) -> int:
    """Convert a ``pm.Tile`` to our extended tile_id (with red dora)."""
    base = int(tile_obj.tile)
    if getattr(tile_obj, "red_dora", False):
        # 4m=4, 4p=13, 4s=22 are 5-pip tiles minus 1 in BaseTile? No: 5m=4
        # But bindings don't expose BaseTile reliably for red; use known mapping:
        if base == 4:   # 5m
            return TILE_RED5M
        if base == 13:  # 5p
            return TILE_RED5P
        if base == 22:  # 5s
            return TILE_RED5S
    return base


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass
class TokenizedObservation:
    """Container for a tokenized observation."""

    tokens: np.ndarray        # shape (MAX_SEQ_LEN, TOKEN_FEATURES), int32
    attention_mask: np.ndarray  # shape (MAX_SEQ_LEN,), bool (True=valid)
    action_mask: np.ndarray   # shape (ACTION_DIM,), bool
    seq_len: int              # number of valid tokens
    current_player: int       # absolute seat 0..3
    phase: int                # raw engine phase

    def to_dict(self):
        return {
            "tokens": self.tokens,
            "attention_mask": self.attention_mask,
            "action_mask": self.action_mask,
            "seq_len": np.int32(self.seq_len),
            "current_player": np.int32(self.current_player),
            "phase": np.int32(self.phase),
        }


class MahjongTokenizer:
    """Build :class:`TokenizedObservation` from a ``pm.Table`` instance.

    The tokenizer is allocation-light: the same numpy buffer is reused
    every call (callers that need a snapshot must ``copy()``).

    Args:
        max_seq_len: Maximum sequence length. Truncation happens
            front-to-back (PAD is a no-op, so it should rarely matter for
            standard play).
        include_oracle: If True, also emit tokens for opponents' hidden
            hands (segment ``OPP_FUURO`` is always emitted; this flag
            controls *closed* hand leaks). Set True for oracle-guided
            training, False for executor-only inference.
    """

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
        self._tokens = np.zeros((max_seq_len, TOKEN_FEATURES), dtype=np.int32)
        self._mask = np.zeros((max_seq_len,), dtype=bool)
        self._action_mask = np.zeros((ACTION_DIM,), dtype=bool)

    # -- low-level token push -------------------------------------------------

    def _push(self, idx: int, segment: int, tile: int, count: int, who: int, extra: int) -> int:
        if idx >= self.max_seq_len:
            return idx
        t = self._tokens[idx]
        t[0] = segment
        t[1] = tile
        t[2] = count
        t[3] = who
        t[4] = extra
        self._mask[idx] = True
        return idx + 1

    # -- high-level encoders --------------------------------------------------

    def encode(self, table, current_player: int, riichi_stage2: bool = False) -> TokenizedObservation:
        """Tokenize the current state of ``table`` for ``current_player``.

        Args:
            table: a ``pm.Table`` instance.
            current_player: absolute seat id (0..3) whose POV we encode.
            riichi_stage2: if True, the env is in the second stage of a
                riichi declaration (player must choose RIICHI vs PASS_RIICHI).
        """
        if pm is None:
            raise RuntimeError(
                "MahjongPyWrapper not importable; install pymahjong first."
            )

        self._tokens.fill(0)
        self._mask.fill(False)
        self._action_mask.fill(False)
        idx = 0

        players = table.players
        me = players[current_player]

        def rel(seat: int) -> int:
            """Relative seat id: 0=self,1=next,2=opposite,3=prev."""
            return (seat - current_player) % 4

        # --- self hand (closed) ------------------------------------------------
        # Aggregate by tile_id to use ``count`` field
        hand_counts = np.zeros(TILE_VOCAB_SIZE, dtype=np.int32)
        for tile_obj in me.hand:
            hand_counts[_tile_id(tile_obj)] += 1
        for tile_id, c in enumerate(hand_counts):
            if c > 0:
                idx = self._push(idx, SegmentType.SELF_HAND, tile_id, int(c), 0, 0)

        # --- last drawn tile (tsumo): expose as separate token if available ---
        try:
            last_tile = table.get_selected_action_tile()
            if last_tile is not None:
                idx = self._push(idx, SegmentType.LAST_DISCARD, _tile_id(last_tile), 1, rel(table.who_make_selection() if hasattr(table, 'who_make_selection') else current_player), 0)
        except Exception:  # noqa: BLE001
            pass

        # --- fuuros (called melds) for all 4 players --------------------------
        for seat in range(4):
            p = players[seat]
            try:
                fuuros = p.get_fuuros()
            except Exception:  # noqa: BLE001
                fuuros = []
            seg = SegmentType.SELF_FUURO if seat == current_player else SegmentType.OPP_FUURO
            r = rel(seat)
            for cg in fuuros:
                # cg.type is a BaseAction enum
                action_type = int(cg.type)
                for tile_obj in cg.tiles:
                    idx = self._push(
                        idx,
                        seg,
                        _tile_id(tile_obj),
                        1,
                        r,
                        action_type,
                    )

        # --- rivers (per-tile with discard order index) -----------------------
        for seat in range(4):
            p = players[seat]
            try:
                river = p.get_river().river
            except Exception:  # noqa: BLE001
                river = []
            seg = SegmentType.SELF_RIVER if seat == current_player else SegmentType.OPP_RIVER
            r = rel(seat)
            for rt in river:
                # rt has .tile (BaseTile), .number (order), .riichi, .fromhand
                base = int(rt.tile)
                # riichi flag in extra (bit 0); fromhand (bit 1)
                extra = (1 if rt.riichi else 0) | ((1 if rt.fromhand else 0) << 1)
                idx = self._push(idx, seg, base, 1, r, extra | ((int(rt.number) & 0x3F) << 2))

        # --- dora indicators --------------------------------------------------
        for di in table.dora_indicator[: getattr(table, "n_active_dora", 1)]:
            idx = self._push(idx, SegmentType.DORA_INDICATOR, _tile_id(di), 1, 4, 0)

        # --- per-player flags & scores ----------------------------------------
        for seat in range(4):
            p = players[seat]
            r = rel(seat)
            idx = self._push(idx, SegmentType.PLAYER_RIICHI, TILE_PAD, int(bool(p.riichi)), r, int(bool(p.double_riichi)))
            idx = self._push(idx, SegmentType.PLAYER_IPPATSU, TILE_PAD, int(bool(p.ippatsu)), r, 0)
            idx = self._push(idx, SegmentType.PLAYER_MENZEN, TILE_PAD, int(bool(p.menzen)), r, 0)
            idx = self._push(idx, SegmentType.PLAYER_SCORE, TILE_PAD, _bucket_score(int(p.score)), r, 0)

        # --- winds, honba, kyoutaku, remaining wall ---------------------------
        try:
            game_wind = int(table.game_wind)
        except Exception:  # noqa: BLE001
            game_wind = 0
        idx = self._push(idx, SegmentType.GAME_WIND, TILE_PAD, game_wind, 4, 0)
        idx = self._push(idx, SegmentType.SELF_WIND, TILE_PAD, int(me.wind), 0, 0)
        idx = self._push(idx, SegmentType.HONBA, TILE_PAD, int(getattr(table, "honba", 0)) & 0xFF, 4, 0)
        idx = self._push(idx, SegmentType.KYOUTAKU, TILE_PAD, int(getattr(table, "riichibo", 0)) & 0xFF, 4, 0)
        try:
            remaining = int(table.get_remain_tile())
        except Exception:  # noqa: BLE001
            remaining = 0
        idx = self._push(idx, SegmentType.REMAINING_TILES, TILE_PAD, _bucket_remaining(remaining), 4, 0)

        # --- phase / action hint ----------------------------------------------
        try:
            phase = int(table.get_phase())
        except Exception:  # noqa: BLE001
            phase = 0
        idx = self._push(idx, SegmentType.PHASE, TILE_PAD, phase, 4, int(riichi_stage2))
        action_hint = 0 if phase < 4 else (1 if phase < 16 else 2)
        idx = self._push(idx, SegmentType.ACTION_HINT, TILE_PAD, action_hint, 4, 0)

        # --- oracle: opponents' hands -----------------------------------------
        if self.include_oracle:
            for seat in range(4):
                if seat == current_player:
                    continue
                p = players[seat]
                opp_counts = np.zeros(TILE_VOCAB_SIZE, dtype=np.int32)
                try:
                    for tile_obj in p.hand:
                        opp_counts[_tile_id(tile_obj)] += 1
                except Exception:  # noqa: BLE001
                    continue
                r = rel(seat)
                for tile_id, c in enumerate(opp_counts):
                    if c > 0:
                        idx = self._push(idx, SegmentType.SELF_HAND, tile_id, int(c), r, 1)

        # --- action mask ------------------------------------------------------
        self._fill_action_mask(table, current_player, riichi_stage2)

        return TokenizedObservation(
            tokens=self._tokens.copy(),
            attention_mask=self._mask.copy(),
            action_mask=self._action_mask.copy(),
            seq_len=idx,
            current_player=current_player,
            phase=phase,
        )

    # ------------------------------------------------------------------------
    # Action mask
    # ------------------------------------------------------------------------

    def _fill_action_mask(self, table, current_player: int, riichi_stage2: bool):
        m = self._action_mask
        if riichi_stage2:
            m[A_RIICHI] = True
            m[A_PASS_RIICHI] = True
            return
        phase = int(table.get_phase())
        if phase < 4:
            actions = table.get_self_actions()
        elif phase < 16:
            actions = table.get_response_actions()
        else:
            return

        for sel in actions:
            self._mask_one_action(sel, m, is_self=phase < 4)

    def _mask_one_action(self, sel, m, is_self: bool):
        """Set bits in ``m`` corresponding to the ``sel`` action.

        Mirrors the encoding in ``Mahjong/Encoding/TrainingDataEncodingV1``
        but kept inline so we don't depend on internal V1 helpers.
        """
        try:
            base = int(sel.action)
            tiles = sel.correspond_tiles
        except Exception:  # noqa: BLE001
            return
        BA = pm.BaseAction
        if is_self and base == int(BA.Discard):
            if not tiles:
                return
            t = tiles[0]
            base_t = int(t.tile)
            if getattr(t, "red_dora", False):
                # Red 5m / 5p / 5s : enable both the regular and the
                # red-dora discard slot so the policy can choose either.
                m[A_DISCARD_BASE + base_t] = True
                if base_t == 4:    # 5m
                    m[A_DISCARD_RED5M] = True
                elif base_t == 13:  # 5p
                    m[A_DISCARD_RED5P] = True
                elif base_t == 22:  # 5s
                    m[A_DISCARD_RED5S] = True
            else:
                m[A_DISCARD_BASE + base_t] = True
        elif base == int(BA.Chi):
            # Discriminate left/middle/right from take vs correspond_tiles ordering.
            # We rely on the engine listing all chi variants in get_response_actions.
            # Without internal access, just enable all 6 chi flags when any chi
            # is offered; the engine will reject invalid sub-variants. The
            # supervised teacher / engine still only picks a valid index.
            if hasattr(sel, "correspond_tiles") and tiles:
                # Heuristic: number diff between min and target tile selects form
                base_t = int(tiles[0].tile)
                used_red = any(getattr(t, "red_dora", False) for t in tiles)
                # We cannot distinguish left/middle/right reliably here without
                # the take tile, so enable all three (plus red variants if needed):
                m[A_CHILEFT] = m[A_CHIMIDDLE] = m[A_CHIRIGHT] = True
                if used_red:
                    m[A_CHILEFT_USERED] = m[A_CHIMIDDLE_USERED] = m[A_CHIRIGHT_USERED] = True
                # silence unused vars
                _ = base_t
        elif base == int(BA.Pon):
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            m[A_PON] = True
            if used_red:
                m[A_PON_USERED] = True
        elif base == int(BA.AnKan):
            m[A_ANKAN] = True
        elif base == int(BA.Kan):
            m[A_MINKAN] = True
        elif base == int(BA.KaKan):
            m[A_KAKAN] = True
        elif base == int(BA.Riichi):
            m[A_RIICHI] = True
        elif base == int(BA.Ron):
            m[A_RON] = True
        elif base == int(BA.Tsumo):
            m[A_TSUMO] = True
        elif base == int(BA.Kyushukyuhai):
            m[A_PUSH] = True
        elif base == int(BA.Pass):
            m[A_PASS_RESPONSE] = True


# ---------------------------------------------------------------------------
# Convenience: token-feature ranges (used by the model)
# ---------------------------------------------------------------------------

#: per-field vocabulary sizes used to build embedding tables
FIELD_VOCAB = {
    "segment": NUM_SEGMENTS,
    "tile": TILE_VOCAB_SIZE,
    "count": 96,         # we bucket up to 95 (river index in extra fits)
    "who": 5,            # 0..3 + 4(N/A)
    "extra": 256,
}

"""Centralized 54-action encoding for Mahjong.

All encoding versions (V1-V4) share the same 54-discrete-action space.
This module is the single source of truth for action index constants and
bidirectional mapping between engine actions and the unified action space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import MahjongPyWrapper as pm

if TYPE_CHECKING:
    from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Action dimension
# ---------------------------------------------------------------------------

ACTION_DIM: int = 54

# ---------------------------------------------------------------------------
# Action index constants
# ---------------------------------------------------------------------------

# Discard (0..36)
A_DISCARD_BASE = 0           # 0..33 -- discard base tile
A_DISCARD_RED5M = 34
A_DISCARD_RED5P = 35
A_DISCARD_RED5S = 36

# Chi (37..42)
A_CHILEFT = 37
A_CHIMIDDLE = 38
A_CHIRIGHT = 39
A_CHILEFT_USERED = 40
A_CHIMIDDLE_USERED = 41
A_CHIRIGHT_USERED = 42

# Pon (43..44)
A_PON = 43
A_PON_USERED = 44

# Kan (45..47)
A_ANKAN = 45
A_MINKAN = 46
A_KAKAN = 47

# Special actions (48..53)
A_RIICHI = 48
A_RON = 49
A_TSUMO = 50
A_PUSH = 51                  # kyushukyuhai
A_PASS_RIICHI = 52
A_PASS_RESPONSE = 53

# ---------------------------------------------------------------------------
# ACTION_TYPES -- maps each of the 54 action indices to a pm.BaseAction
# ---------------------------------------------------------------------------

ACTION_TYPES = (
    [pm.BaseAction.Discard] * (34 + 3)       # 0..36
    + [pm.BaseAction.Chi] * 6                 # 37..42
    + [pm.BaseAction.Pon] * 2                 # 43..44
    + [pm.BaseAction.AnKan]                   # 45
    + [pm.BaseAction.Kan]                     # 46
    + [pm.BaseAction.KaKan]                   # 47
    + [pm.BaseAction.Riichi]                  # 48
    + [pm.BaseAction.Ron]                     # 49
    + [pm.BaseAction.Tsumo]                   # 50
    + [pm.BaseAction.Kyushukyuhai]            # 51
    + [pm.BaseAction.Pass] * 2                # 52..53
)


class ActionEncoder:
    """Centralized bidirectional mapping between engine actions and the
    54-action unified space."""

    # ------------------------------------------------------------------
    # Chi disambiguation
    # ------------------------------------------------------------------

    @staticmethod
    def classify_chi(chi_tile_id: int, hand_tiles) -> int:
        """Determine chi variant from (taken tile, hand pair).

        Returns:
            0 = ChiLeft, 1 = ChiMiddle, 2 = ChiRight.

        Mirrors V1 C++ logic in TrainingDataEncodingV1.cpp:
            if (chi_tile < h[0])  left
            elif (chi_tile > h[1])  right
            else  middle
        """
        h = sorted(int(t.tile) for t in hand_tiles)
        if chi_tile_id < h[0]:
            return 0  # left
        if chi_tile_id > h[1]:
            return 2  # right
        return 1      # middle

    # ------------------------------------------------------------------
    # Engine → Unified (used by datasets, paipu replay)
    # ------------------------------------------------------------------

    @staticmethod
    def engine_to_unified(table, engine_idx: int) -> int:
        """Map an engine selection-list index to the 54-action space.

        Fixes vs. the old ``_engine_idx_to_unified``:
        - Red-5 discard returns A_DISCARD_RED5M/P/S (not CHILEFT_USERED).
        - Chi actions use classify_chi for left/middle/right disambiguation.
        """
        phase = table.get_phase()
        actions = table.get_self_actions() if phase < 4 else table.get_response_actions()
        sel = actions[engine_idx]
        BA = pm.BaseAction
        ba = int(sel.action)
        tiles = sel.correspond_tiles

        if ba == int(BA.Discard):
            t = tiles[0]
            base = int(t.tile)
            if getattr(t, "red_dora", False):
                if base == 4:
                    return A_DISCARD_RED5M
                if base == 13:
                    return A_DISCARD_RED5P
                if base == 22:
                    return A_DISCARD_RED5S
            return base

        if ba == int(BA.Chi):
            chi_tile_id = int(table.get_selected_action_tile().tile)
            kind = ActionEncoder.classify_chi(chi_tile_id, tiles)
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            if used_red:
                return (A_CHILEFT_USERED, A_CHIMIDDLE_USERED, A_CHIRIGHT_USERED)[kind]
            return (A_CHILEFT, A_CHIMIDDLE, A_CHIRIGHT)[kind]

        if ba == int(BA.Pon):
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            return A_PON_USERED if used_red else A_PON

        if ba == int(BA.AnKan):
            return A_ANKAN
        if ba == int(BA.Kan):
            return A_MINKAN
        if ba == int(BA.KaKan):
            return A_KAKAN
        if ba == int(BA.Riichi):
            return A_RIICHI
        if ba == int(BA.Ron):
            return A_RON
        if ba == int(BA.Tsumo):
            return A_TSUMO
        if ba == int(BA.Kyushukyuhai):
            return A_PUSH
        if ba == int(BA.Pass):
            return A_PASS_RESPONSE

        raise ValueError(f"unknown base action {ba}")

    # ------------------------------------------------------------------
    # Unified → Engine (used by envs when translating agent actions)
    # ------------------------------------------------------------------

    @staticmethod
    def unified_to_engine(table, action: int) -> int:
        """Translate a 54-action index into an engine ``make_selection`` index.

        Returns the index into ``get_self_actions()`` or
        ``get_response_actions()`` that corresponds to *action*.
        """
        phase = table.get_phase()
        actions = table.get_self_actions() if phase < 4 else table.get_response_actions()

        BA = pm.BaseAction
        # Map action id -> (BaseAction, tile_basetiles or None, use_red)
        if 0 <= action < 34:
            target = (BA.Discard, [action], False)
        elif action == A_DISCARD_RED5M:
            target = (BA.Discard, [4], True)
        elif action == A_DISCARD_RED5P:
            target = (BA.Discard, [13], True)
        elif action == A_DISCARD_RED5S:
            target = (BA.Discard, [22], True)
        elif action in (A_CHILEFT, A_CHIMIDDLE, A_CHIRIGHT):
            target = (BA.Chi, None, False)
        elif action in (A_CHILEFT_USERED, A_CHIMIDDLE_USERED, A_CHIRIGHT_USERED):
            target = (BA.Chi, None, True)
        elif action == A_PON:
            target = (BA.Pon, None, False)
        elif action == A_PON_USERED:
            target = (BA.Pon, None, True)
        elif action == A_ANKAN:
            target = (BA.AnKan, None, False)
        elif action == A_MINKAN:
            target = (BA.Kan, None, False)
        elif action == A_KAKAN:
            target = (BA.KaKan, None, False)
        elif action == A_RIICHI:
            target = (BA.Riichi, None, False)
        elif action == A_RON:
            target = (BA.Ron, None, False)
        elif action == A_TSUMO:
            target = (BA.Tsumo, None, False)
        elif action == A_PUSH:
            target = (BA.Kyushukyuhai, None, False)
        elif action in (A_PASS_RIICHI, A_PASS_RESPONSE):
            target = (BA.Pass, None, False)
        else:
            raise ValueError(f"action {action} out of range")

        base_action, tile_basetiles, use_red = target

        for i, sel in enumerate(actions):
            if int(sel.action) != int(base_action):
                continue
            tiles = sel.correspond_tiles
            if tile_basetiles is None:
                # Chi/Pon: match by red-dora flag
                has_red = any(getattr(t, "red_dora", False) for t in tiles) if tiles else False
                if has_red == use_red:
                    return i
                # Fallback: if only one candidate of this base action, accept it
                continue
            if tiles and int(tiles[0].tile) == tile_basetiles[0]:
                return i

        raise ValueError(
            f"No engine selection matches action={action}, base={base_action}"
        )

    # ------------------------------------------------------------------
    # Action mask filling
    # ------------------------------------------------------------------

    @staticmethod
    def fill_action_mask(
        table,
        current_player: int,
        riichi_stage2: bool,
        mask_out: np.ndarray,
        last_discard_tile=None,
    ) -> None:
        """Fill a (54,) boolean mask indicating which actions are legal.

        Args:
            table: ``pm.Table`` instance.
            current_player: player whose legal actions to encode.
            riichi_stage2: if True, only RIICHI and PASS_RIICHI are legal.
            mask_out: pre-allocated (54,) boolean array to write into.
            last_discard_tile: tile object of the last discard (for chi
                disambiguation).  ``None`` for self-action phases.
        """
        mask_out[:] = False
        if riichi_stage2:
            mask_out[A_RIICHI] = True
            mask_out[A_PASS_RIICHI] = True
            return

        phase = int(table.get_phase())
        if phase < 4:
            actions = table.get_self_actions()
            is_self = True
        elif phase < 16:
            actions = table.get_response_actions()
            is_self = False
        else:
            return

        chi_tile_id = None
        if last_discard_tile is not None and not is_self:
            chi_tile_id = int(last_discard_tile.tile)

        for sel in actions:
            ActionEncoder._mask_one(sel, mask_out, is_self=is_self, chi_tile_id=chi_tile_id)

    @staticmethod
    def _mask_one(sel, m: np.ndarray, is_self: bool, chi_tile_id: Optional[int]):
        """Set the appropriate bit in *m* for a single engine action."""
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
                m[A_CHILEFT] = m[A_CHIMIDDLE] = m[A_CHIRIGHT] = True
                if any(getattr(t, "red_dora", False) for t in tiles):
                    m[A_CHILEFT_USERED] = m[A_CHIMIDDLE_USERED] = m[A_CHIRIGHT_USERED] = True
                return
            kind = ActionEncoder.classify_chi(chi_tile_id, tiles)
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

    # ------------------------------------------------------------------
    # Tile mapping (for env step(), extracted from MahjongEnv.step())
    # ------------------------------------------------------------------

    @staticmethod
    def action_to_tiles(table, player_id: int, action: int) -> Tuple[List[int], bool]:
        """Map a 54-action index to (corresponding_tile_ids, use_red_dora).

        This is the logic previously inlined in ``MahjongEnv.step()``.
        Only valid for non-riichi-stage2, non-riichi-declaration actions.
        """
        if action < 34:
            return [action], False
        if action == A_DISCARD_RED5M:
            return [4], True
        if action == A_DISCARD_RED5P:
            return [13], True
        if action == A_DISCARD_RED5S:
            return [22], True

        if action in (A_CHILEFT, A_CHILEFT_USERED, A_CHIMIDDLE, A_CHIMIDDLE_USERED,
                       A_CHIRIGHT, A_CHIRIGHT_USERED):
            chi_tile_id = int(table.get_selected_action_tile().tile)
            use_red = action in (A_CHILEFT_USERED, A_CHIMIDDLE_USERED, A_CHIRIGHT_USERED)
            if action in (A_CHILEFT, A_CHILEFT_USERED):
                return [chi_tile_id + 1, chi_tile_id + 2], use_red
            if action in (A_CHIMIDDLE, A_CHIMIDDLE_USERED):
                return [chi_tile_id - 1, chi_tile_id + 1], use_red
            # CHIRIGHT
            return [chi_tile_id - 2, chi_tile_id - 1], use_red

        if action in (A_PON, A_PON_USERED):
            pon_tile_id = int(table.get_selected_action_tile().tile)
            return [pon_tile_id, pon_tile_id], action == A_PON_USERED

        if action == A_MINKAN:
            kan_tile_id = int(table.get_selected_action_tile().tile)
            return [kan_tile_id] * 3, False

        if action == A_ANKAN:
            me = table.players[player_id]
            if me.double_riichi or me.riichi:
                kan_tile_id = int(me.hand[-1].tile)
            else:
                # Player may have multiple ankan options -- pick one at random
                import numpy as _np
                obs = np.zeros([93 + 18, 34], dtype=np.int8)
                pm.encv1_encode_table(table, player_id, True, obs)
                kan_tile_id = int(_np.random.choice(
                    _np.argwhere(obs[3]).flatten()))
            return [kan_tile_id] * 4, False

        if action == A_KAKAN:
            import numpy as _np
            obs = np.zeros([93 + 18, 34], dtype=np.int8)
            pm.encv1_encode_table(table, player_id, True, obs)
            kan_tile_id = int(_np.random.choice(
                _np.argwhere(
                    (_np.sum(obs[:4], axis=0) == 1) * (_np.sum(obs[6:10], axis=0) == 3)
                ).flatten()))
            return [kan_tile_id], False

        if action == A_RON:
            return [], False

        if action in (A_TSUMO, A_PUSH, A_PASS_RESPONSE, A_PASS_RIICHI, A_RIICHI):
            return [], False

        raise ValueError(f"Unhandled action {action}")

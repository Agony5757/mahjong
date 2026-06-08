#!/usr/bin/env python3
"""mjai-protocol bot wrapping a V5 (Douzero-head) checkpoint.

This script is the *runtime* for the V5 mjai bot. Package it into a
``bot.zip`` alongside the model checkpoint and a pre-built MahjongPyWrapper
wheel to submit to ``mjai.Simulator``.

Architecture
------------
mjai is event-stream JSON over stdin/stdout. The bot:

1. Parses each incoming event batch.
2. Maintains its own minimal game state in pure Python plus a libriichi
   ``mjai.mlibriichi.state.PlayerState`` shadow — the latter is the
   engine-authoritative source of legal actions and is fed every event
   verbatim via ``ps.update(event_json)``. The action mask is built from
   ``ps.last_cans`` (``ActionCandidate``), which matches exactly what
   the mjai simulator will accept.
3. Drives a ``pm.encv4_HandEncoder`` directly via its ``on_*`` hooks so
   the per-player V4 token stream matches what the model was trained on
   (model input is encv4; legality is libriichi).
4. On a decision event, computes the 54-dim action mask from libriichi
   ``last_cans``, runs the V5 model, picks the best legal action, and
   emits the corresponding mjai action message. Every non-trivial
   emitted JSON is run through ``ps.validate_reaction`` as a final
   safety net; if it raises, the bot falls back to ``{"type":"none"}``
   or tsumogiri instead of chombo'ing.

Earlier versions of this bot hand-coded the legal-action mask which
diverged from libriichi in several edge cases (no-yaku ron, riichi +
ankan wait-preservation, kan-dora limit, chi/pon timing after another
call). Those bug classes are now closed because the mask comes from the
same engine the mjai simulator uses.

Usage (inside docker container):
    python bot.py <player_id>
where ``<player_id>`` is 0..3.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

import MahjongPyWrapper as pm  # type: ignore
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.douzero import DouzeroTransformer
from pymahjong.rl.action_features import ACTION_FEAT_DIM

try:
    import mjai.mlibriichi as _mlr  # type: ignore
    _PLAYER_STATE_CLS = _mlr.state.PlayerState
except Exception as _e:  # noqa: BLE001
    _PLAYER_STATE_CLS = None
    _MLR_IMPORT_ERR = _e
else:
    _MLR_IMPORT_ERR = None


# ---------------------------------------------------------------------------
# Tile encoding helpers — mjai uses string tiles, V4 encoder uses BaseTile.
# ---------------------------------------------------------------------------

# mjai tile string → (BaseTile_index 0..33, is_aka)
MJAI_TILE_INFO: Dict[str, Tuple[int, bool]] = {
    **{f"{n}m": (n - 1, False) for n in range(1, 10)},
    **{f"{n}p": (n - 1 + 9, False) for n in range(1, 10)},
    **{f"{n}s": (n - 1 + 18, False) for n in range(1, 10)},
    "E": (27, False), "S": (28, False), "W": (29, False), "N": (30, False),
    "P": (31, False), "F": (32, False), "C": (33, False),
    # red 5s — libriichi uses "5mr"/"5pr"/"5sr"; mjai.app docs use "0m"/"0p"/"0s"
    "5mr": (4, True),
    "5pr": (13, True),
    "5sr": (22, True),
    "0m": (4, True),
    "0p": (13, True),
    "0s": (22, True),
}

# Reverse: (BaseTile_index, is_aka) → mjai string
def basetile_to_mjai(basetile_idx: int, aka: bool = False) -> str:
    if aka:
        if basetile_idx == 4:
            return "5mr"
        if basetile_idx == 13:
            return "5pr"
        if basetile_idx == 22:
            return "5sr"
    if basetile_idx < 9:
        return f"{basetile_idx + 1}m"
    if basetile_idx < 18:
        return f"{basetile_idx - 9 + 1}p"
    if basetile_idx < 27:
        return f"{basetile_idx - 18 + 1}s"
    return ["E", "S", "W", "N", "P", "F", "C"][basetile_idx - 27]


def basetile_enum(idx: int) -> Any:
    """Get pm.BaseTile enum value from 0..33 integer."""
    return pm.BaseTile(idx)


BAKAZE_MAP = {"E": 0, "S": 1, "W": 2, "N": 3}


# ---------------------------------------------------------------------------
# Unified 54-action constants (must match pymahjong/rl/action_space.py)
# ---------------------------------------------------------------------------

ACTION_DIM = 54
A_DISCARD_BASE = 0           # 0..33 — discard base tile
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
# Mjai bot
# ---------------------------------------------------------------------------


class V5MjaiBot:
    """V5 model → mjai protocol adapter."""

    # ------------------------------------------------------------------ init

    def __init__(
        self,
        player_id: int,
        model_path: Path,
        device: str = "cpu",
        d_model: int = 384,
        n_heads: int = 8,
        n_layers: int = 6,
        ff_mult: int = 4,
        scorer_hidden: int = 256,
    ):
        assert 0 <= player_id < 4
        self.player_id = player_id
        self.device = torch.device(device)

        cfg = TransformerConfig(
            d_model=d_model, n_heads=n_heads, n_layers=n_layers, ff_mult=ff_mult,
        )
        self.model = DouzeroTransformer(event_dim=100, action_feat_dim=ACTION_FEAT_DIM, 
            config=cfg, scorer_hidden=scorer_hidden,
        ).to(self.device).eval()
        ck = torch.load(str(model_path), map_location=self.device, weights_only=False)
        state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
        self.model.load_state_dict(state)

        # Shadow PlayerState from libriichi — engine-authoritative legality.
        if _PLAYER_STATE_CLS is None:
            raise RuntimeError(
                f"mjai.mlibriichi not available; cannot run V5MjaiBot: {_MLR_IMPORT_ERR}"
            )
        self.ps = _PLAYER_STATE_CLS(player_id)
        # Latest ActionCandidate from ps.update; refreshed every event.
        self._last_cans: Optional[Any] = None

        # Per-kyoku state (reset on start_kyoku)
        self._reset_kyoku_state()

    def _reset_kyoku_state(self) -> None:
        self.encoder: Optional[Any] = None        # pm.encv4_HandEncoder
        self.table: Optional[Any] = None          # pm.Table (init-only)
        self.bakaze: str = "E"
        self.kyoku: int = 1
        self.honba: int = 0
        self.kyotaku: int = 0
        self.oya: int = 0
        self.scores: List[int] = [25000] * 4
        self.dora_indicators: List[str] = []
        # my hand (mjai strings, e.g. "1m", "5pr")
        self.my_tehai: List[str] = []
        # tiles I've discarded (for furiten)
        self.my_river: List[str] = []
        # all 4 players' discards (for opponent tracking & display)
        self.rivers: List[List[str]] = [[] for _ in range(4)]
        # my open melds
        self.my_melds: List[Dict[str, Any]] = []
        # melds for all 4 players (visible)
        self.melds: List[List[Dict[str, Any]]] = [[] for _ in range(4)]
        # riichi status per player
        self.riichi: List[bool] = [False] * 4
        # last tile drawn for me (for tsumogiri detection)
        self.last_self_tsumo: Optional[str] = None
        # tile just discarded by an opponent (relevant for response phase)
        self.last_opp_dahai: Optional[Dict[str, Any]] = None
        # remaining tiles in wall (for ryukyoku check)
        self.tiles_left: int = 70

    # -------------------------------------------------------- main entry point

    def react(self, line: str) -> Optional[str]:
        """Process one mjai event batch, optionally returning a response."""
        events = json.loads(line)
        if not isinstance(events, list):
            events = [events]

        for ev in events:
            self._process_event(ev)

        # Decide on action based on last event
        last = events[-1] if events else None
        if last is None:
            return None
        action_msg = self._maybe_act(last)
        return action_msg

    # ----------------------------------------------------------- event handler

    def _process_event(self, ev: Dict[str, Any]) -> None:
        # Feed every event to the libriichi PlayerState shadow — this is
        # what powers the engine-authoritative action mask in
        # _compute_*_mask. Schema violations are logged and skipped (we
        # keep whatever last_cans we had before).
        try:
            self._last_cans = self.ps.update(json.dumps(ev))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(
                f"V5 ps.update failed on {ev.get('type')!r}: {e}\n"
            )

        t = ev.get("type")
        if t == "start_game":
            # No per-game state needed; per-kyoku state is reset in start_kyoku
            return
        if t == "start_kyoku":
            self._on_start_kyoku(ev)
            return
        if t == "end_kyoku" or t == "end_game":
            self.encoder = None
            return
        if self.encoder is None:
            return  # safety: ignore mid-events before kyoku init

        if t == "tsumo":
            self._on_tsumo(ev)
        elif t == "dahai":
            self._on_dahai(ev)
        elif t == "chi":
            self._on_chi(ev)
        elif t == "pon":
            self._on_pon(ev)
        elif t == "daiminkan" or t == "kan":
            # mjai "kan" with consumed=4 tiles is minkan / ankan; need to distinguish
            self._on_kan(ev)
        elif t == "ankan":
            self._on_ankan(ev)
        elif t == "kakan":
            self._on_kakan(ev)
        elif t == "reach":
            self._on_reach(ev)
        elif t == "reach_accepted":
            self._on_reach_accepted(ev)
        elif t == "dora":
            self._on_dora(ev)
        elif t == "hora":
            self._on_hora(ev)
        elif t == "ryukyoku":
            self.encoder.on_ryuukyoku()

    # --------------------------------------------------------- start_kyoku init

    def _on_start_kyoku(self, ev: Dict[str, Any]) -> None:
        self._reset_kyoku_state()
        self.bakaze = ev["bakaze"]
        self.kyoku = ev["kyoku"]
        self.honba = ev["honba"]
        self.kyotaku = ev["kyotaku"]
        self.oya = ev["oya"]
        self.scores = list(ev["scores"])
        self.dora_indicators = [ev["dora_marker"]]
        # Our tehai is in ev["tehais"][player_id]; opponents are masked as "?"
        my_tehai = ev["tehais"][self.player_id]
        assert "?" not in my_tehai, "my own tehai should be revealed"
        self.my_tehai = list(my_tehai)
        # Dealer gets 14 tiles (last one is initial tsumo)
        if len(my_tehai) == 14:
            self.last_self_tsumo = my_tehai[-1]

        # Build a yama where our seat's deal positions get the REAL tiles
        # from mjai (and the dora indicator position gets the real dora
        # marker). Without this fix, the encoder's INIT_HAND events would
        # reflect the naive yama (1m-1m-1m-1m-...) and the model would
        # receive garbage initial hands — see commit history for details.
        yama = self._build_initial_yama(my_tehai, ev["dora_marker"])

        self.table = pm.Table()
        self.table.game_init_with_config(
            yama,
            self.scores,
            self.kyotaku,
            self.honba,
            BAKAZE_MAP[self.bakaze],
            self.oya,
        )
        self.encoder = pm.encv4_HandEncoder(self.table)
        self.encoder.encode_init()

    def _build_initial_yama(self, my_tehai: List[str], dora_marker: str) -> List[int]:
        """Construct a 136-int yama so that ``pm.Table.game_init_with_config``
        deals ``my_tehai`` to our seat AND places ``dora_marker`` at the
        dora-indicator position.

        Tenhou-style wall layout per :func:`Mahjong/Table.cpp:Table::draw_tenhou_style`:
        the wall is popped from the back (yama.back()) and dealt 4-4-4-1 in
        rounds starting from oya. Concretely with ``yama = list(range(136))``
        and ``oya=0``, ``players[0]`` gets yama positions ``{135..132,
        119..116, 103..100, 87}`` for its 13 init tiles, then ``yama[83]``
        as its first tsumo (if oya). The dora indicator is read from
        ``yama[5]`` (the dead wall is at the front of the yama).

        Tile id ↔ basetile mapping (4 ids per basetile, contiguous):
        bt=0  → ids 0..3 (1m), bt=4 → ids 16..19 (5m incl aka at id 16),
        bt=13 → ids 52..55 (5p, aka=52), bt=22 → ids 88..91 (5s, aka=88),
        bt=33 → ids 132..135 (中).

        We pick a UNIQUE tile id for every requested mjai tile string, then
        atomically place all (position, tile_id) constraints into the yama,
        filling the remaining slots with the leftover ids in ascending
        order.
        """
        AKA_ID = {4: 16, 13: 52, 22: 88}

        def mjai_to_id_picker():
            used: set = set()
            def pick(mjai_tile: str) -> int:
                bt, aka = MJAI_TILE_INFO[mjai_tile]
                if aka:
                    tid = AKA_ID[bt]
                    if tid in used:
                        raise ValueError(f"duplicate aka tile id for {mjai_tile}")
                    used.add(tid)
                    return tid
                cands = [i for i in range(bt * 4, bt * 4 + 4)]
                if bt in AKA_ID:
                    cands = [c for c in cands if c != AKA_ID[bt]]
                for c in cands:
                    if c not in used:
                        used.add(c)
                        return c
                raise ValueError(f"no tile id available for {mjai_tile}")
            return pick

        pick_id = mjai_to_id_picker()

        # Compute our seat's deal positions (popping from back of yama).
        positions: List[int] = []
        cursor = 135
        for _round in range(3):
            for i in range(4):
                player = (self.oya + i) % 4
                for _ in range(4):
                    if player == self.player_id:
                        positions.append(cursor)
                    cursor -= 1
        # 'tiao zhang' final 1-tile per player
        for i in range(4):
            player = (self.oya + i) % 4
            if player == self.player_id:
                positions.append(cursor)
            cursor -= 1
        # If we're oya and mjai gave us 14 tiles, the 14th is the first tsumo
        # which pm.Table will deal from yama[cursor] (next pop).
        n_init = 13
        if len(my_tehai) == 14:
            positions.append(cursor)
            n_init = 14
        assert len(positions) == n_init, (
            f"yama-position calc mismatch: got {len(positions)} expected {n_init}"
        )

        # Build the placement constraints.
        placements: Dict[int, int] = {}
        for pos, mjai_tile in zip(positions, my_tehai[:n_init]):
            placements[pos] = pick_id(mjai_tile)
        # Dora indicator: pm.Table reads it from yama[5] (after dealing).
        placements[5] = pick_id(dora_marker)

        # Compose yama: place desired ids, fill remaining slots with leftover
        # ids in ascending order.
        used_ids = set(placements.values())
        leftover = (tid for tid in range(136) if tid not in used_ids)
        yama: List[int] = [0] * 136
        for pos in range(136):
            if pos in placements:
                yama[pos] = placements[pos]
            else:
                yama[pos] = next(leftover)
        return yama

    # --------------------------------------------------------- visible events

    def _on_tsumo(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        pai = ev["pai"]
        if actor == self.player_id:
            assert pai != "?"
            self.my_tehai.append(pai)
            self.last_self_tsumo = pai
        else:
            # opponent draw: pai is "?", we don't know the tile
            pai = "?"
        # Encode draw (use dummy for opponents — track(opponent) is unused)
        if pai != "?":
            bt, aka = MJAI_TILE_INFO[pai]
            self.encoder.on_draw(actor, basetile_enum(bt), aka)
        else:
            # Encode a placeholder so opponent's track stays length-consistent
            self.encoder.on_draw(actor, basetile_enum(0), False)
        self.tiles_left -= 1

    def _on_dahai(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        pai = ev["pai"]
        tsumogiri = ev.get("tsumogiri", False)
        bt, aka = MJAI_TILE_INFO[pai]
        # 0x02 flag = from-hand (not tsumogiri) — matches LogAction.DiscardFromHand
        flags = 0 if tsumogiri else 0x02
        self.encoder.on_discard(actor, basetile_enum(bt), aka, flags)
        self.rivers[actor].append(pai)
        if actor == self.player_id:
            try:
                self.my_tehai.remove(pai)
            except ValueError:
                pass
            self.my_river.append(pai)
            self.last_self_tsumo = None
        else:
            self.last_opp_dahai = ev

    def _on_chi(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        target = ev["target"]
        consumed = ev["consumed"]  # 2 tiles
        called_tile = ev["pai"]
        all_tiles = sorted(consumed + [called_tile], key=lambda t: MJAI_TILE_INFO[t][0])
        lowest_bt = MJAI_TILE_INFO[all_tiles[0]][0]
        called_bt = MJAI_TILE_INFO[called_tile][0]
        chi_type = called_bt - lowest_bt  # 0 (chi-left), 1 (middle), 2 (right)
        aka_bits = sum(1 for t in consumed if MJAI_TILE_INFO[t][1])
        self.encoder.on_chi(actor, basetile_enum(lowest_bt), chi_type, target, aka_bits)
        # Update melds + hand
        meld = {"type": "chi", "consumed": consumed, "called": called_tile, "from": target}
        self.melds[actor].append(meld)
        if actor == self.player_id:
            for t in consumed:
                self.my_tehai.remove(t)
            self.my_melds.append(meld)

    def _on_pon(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        target = ev["target"]
        consumed = ev["consumed"]
        called_tile = ev["pai"]
        bt, aka = MJAI_TILE_INFO[called_tile]
        self.encoder.on_pon(actor, basetile_enum(bt), target, aka)
        meld = {"type": "pon", "consumed": consumed, "called": called_tile, "from": target}
        self.melds[actor].append(meld)
        if actor == self.player_id:
            for t in consumed:
                self.my_tehai.remove(t)
            self.my_melds.append(meld)

    def _on_kan(self, ev: Dict[str, Any]) -> None:
        # daiminkan (called)
        actor = ev["actor"]
        target = ev.get("target", actor)
        called_tile = ev["pai"]
        consumed = ev.get("consumed", [])
        bt, aka = MJAI_TILE_INFO[called_tile]
        self.encoder.on_daiminkan(actor, basetile_enum(bt), target, aka)
        meld = {"type": "minkan", "consumed": consumed, "called": called_tile, "from": target}
        self.melds[actor].append(meld)
        if actor == self.player_id:
            for t in consumed:
                self.my_tehai.remove(t)
            self.my_melds.append(meld)

    def _on_ankan(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        consumed = ev["consumed"]  # 4 tiles of same kind
        bt, _ = MJAI_TILE_INFO[consumed[0]]
        self.encoder.on_ankan(actor, basetile_enum(bt))
        meld = {"type": "ankan", "consumed": consumed}
        self.melds[actor].append(meld)
        if actor == self.player_id:
            for t in consumed:
                self.my_tehai.remove(t)
            self.my_melds.append(meld)

    def _on_kakan(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        pai = ev["pai"]
        bt, aka = MJAI_TILE_INFO[pai]
        self.encoder.on_kakan(actor, basetile_enum(bt), aka)
        # upgrade existing pon meld
        if actor == self.player_id:
            try:
                self.my_tehai.remove(pai)
            except ValueError:
                pass

    def _on_reach(self, ev: Dict[str, Any]) -> None:
        # reach announce is paired with a dahai event
        pass  # actual tile + riichi flag is in the subsequent dahai

    def _on_reach_accepted(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        self.riichi[actor] = True
        self.encoder.on_riichi_success(actor)

    def _on_dora(self, ev: Dict[str, Any]) -> None:
        marker = ev["dora_marker"]
        bt, aka = MJAI_TILE_INFO[marker]
        self.encoder.on_dora_reveal(basetile_enum(bt), aka)
        self.dora_indicators.append(marker)

    def _on_hora(self, ev: Dict[str, Any]) -> None:
        actor = ev["actor"]
        target = ev["target"]
        if actor == target:
            self.encoder.on_tsumo(actor)
        else:
            self.encoder.on_ron(actor, target)

    # ---------------------------------------------------------- decision logic

    def _maybe_act(self, last_ev: Dict[str, Any]) -> Optional[str]:
        """Decide if we should react to last_ev, and emit mjai action.

        Dispatch is driven by libriichi's ``ActionCandidate`` (``self._last_cans``)
        which is the engine-authoritative signal: if ``can_act`` is False,
        we don't act this turn. Otherwise we either:

        * pick a self-action (discard / riichi / tsumo / ankan / kakan / push)
          when ``can_discard`` (and friends) is set; OR
        * pick a response (pass / pon / chi / kan / ron) when
          ``can_chi/can_pon/can_daiminkan/can_ron_agari/can_pass`` is set.

        We also handle the riichi 2-step protocol (reach echo → dahai).
        """
        t = last_ev.get("type")
        ac = self._last_cans

        # === Reach 2-step: server echoed our own reach, now emit dahai
        if t == "reach" and last_ev.get("actor") == self.player_id and getattr(self, "_pending_riichi", False):
            self._pending_riichi = False
            candidates = getattr(self, "_pending_riichi_candidates", None) or []
            if not candidates:
                ok, candidates = self._can_riichi()
                if not ok:
                    candidates = []
            if not candidates:
                # Last-ditch: try every tile in hand and let validate_reaction
                # pick the first one libriichi accepts. Beats chombo.
                for tile in list(set(self.my_tehai)):
                    candidate_msg = self._make_dahai_msg(tile)
                    try:
                        self.ps.validate_reaction(candidate_msg)
                        return candidate_msg
                    except Exception:
                        continue
                if self.last_self_tsumo is not None:
                    return self._make_dahai_msg(self.last_self_tsumo, tsumogiri=True)
                return None
            mask = np.zeros(ACTION_DIM, dtype=bool)
            for bt in candidates:
                mask[A_DISCARD_BASE + bt] = True
                if bt == 4 and "5mr" in self.my_tehai:
                    mask[A_DISCARD_RED5M] = True
                elif bt == 13 and "5pr" in self.my_tehai:
                    mask[A_DISCARD_RED5P] = True
                elif bt == 22 and "5sr" in self.my_tehai:
                    mask[A_DISCARD_RED5S] = True
            action = self._run_model(mask)
            return self._guarded_emit(self._action_to_mjai_self(action))

        # === Below this point, libriichi's ActionCandidate drives dispatch.
        if ac is None or not getattr(ac, "can_act", False):
            return None

        # Self-action phase: ours to draw/discard/riichi/tsumo/(an)kan/push.
        # This covers: after our own tsumo, after our own chi/pon (forced
        # discard), after our own ankan/daiminkan/kakan rinshan tsumo.
        if (ac.can_discard or ac.can_tsumo_agari or ac.can_riichi
                or ac.can_ankan or ac.can_kakan or ac.can_ryukyoku):
            return self._self_action()

        # Response phase: another player's dahai / kakan (chankan).
        if (ac.can_chi or ac.can_pon or ac.can_daiminkan or ac.can_ron_agari):
            if t == "kakan":
                return self._response_to_kakan(last_ev)
            return self._response_to_dahai(last_ev)

        # can_pass without any call → just pass
        if ac.can_pass:
            return '{"type":"none"}'

        return None

    def _self_action(self) -> str:
        """Pick action after our own tsumo (discard / riichi / tsumo / ankan / kakan / push)."""
        mask = self._compute_self_action_mask()
        action = self._run_model(mask)
        msg = self._action_to_mjai_self(action)
        return self._guarded_emit(msg)

    def _response_to_dahai(self, last_ev: Dict[str, Any]) -> str:
        """Pick response to opponent's dahai (pass / pon / chi / kan / ron).

        Mask comes from libriichi ``ActionCandidate`` (see
        :meth:`_compute_response_mask`); every emitted action JSON is
        validated through ``ps.validate_reaction`` before sending.
        """
        mask = self._compute_response_mask(last_ev)
        if not mask.any() or (mask.sum() == 1 and mask[A_PASS_RESPONSE]):
            return '{"type":"none"}'
        action = self._run_model(mask)
        msg = self._action_to_mjai_response(action, last_ev)
        return self._guarded_emit(msg)

    def _response_to_kakan(self, last_ev: Dict[str, Any]) -> str:
        """Chankan check — libriichi sets ``can_ron_agari`` on its
        ``last_cans`` if a chankan ron is legal (yakus included)."""
        ac = self._last_cans
        if ac is not None and ac.can_ron_agari:
            actor = last_ev["actor"]
            tile = last_ev.get("pai") or (last_ev.get("consumed", [None])[0])
            if tile is None:
                return '{"type":"none"}'
            msg = json.dumps({
                "type": "hora",
                "actor": self.player_id,
                "target": actor,
                "pai": tile,
            })
            return self._guarded_emit(msg)
        return '{"type":"none"}'

    # ---------------------------------------------------- action-mask building

    def _tehai_counts(self) -> List[int]:
        """Return 34-len list of tile counts in my tehai (red 5s collapsed to normal 5)."""
        counts = [0] * 34
        for t in self.my_tehai:
            bt, _ = MJAI_TILE_INFO[t]
            counts[bt] += 1
        return counts

    def _tehai_to_compact(self, counts: Optional[List[int]] = None) -> str:
        """Convert 34-len counts to compact hand string like '1234567m...'."""
        if counts is None:
            counts = self._tehai_counts()
        out = []
        for suit_off, suit_char in [(0, "m"), (9, "p"), (18, "s")]:
            chars = []
            for i in range(9):
                chars.extend(str(i + 1) * counts[suit_off + i])
            if chars:
                out.append("".join(chars) + suit_char)
        # honors → 1z..7z
        honor_chars = []
        for i in range(7):
            honor_chars.extend(str(i + 1) * counts[27 + i])
        if honor_chars:
            out.append("".join(honor_chars) + "z")
        return "".join(out)

    def _is_furiten_for(self, tile_bt: int) -> bool:
        """Check if winning on tile_bt would be furiten (already in our river)."""
        for t in self.my_river:
            bt, _ = MJAI_TILE_INFO[t]
            if bt == tile_bt:
                return True
        return False

    def _can_tsumo(self) -> bool:
        """Check if our current 14-tile hand is a winning hand."""
        if self.last_self_tsumo is None:
            return False
        if len(self.my_tehai) % 3 != 2:
            return False
        # Use C++ helper
        try:
            return bool(pm.is_ordinary_agari(self._tehai_to_compact()))
        except Exception:
            return False

    def _can_ron(self, opp_tile: str) -> bool:
        """Check if ron-ing on opp_tile gives us a winning hand (and not furiten)."""
        if len(self.my_tehai) % 3 != 1:
            return False
        bt, _ = MJAI_TILE_INFO[opp_tile]
        if self._is_furiten_for(bt):
            return False
        counts = self._tehai_counts()
        counts[bt] += 1
        try:
            return bool(pm.is_ordinary_agari(self._tehai_to_compact(counts)))
        except Exception:
            return False

    def _can_riichi(self) -> Tuple[bool, List[int]]:
        """Check riichi legality + return list of basetile candidates we can discard
        and still be tenpai. Returns (any_legal, [basetile_index, ...])."""
        if self.riichi[self.player_id]:
            return False, []
        # Menzen check: no called melds
        if any(m["type"] in ("chi", "pon", "minkan", "kakan") for m in self.my_melds):
            return False, []
        if self.scores[self.player_id] < 1000:
            return False, []
        if self.tiles_left < 4:
            return False, []
        if len(self.my_tehai) % 3 != 2:
            return False, []
        # For each tile in tehai, discard it and check tenpai
        counts = self._tehai_counts()
        candidates = []
        seen = set()
        for bt in range(34):
            if counts[bt] == 0:
                continue
            if bt in seen:
                continue
            seen.add(bt)
            counts[bt] -= 1
            try:
                shanten = pm.normal_round_to_win(self._tehai_to_compact(counts), 0)
                if shanten <= 1:  # 0=agari, 1=tenpai
                    candidates.append(bt)
            except Exception:
                pass
            counts[bt] += 1
        return (len(candidates) > 0), candidates

    def _can_pon(self, opp_tile: str) -> bool:
        bt, _ = MJAI_TILE_INFO[opp_tile]
        return self._tehai_counts()[bt] >= 2

    def _can_minkan(self, opp_tile: str) -> bool:
        bt, _ = MJAI_TILE_INFO[opp_tile]
        return self._tehai_counts()[bt] >= 3

    def _can_ankan(self) -> List[int]:
        """Return list of basetile indices we can ankan."""
        counts = self._tehai_counts()
        return [bt for bt in range(34) if counts[bt] >= 4]

    def _can_kakan(self) -> List[int]:
        """Return list of basetile indices we can kakan (have pon meld + 1 in hand)."""
        result = []
        for meld in self.my_melds:
            if meld["type"] == "pon":
                bt, _ = MJAI_TILE_INFO[meld["called"]]
                if self._tehai_counts()[bt] >= 1:
                    result.append(bt)
        return result

    def _can_chi_patterns(self, opp_tile: str, from_actor: int) -> List[Tuple[int, int]]:
        """Return list of (chi_type, lowest_basetile) we can chi on opp_tile.

        Convention (matches ``pymahjong.rl.action_space.classify_chi``):

        * ``chi_type=0`` (A_CHILEFT)  = called tile is the LOWEST  in the run
        * ``chi_type=1`` (A_CHIMIDDLE) = called tile is the MIDDLE in the run
        * ``chi_type=2`` (A_CHIRIGHT) = called tile is the HIGHEST in the run

        Only legal from kamicha. Note: superseded by libriichi
        ``ActionCandidate.can_chi_low/mid/high`` for the actual mask;
        kept here for callers that need a hand-only check.
        """
        # Only kamicha → us (i.e., from_actor + 1 mod 4 == player_id)
        if (from_actor + 1) % 4 != self.player_id:
            return []
        bt, _ = MJAI_TILE_INFO[opp_tile]
        if bt >= 27:  # honors can't chi
            return []
        suit_off = (bt // 9) * 9
        idx_in_suit = bt - suit_off
        counts = self._tehai_counts()
        out: List[Tuple[int, int]] = []
        # chi_type=0 (called LOW): hand has +1, +2 -> run lowest = called bt
        if idx_in_suit <= 6 and counts[bt + 1] > 0 and counts[bt + 2] > 0:
            out.append((0, bt))
        # chi_type=1 (called MID): hand has -1, +1 -> run lowest = bt-1
        if 1 <= idx_in_suit <= 7 and counts[bt - 1] > 0 and counts[bt + 1] > 0:
            out.append((1, bt - 1))
        # chi_type=2 (called HIGH): hand has -2, -1 -> run lowest = bt-2
        if idx_in_suit >= 2 and counts[bt - 2] > 0 and counts[bt - 1] > 0:
            out.append((2, bt - 2))
        return out

    def _compute_self_action_mask(self) -> np.ndarray:
        """Return 54-dim bool mask of legal actions in our self-action phase.

        Uses libriichi's ``ActionCandidate`` (``self._last_cans``) as the
        authoritative source. Falls back to a tsumogiri-only mask if the
        shadow state has no candidates (defensive — should not happen
        once start_kyoku has fired).
        """
        mask = np.zeros(ACTION_DIM, dtype=bool)
        ac = self._last_cans
        if ac is None or not getattr(ac, "can_act", False):
            # Defensive fallback: emit a tsumogiri-safe mask
            if self.last_self_tsumo is not None:
                bt, aka = MJAI_TILE_INFO[self.last_self_tsumo]
                if aka:
                    {4: A_DISCARD_RED5M, 13: A_DISCARD_RED5P, 22: A_DISCARD_RED5S}.get(bt)
                    aka_action = {4: A_DISCARD_RED5M, 13: A_DISCARD_RED5P, 22: A_DISCARD_RED5S}.get(bt)
                    if aka_action is not None:
                        mask[aka_action] = True
                        return mask
                mask[A_DISCARD_BASE + bt] = True
            return mask

        # === Discard
        if ac.can_discard:
            tehai = self.ps.tehai            # 34-len count vector
            akas = self.ps.akas_in_hand      # [bool, bool, bool] for 5m/5p/5s
            forbidden = self.ps.forbidden_tiles  # kuikae / post-call constraints
            # Number of non-aka 5s per suit:
            #   tehai[4]  = total 5m count (including aka), so non-aka = total - akas[0]
            for bt in range(34):
                if tehai[bt] <= 0:
                    continue
                if forbidden[bt]:
                    continue
                # If bt is a 5-tile and the only copy in hand is the aka,
                # don't enable the NORMAL discard.
                if bt == 4 and akas[0] and tehai[bt] == 1:
                    continue
                if bt == 13 and akas[1] and tehai[bt] == 1:
                    continue
                if bt == 22 and akas[2] and tehai[bt] == 1:
                    continue
                mask[A_DISCARD_BASE + bt] = True
            # Aka discards: enabled iff aka present AND that tile is not forbidden
            if akas[0] and not forbidden[4]:
                mask[A_DISCARD_RED5M] = True
            if akas[1] and not forbidden[13]:
                mask[A_DISCARD_RED5P] = True
            if akas[2] and not forbidden[22]:
                mask[A_DISCARD_RED5S] = True

        # === Tsumo
        if ac.can_tsumo_agari:
            mask[A_TSUMO] = True

        # === Riichi (also requires tenpai-preserving discard — checked at
        # the dahai step). We additionally guard: must have at least one
        # candidate discard, otherwise the bot would emit reach then be
        # forced into a chombo dahai. _can_riichi computes candidates.
        if ac.can_riichi:
            ok, _ = self._can_riichi()
            if ok:
                mask[A_RIICHI] = True

        # === Ankan (libriichi guards riichi+ankan wait-preservation,
        # kan-dora limit, 4-kan abortive, last-wall-tile, etc.)
        if ac.can_ankan:
            mask[A_ANKAN] = True

        # === Kakan
        if ac.can_kakan:
            mask[A_KAKAN] = True

        # === Kyushukyuhai
        if ac.can_ryukyoku:
            mask[A_PUSH] = True

        return mask

    def _compute_response_mask(self, last_dahai: Dict[str, Any]) -> np.ndarray:
        """Return 54-dim mask for responses to opponent's dahai.

        Uses libriichi's ``ActionCandidate`` (``self._last_cans``).

        Chi convention (matches ``pymahjong.rl.action_space.classify_chi``):

        * ``A_CHILEFT``  = called tile is the LOWEST  in the run (libriichi ``can_chi_low``)
        * ``A_CHIMIDDLE`` = called tile is the MIDDLE in the run (libriichi ``can_chi_mid``)
        * ``A_CHIRIGHT`` = called tile is the HIGHEST in the run (libriichi ``can_chi_high``)
        """
        mask = np.zeros(ACTION_DIM, dtype=bool)
        ac = self._last_cans
        # Pass is always present as a baseline; libriichi may also set can_pass
        mask[A_PASS_RESPONSE] = True
        if ac is None:
            return mask

        # === Ron
        if ac.can_ron_agari:
            mask[A_RON] = True

        # === Pon (+ aka variant if we have an aka 5 in hand for 5m/5p/5s)
        if ac.can_pon:
            mask[A_PON] = True
            opp_tile = last_dahai["pai"]
            bt, _ = MJAI_TILE_INFO[opp_tile]
            if bt in (4, 13, 22):
                aka_idx = {4: 0, 13: 1, 22: 2}[bt]
                if self.ps.akas_in_hand[aka_idx]:
                    # Sanity: we need 2 tiles of bt; if we only have 1 normal + 1 aka,
                    # then the only viable pon uses the aka, so A_PON_USERED is the
                    # only legal pon. If we have >=2 normals, both A_PON and
                    # A_PON_USERED are legal.
                    mask[A_PON_USERED] = True

        # === Minkan (daiminkan)
        if ac.can_daiminkan:
            mask[A_MINKAN] = True

        # === Chi (only legal from kamicha; libriichi enforces this)
        if ac.can_chi_low:
            mask[A_CHILEFT] = True
        if ac.can_chi_mid:
            mask[A_CHIMIDDLE] = True
        if ac.can_chi_high:
            mask[A_CHIRIGHT] = True
        # Chi-with-red variants: if the chi run includes a 5-tile that we
        # have as aka, enable the *USERED variant. classify_chi maps:
        #   CHILEFT  (called low)  -> consumed = [bt+1, bt+2]
        #   CHIMIDDLE              -> consumed = [bt-1, bt+1]
        #   CHIRIGHT (called high) -> consumed = [bt-2, bt-1]
        if any([ac.can_chi_low, ac.can_chi_mid, ac.can_chi_high]):
            opp_tile = last_dahai["pai"]
            bt, _ = MJAI_TILE_INFO[opp_tile]
            tehai_counts = self.ps.tehai
            akas = self.ps.akas_in_hand
            for is_legal, chi_variant, consumed_offsets in (
                (ac.can_chi_low,  A_CHILEFT_USERED,   (bt + 1, bt + 2)),
                (ac.can_chi_mid,  A_CHIMIDDLE_USERED, (bt - 1, bt + 1)),
                (ac.can_chi_high, A_CHIRIGHT_USERED,  (bt - 2, bt - 1)),
            ):
                if not is_legal:
                    continue
                # Check if either consumed slot is a 5 we have aka of, AND
                # actually have a second tile of that 5-type to consume.
                aka_in_run = False
                for off in consumed_offsets:
                    if off == 4 and akas[0]:
                        aka_in_run = True
                    elif off == 13 and akas[1]:
                        aka_in_run = True
                    elif off == 22 and akas[2]:
                        aka_in_run = True
                if aka_in_run:
                    mask[chi_variant] = True

        return mask

    # ---------------------------------------------------------- model forward

    def _run_model(self, action_mask: np.ndarray) -> int:
        """Encode current state → model forward → pick best legal action."""
        # Register decide event (label = 0 for inference)
        self.encoder.on_decide(self.player_id, action_mask.astype(np.uint8), 0)
        # Snapshot track for our seat
        track = self.encoder.track(self.player_id)
        events = np.asarray(track.events(), dtype=np.bool_)
        seq_len = int(events.shape[0])
        max_seq_len = 512
        if seq_len > max_seq_len:
            events = events[-max_seq_len:]
            seq_len = max_seq_len
        from pymahjong.rl.tokenization import EVENT_DIM
        features = np.zeros((seq_len, EVENT_DIM), dtype=np.float32)
        features[:seq_len] = events
        attn_mask = np.ones((seq_len,), dtype=np.bool_)

        with torch.inference_mode():
            feat_t = torch.as_tensor(features, device=self.device).unsqueeze(0)
            attn_t = torch.as_tensor(attn_mask, device=self.device).unsqueeze(0)
            mask_t = torch.as_tensor(action_mask, device=self.device).unsqueeze(0)
            action, _, _ = self.model.act(feat_t, attn_t, mask_t, deterministic=True)
        return int(action.item())

    # --------------------------------------------- action → mjai message

    def _action_to_mjai_self(self, action: int) -> str:
        if 0 <= action < 34:
            tile = basetile_to_mjai(action)
            return self._make_dahai_msg(tile)
        if action == A_DISCARD_RED5M:
            return self._make_dahai_msg("5mr")
        if action == A_DISCARD_RED5P:
            return self._make_dahai_msg("5pr")
        if action == A_DISCARD_RED5S:
            return self._make_dahai_msg("5sr")
        if action == A_RIICHI:
            # Riichi is a two-event protocol in mjai: emit `reach`, then on the
            # next prompt emit `dahai` (with the discard tile that keeps tenpai).
            # The simulator sends back the reach event for us to confirm, then
            # asks for the dahai. We emit reach here and remember the
            # tenpai-preserving discard candidates so the next prompt can pick
            # from them with the model.
            self._pending_riichi = True
            ok, candidates = self._can_riichi()
            self._pending_riichi_candidates = candidates if ok else []
            return json.dumps({"type": "reach", "actor": self.player_id})
        if action == A_TSUMO:
            tile = self.last_self_tsumo or self.my_tehai[-1]
            return json.dumps({
                "type": "hora",
                "actor": self.player_id,
                "target": self.player_id,
                "pai": tile,
            })
        if action == A_ANKAN:
            # Use libriichi's engine-validated candidate list (handles riichi
            # wait-preservation, kan-dora limit, 4-kan abortive, last-wall-tile).
            cands = list(self.ps.ankan_candidates() or [])
            if not cands:
                return '{"type":"none"}'
            normal_str = cands[0]  # mjai tile string, e.g. "5m"
            bt, _ = MJAI_TILE_INFO[normal_str]
            consumed = [normal_str] * 4
            # If aka exists in our hand for this tile, swap one in
            aka_str = None
            if bt == 4: aka_str = "5mr"
            elif bt == 13: aka_str = "5pr"
            elif bt == 22: aka_str = "5sr"
            if aka_str and aka_str in self.my_tehai:
                consumed[0] = aka_str
            return json.dumps({
                "type": "ankan",
                "actor": self.player_id,
                "consumed": consumed,
            })
        if action == A_KAKAN:
            cands = list(self.ps.kakan_candidates() or [])
            if not cands:
                return '{"type":"none"}'
            normal_str = cands[0]
            bt, _ = MJAI_TILE_INFO[normal_str]
            # find the matching pon meld
            for meld in self.my_melds:
                if meld["type"] == "pon":
                    mbt, _ = MJAI_TILE_INFO[meld["called"]]
                    if mbt == bt:
                        aka_str = None
                        if bt == 4: aka_str = "5mr"
                        elif bt == 13: aka_str = "5pr"
                        elif bt == 22: aka_str = "5sr"
                        kakan_tile = aka_str if (aka_str and aka_str in self.my_tehai) else normal_str
                        return json.dumps({
                            "type": "kakan",
                            "actor": self.player_id,
                            "pai": kakan_tile,
                            "consumed": meld["consumed"] + [meld["called"]],
                        })
            return '{"type":"none"}'
        # Fallback: tsumogiri
        if self.last_self_tsumo is not None:
            return self._make_dahai_msg(self.last_self_tsumo, tsumogiri=True)
        return '{"type":"none"}'

    def _action_to_mjai_response(self, action: int, last_dahai: Dict[str, Any]) -> str:
        opp_tile = last_dahai["pai"]
        from_actor = last_dahai["actor"]
        if action == A_PASS_RESPONSE:
            return '{"type":"none"}'
        if action == A_RON:
            return json.dumps({
                "type": "hora",
                "actor": self.player_id,
                "target": from_actor,
                "pai": opp_tile,
            })
        if action == A_PON or action == A_PON_USERED:
            bt, _ = MJAI_TILE_INFO[opp_tile]
            # Find 2 tiles from tehai of this bt; prefer aka if A_PON_USERED
            consumed: List[str] = []
            normal_str = basetile_to_mjai(bt, aka=False)
            aka_str = None
            if bt == 4: aka_str = "5mr"
            elif bt == 13: aka_str = "5pr"
            elif bt == 22: aka_str = "5sr"
            tehai_copy = list(self.my_tehai)
            if action == A_PON_USERED and aka_str and aka_str in tehai_copy:
                consumed.append(aka_str)
                tehai_copy.remove(aka_str)
                # need 1 more normal
                if normal_str in tehai_copy:
                    consumed.append(normal_str)
            else:
                # Two normal tiles preferred (avoid burning aka)
                count_norm = tehai_copy.count(normal_str)
                count_aka = tehai_copy.count(aka_str) if aka_str else 0
                if count_norm >= 2:
                    consumed = [normal_str, normal_str]
                elif count_norm == 1 and count_aka >= 1:
                    consumed = [normal_str, aka_str]  # type: ignore
                elif count_aka >= 2:
                    consumed = [aka_str, aka_str]  # type: ignore
                else:
                    return '{"type":"none"}'
            return json.dumps({
                "type": "pon",
                "actor": self.player_id,
                "target": from_actor,
                "pai": opp_tile,
                "consumed": consumed,
            })
        if action == A_MINKAN:
            bt, _ = MJAI_TILE_INFO[opp_tile]
            normal_str = basetile_to_mjai(bt, aka=False)
            aka_str = None
            if bt == 4: aka_str = "5mr"
            elif bt == 13: aka_str = "5pr"
            elif bt == 22: aka_str = "5sr"
            tehai_copy = list(self.my_tehai)
            consumed = []
            # Take all 3 matching tiles from hand (incl aka if present)
            for t in (aka_str, normal_str, normal_str, normal_str):
                if t and t in tehai_copy:
                    consumed.append(t)
                    tehai_copy.remove(t)
                if len(consumed) == 3:
                    break
            if len(consumed) != 3:
                return '{"type":"none"}'
            return json.dumps({
                "type": "kan",
                "actor": self.player_id,
                "target": from_actor,
                "pai": opp_tile,
                "consumed": consumed,
            })
        if A_CHILEFT <= action <= A_CHIRIGHT_USERED:
            chi_type = (action - A_CHILEFT) % 3   # 0/1/2
            use_red = action >= A_CHILEFT_USERED
            bt, _ = MJAI_TILE_INFO[opp_tile]
            # Determine the 2 tiles we consume from hand.
            # Convention (matches pymahjong.rl.action_space.classify_chi):
            #   chi_type=0 (A_CHILEFT)   = called is LOWEST  -> consumed = [bt+1, bt+2]
            #   chi_type=1 (A_CHIMIDDLE) = called is MIDDLE  -> consumed = [bt-1, bt+1]
            #   chi_type=2 (A_CHIRIGHT)  = called is HIGHEST -> consumed = [bt-2, bt-1]
            if chi_type == 0:
                want = [bt + 1, bt + 2]
            elif chi_type == 1:
                want = [bt - 1, bt + 1]
            else:
                want = [bt - 2, bt - 1]
            consumed = []
            tehai_copy = list(self.my_tehai)
            for w in want:
                normal_str = basetile_to_mjai(w, aka=False)
                aka_str = None
                if w == 4: aka_str = "5mr"
                elif w == 13: aka_str = "5pr"
                elif w == 22: aka_str = "5sr"
                if use_red and aka_str and aka_str in tehai_copy:
                    consumed.append(aka_str)
                    tehai_copy.remove(aka_str)
                elif normal_str in tehai_copy:
                    consumed.append(normal_str)
                    tehai_copy.remove(normal_str)
                elif aka_str and aka_str in tehai_copy:
                    consumed.append(aka_str)
                    tehai_copy.remove(aka_str)
                else:
                    return '{"type":"none"}'
            return json.dumps({
                "type": "chi",
                "actor": self.player_id,
                "target": from_actor,
                "pai": opp_tile,
                "consumed": consumed,
            })
        return '{"type":"none"}'

    def _guarded_emit(self, msg: str) -> str:
        """Validate ``msg`` through libriichi ``ps.validate_reaction``;
        on failure, fall back to a safe action and warn on stderr.

        ``{"type":"none"}`` and reach announcements (``{"type":"reach"}``)
        are passed through without validation — reach pairs with a
        follow-up dahai that gets its own validation.
        """
        try:
            parsed = json.loads(msg)
        except Exception:
            return msg
        t = parsed.get("type")
        if t in ("none", "reach"):
            return msg
        try:
            self.ps.validate_reaction(msg)
            return msg
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(
                f"V5 validate_reaction rejected {parsed!r}: {e}\n"
            )
            # Fallback strategy:
            # - For self-action discards/agari/kans → tsumogiri if possible, else "none"
            # - For response-phase → "none" (pass)
            if t in ("dahai", "hora", "ankan", "kakan", "reach"):
                if self.last_self_tsumo is not None and self.last_self_tsumo in self.my_tehai:
                    fb = self._make_dahai_msg(self.last_self_tsumo, tsumogiri=True)
                    try:
                        self.ps.validate_reaction(fb)
                        return fb
                    except Exception:
                        pass
            return '{"type":"none"}'

    def _make_dahai_msg(self, tile: str, tsumogiri: Optional[bool] = None) -> str:
        # Safety: if the requested tile is not actually in our hand, fall back
        # to a tile that is (prefer the just-drawn tile = tsumogiri, else any
        # tile in tehai). This guards against action-mask bugs causing chombo.
        if tile not in self.my_tehai:
            sys.stderr.write(
                f"V5 dahai sanity: requested {tile} not in tehai {sorted(self.my_tehai)}; "
                f"falling back\n"
            )
            # Prefer tsumogiri (always safe — we just drew this tile)
            if self.last_self_tsumo is not None and self.last_self_tsumo in self.my_tehai:
                tile = self.last_self_tsumo
                tsumogiri = True
            elif self.my_tehai:
                tile = self.my_tehai[-1]
                tsumogiri = None  # recompute below
            else:
                # Should not happen
                return '{"type":"none"}'
        if tsumogiri is None:
            tsumogiri = (tile == self.last_self_tsumo)
        return json.dumps({
            "type": "dahai",
            "actor": self.player_id,
            "pai": tile,
            "tsumogiri": tsumogiri,
        })


# ---------------------------------------------------------------------------
# Main loop (stdio)
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        player_id = int(sys.argv[-1])
        assert 0 <= player_id < 4
    except (ValueError, IndexError, AssertionError):
        print("Usage: python bot.py <player_id (0..3)>", file=sys.stderr)
        return 1

    model_path_env = os.environ.get("V5_MODEL_PATH", "model.pt")
    model_path = Path(model_path_env)
    if not model_path.is_absolute():
        # Look beside bot.py
        model_path = Path(__file__).parent / model_path
    if not model_path.exists():
        print(f"V5 model not found at {model_path}", file=sys.stderr)
        return 2

    bot = V5MjaiBot(player_id, model_path)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = bot.react(line)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc(file=sys.stderr)
            resp = '{"type":"none"}'
        if resp:
            print(resp, flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())

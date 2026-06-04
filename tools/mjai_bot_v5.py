#!/usr/bin/env python3
"""mjai-protocol bot wrapping a V5 (Douzero-head) checkpoint.

This script is the *runtime* for the V5 mjai bot. Package it into a
``bot.zip`` alongside the model checkpoint and a pre-built MahjongPyWrapper
wheel to submit to ``mjai.Simulator``.

Architecture
------------
mjai is event-stream JSON over stdin/stdout. The bot:

1. Parses each incoming event batch.
2. Maintains its own minimal game state in pure Python (so we don't need
   to keep a parallel ``pm.Table`` perfectly in sync with the mjai server,
   which is hard because opponent draws are masked as ``"pai": "?"``).
3. Drives a ``pm.encv4_HandEncoder`` directly via its ``on_*`` hooks so
   the per-player V4 token stream matches what the model was trained on.
4. On a decision event, computes the 54-dim action mask from the mjai
   state, runs the V5 model, picks the best legal action, and emits the
   corresponding mjai action message.

This keeps the encoder logic identical to training (C++ ``encv4``) while
sidestepping the parallel ``pm.Table`` sync problem.

Status: SKELETON — see ``# TODO(mjai-bot)`` markers. The framework is in
place; the remaining work is filling out the action-mask logic for
response phases (pon/chi/kan/ron) and finishing the chi tile-id selection
when emitting chi messages.

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
from pymahjong.rl.encoding import EncodingVersion, get_strategy


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
        self.model = get_strategy(EncodingVersion.V5).create_model(
            transformer_config=cfg, scorer_hidden=scorer_hidden,
        ).to(self.device).eval()
        ck = torch.load(str(model_path), map_location=self.device, weights_only=False)
        state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
        self.model.load_state_dict(state)

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
        # Dealer gets 14 tiles (last one is initial tsumo); convert
        if len(my_tehai) == 14:
            self.last_self_tsumo = my_tehai[-1]

        # Build a stub yama: 13 tiles per player slots; opponents get
        # placeholder tiles. Wall structure for game_init_with_config is
        # internal — we just need a 136-tile vector. Use our real tiles
        # for our slots + any tiles for others.
        # TODO(mjai-bot): verify yama layout matches what pm.Table expects.
        # Below uses a naive layout; may need tweak.
        yama = self._build_initial_yama(my_tehai)

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
        # Now register dora
        dora_idx, dora_aka = MJAI_TILE_INFO[ev["dora_marker"]]
        # encode_init already snapshotted dora from table state; if mjai dora
        # differs (it shouldn't, since we copied into yama), we'd call:
        # self.encoder.on_dora_reveal(basetile_enum(dora_idx), dora_aka)

    def _build_initial_yama(self, my_tehai: List[str]) -> List[int]:
        """Construct a 136-int yama where our seat's draws come from our tehai.

        Tenhou-style wall layout per ``game_init_with_config`` source: the
        wall is dealt 4-4-4-1 in rounds to each seat starting from oya. To
        guarantee our tiles end up in our hand, we need to compute the
        right positions for our seat — see :func:`Mahjong/Table.cpp:185`.

        TODO(mjai-bot): implement the exact yama layout. As a STUB we use
        ``pm.generate_test_yama()`` style random — this means our table's
        initial hand will NOT match ``my_tehai``. The C++ encoder reads
        the hand from table on encode_init(), so this matters.

        WORKAROUND: after game_init_with_config we can call
        ``encoder.fire_init_hand`` with our real tehai bypassing the
        table's hand. Let's go with that path.
        """
        # Fallback: deterministic ordering. NB: opponents' tiles don't matter.
        yama = list(range(136))
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
        """Decide if we should react to last_ev, and emit mjai action."""
        t = last_ev.get("type")

        # === Reach 2-step: server echoed our own reach, now emit dahai
        if t == "reach" and last_ev.get("actor") == self.player_id and getattr(self, "_pending_riichi", False):
            self._pending_riichi = False
            # Pick a discard tile that keeps tenpai
            ok, candidates = self._can_riichi()
            if not ok or not candidates:
                # Fallback: tsumogiri
                if self.last_self_tsumo is not None:
                    return self._make_dahai_msg(self.last_self_tsumo, tsumogiri=True)
                return None
            # Use model to pick among legal tenpai-preserving discards
            mask = np.zeros(ACTION_DIM, dtype=bool)
            for bt in candidates:
                mask[A_DISCARD_BASE + bt] = True
                # Also offer aka variants if we have them
                if bt == 4 and "5mr" in self.my_tehai:
                    mask[A_DISCARD_RED5M] = True
                elif bt == 13 and "5pr" in self.my_tehai:
                    mask[A_DISCARD_RED5P] = True
                elif bt == 22 and "5sr" in self.my_tehai:
                    mask[A_DISCARD_RED5S] = True
            action = self._run_model(mask)
            return self._action_to_mjai_self(action)

        # === Self-action phase: after our own tsumo
        if t == "tsumo" and last_ev.get("actor") == self.player_id:
            return self._self_action()

        # === Response phase: after another player's dahai
        if t == "dahai" and last_ev.get("actor") != self.player_id:
            return self._response_to_dahai(last_ev)

        # === Chankan response to opponent kakan
        if t == "kakan" and last_ev.get("actor") != self.player_id:
            return self._response_to_kakan(last_ev)

        # === No decision needed
        return None

    def _self_action(self) -> str:
        """Pick action after our own tsumo (discard / riichi / tsumo / ankan / kakan / push)."""
        mask = self._compute_self_action_mask()
        action = self._run_model(mask)
        return self._action_to_mjai_self(action)

    def _response_to_dahai(self, last_ev: Dict[str, Any]) -> str:
        """Pick response to opponent's dahai (pass / pon / chi / kan / ron)."""
        mask = self._compute_response_mask(last_ev)
        if not mask.any() or (mask.sum() == 1 and mask[A_PASS_RESPONSE]):
            return '{"type":"none"}'
        action = self._run_model(mask)
        return self._action_to_mjai_response(action, last_ev)

    def _response_to_kakan(self, last_ev: Dict[str, Any]) -> str:
        """Chankan check."""
        # TODO(mjai-bot): check if we can ron on the kakan tile
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

        chi_type: 0=chi-left (opp tile is highest), 1=chi-middle (opp tile is
        middle), 2=chi-right (opp tile is lowest). Only legal from kamicha
        (upstream player). Honor/terminal restrictions apply.
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
        # chi-left: opp tile is highest in run (tiles -2, -1 in suit)
        if idx_in_suit >= 2 and counts[bt - 2] > 0 and counts[bt - 1] > 0:
            out.append((0, bt - 2))
        # chi-middle: opp tile is middle (tiles -1, +1)
        if 1 <= idx_in_suit <= 7 and counts[bt - 1] > 0 and counts[bt + 1] > 0:
            out.append((1, bt - 1))
        # chi-right: opp tile is lowest (tiles +1, +2)
        if idx_in_suit <= 6 and counts[bt + 1] > 0 and counts[bt + 2] > 0:
            out.append((2, bt))
        return out

    def _compute_self_action_mask(self) -> np.ndarray:
        """Return 54-dim bool mask of legal actions in our self-action phase."""
        mask = np.zeros(ACTION_DIM, dtype=bool)
        counts = self._tehai_counts()

        # === Discard legality
        riichi_locked = self.riichi[self.player_id]
        if riichi_locked:
            # Only tsumogiri the just-drawn tile
            tsumo = self.last_self_tsumo
            if tsumo is not None:
                bt, aka = MJAI_TILE_INFO[tsumo]
                if aka and bt == 4:
                    mask[A_DISCARD_RED5M] = True
                elif aka and bt == 13:
                    mask[A_DISCARD_RED5P] = True
                elif aka and bt == 22:
                    mask[A_DISCARD_RED5S] = True
                else:
                    mask[A_DISCARD_BASE + bt] = True
        else:
            # Count normal vs aka separately for 5m/5p/5s
            has_normal: Dict[int, bool] = {}    # bt -> True if normal version in hand
            has_aka: Dict[int, bool] = {}       # bt in (4, 13, 22) -> True if aka 5 in hand
            for tile in self.my_tehai:
                bt, aka = MJAI_TILE_INFO[tile]
                if aka:
                    has_aka[bt] = True
                else:
                    has_normal[bt] = True
            # Enable base-tile discard only if normal version in hand
            for bt, _ in has_normal.items():
                mask[A_DISCARD_BASE + bt] = True
            # Enable aka discard only if aka version in hand
            if has_aka.get(4):
                mask[A_DISCARD_RED5M] = True
            if has_aka.get(13):
                mask[A_DISCARD_RED5P] = True
            if has_aka.get(22):
                mask[A_DISCARD_RED5S] = True
            # For tiles that are 5m/5p/5s and we have ONLY aka (no normal),
            # we must NOT enable A_DISCARD_BASE+bt — which is what the above
            # achieves naturally since has_normal[bt] would be False.

        # === Tsumo
        if self._can_tsumo():
            mask[A_TSUMO] = True

        # === Riichi
        if not riichi_locked:
            ok, _ = self._can_riichi()
            if ok:
                mask[A_RIICHI] = True

        # === Ankan / Kakan
        if self._can_ankan():
            mask[A_ANKAN] = True
        if self._can_kakan():
            mask[A_KAKAN] = True

        # === Kyushukyuhai (skip — rare, may add later)
        # TODO(mjai-bot): kyushukyuhai check

        return mask

    def _compute_response_mask(self, last_dahai: Dict[str, Any]) -> np.ndarray:
        """Return 54-dim mask for responses to opponent's dahai."""
        mask = np.zeros(ACTION_DIM, dtype=bool)
        mask[A_PASS_RESPONSE] = True

        opp_tile = last_dahai["pai"]
        from_actor = last_dahai["actor"]

        # === Ron
        if self._can_ron(opp_tile):
            mask[A_RON] = True

        # If we're in riichi we can't call (only ron/pass)
        if self.riichi[self.player_id]:
            return mask

        # === Pon
        if self._can_pon(opp_tile):
            mask[A_PON] = True
            # red 5 variant: if we have an aka of this tile
            bt, _ = MJAI_TILE_INFO[opp_tile]
            if bt in (4, 13, 22):
                aka_str = {4: "5mr", 13: "5pr", 22: "5sr"}[bt]
                if aka_str in self.my_tehai:
                    mask[A_PON_USERED] = True

        # === Minkan
        if self._can_minkan(opp_tile):
            mask[A_MINKAN] = True

        # === Chi (only from kamicha)
        chi_options = self._can_chi_patterns(opp_tile, from_actor)
        for chi_type, _lowest in chi_options:
            mask[A_CHILEFT + chi_type] = True
            # red-variant flag if either consumed tile is aka 5
            # (will be picked up in action emission)

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
        from pymahjong.rl.v4.tokenization import EVENT_DIM
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
            # asks for the dahai. We emit reach here and remember to pick the
            # best legal riichi discard next time.
            self._pending_riichi = True
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
            # Find first quad in tehai; if multiple, ask model on next pass
            tiles_4 = [bt for bt in range(34) if self._tehai_counts()[bt] >= 4]
            if not tiles_4:
                return '{"type":"none"}'
            bt = tiles_4[0]
            normal_str = basetile_to_mjai(bt)
            consumed = [normal_str] * 4
            # If aka exists, replace one with aka
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
            ka_bts = self._can_kakan()
            if not ka_bts:
                return '{"type":"none"}'
            bt = ka_bts[0]
            # find the matching pon meld
            for meld in self.my_melds:
                if meld["type"] == "pon":
                    mbt, _ = MJAI_TILE_INFO[meld["called"]]
                    if mbt == bt:
                        # which tile in hand we use for kakan (prefer aka if exists)
                        normal_str = basetile_to_mjai(bt)
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
            # Determine the 2 tiles we consume from hand
            if chi_type == 0:
                want = [bt - 2, bt - 1]
            elif chi_type == 1:
                want = [bt - 1, bt + 1]
            else:
                want = [bt + 1, bt + 2]
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

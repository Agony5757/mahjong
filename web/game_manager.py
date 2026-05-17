"""
Game session manager for the mahjong web server.

Wraps MahjongPyWrapper.Table directly (no MahjongEnv detour) and provides:
- A clean state serialization for the front-end (one JSON snapshot)
- Action validation + index→C++ selection resolution (incl. riichi 2-step)
- Multi-kyoku (hansou) loop via HansouSession
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import MahjongPyWrapper as pm

from hansou import HansouSession
from verbose_log import SessionLogger


class GameMode(str, Enum):
    HUMAN_AI = "human_ai"
    FOUR_AI = "4ai"


# ─── Tile / action helpers ────────────────────────────────────────────────────

_BASETILE_NAMES_Z = ("1z", "2z", "3z", "4z", "5z", "6z", "7z")


def basetile_to_str(bt: int) -> str:
    if bt < 9:
        return f"{bt + 1}m"
    if bt < 18:
        return f"{bt - 9 + 1}p"
    if bt < 27:
        return f"{bt - 18 + 1}s"
    return _BASETILE_NAMES_Z[bt - 27]


def basetile_to_zh(bt: int) -> str:
    """Display label like '5万' for logs."""
    if bt < 9:
        return f"{bt + 1}万"
    if bt < 18:
        return f"{bt - 9 + 1}饼"
    if bt < 27:
        return f"{bt - 18 + 1}索"
    names = ("东", "南", "西", "北", "白", "发", "中")
    return names[bt - 27]


# ─── Action index ↔ BaseAction mapping (matches encv1, see TrainingDataEncodingV1.cpp) ─
#   0..33  : Discard basetile i (no red)
#   34     : Discard red 5m
#   35     : Discard red 5p
#   36     : Discard red 5s
#   37     : Chi left
#   38     : Chi middle
#   39     : Chi right
#   40..42 : Chi left/middle/right (use red dora)
#   43     : Pon
#   44     : Pon (use red)
#   45     : AnKan
#   46     : Minkan (Kan response)
#   47     : KaKan
#   48     : Riichi (confirm)
#   49     : Ron / ChanKan / ChanAnKan
#   50     : Tsumo
#   51     : Kyushukyuhai
#   52     : Pass riichi (cancel)
#   53     : Pass response

DISCARD_RED_BASE = 34   # 34,35,36 = red5 of m/p/s
CHILEFT, CHIMIDDLE, CHIRIGHT = 37, 38, 39
CHILEFT_R, CHIMID_R, CHIRIGHT_R = 40, 41, 42
PON, PON_USERED = 43, 44
ANKAN, MINKAN, KAKAN = 45, 46, 47
RIICHI = 48
RON = 49
TSUMO = 50
KYUSHU = 51
PASS_RIICHI = 52
PASS_RESPONSE = 53

_CHI_SET = {CHILEFT, CHIMIDDLE, CHIRIGHT, CHILEFT_R, CHIMID_R, CHIRIGHT_R}


class MahjongEnvAdapter:
    """Thin wrapper over pm.Table that drives one kyoku at a time and supports reset."""

    def __init__(self, mode: GameMode, seed: Optional[int] = None):
        self.mode = mode
        self.base_seed = seed
        self.t: pm.Table = pm.Table()
        self._riichi_stage2 = False
        self._may_riichi_tile_id: Optional[int] = None
        # Lifecycle callbacks (post-reset_kyoku and post-step).
        self._on_kyoku_start_cbs: list = []
        self._on_step_cbs: list = []

    # ─── Callback registration ───────────────────────────────────────────────

    def add_on_kyoku_start(self, cb) -> None:
        """Register a no-arg callback fired after each ``reset_kyoku``."""
        self._on_kyoku_start_cbs.append(cb)

    def add_on_step(self, cb) -> None:
        """Register a no-arg callback fired after each successful ``step``."""
        self._on_step_cbs.append(cb)

    def clear_callbacks(self) -> None:
        self._on_kyoku_start_cbs.clear()
        self._on_step_cbs.clear()

    def _fire_kyoku_start(self) -> None:
        for cb in self._on_kyoku_start_cbs:
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass  # don't let AI bookkeeping break the engine loop

    def _fire_on_step(self) -> None:
        for cb in self._on_step_cbs:
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def reset_kyoku(
        self,
        *,
        oya: int,
        game_wind: str,
        scores: list,
        kyoutaku: int,
        honba: int,
        seed: Optional[int] = None,
    ) -> None:
        """Initialize the C++ Table for a fresh kyoku."""
        wind_idx = ("east", "south", "west", "north").index(game_wind)
        self.t = pm.Table()
        if seed is None and self.base_seed is not None:
            seed = self.base_seed + (oya * 4 + wind_idx) * 31  # deterministic per kyoku
        if seed is not None:
            self.t.set_seed(seed)
        self.t.game_init_with_config(
            [],          # random yama
            list(scores),
            int(kyoutaku),
            int(honba),
            wind_idx,
            int(oya),
        )
        self._riichi_stage2 = False
        self._may_riichi_tile_id = None
        self._auto_skip_pass()
        self._fire_kyoku_start()

    def _auto_skip_pass(self) -> None:
        """Auto-advance through phases that have only a single forced action (pass)."""
        while not self.is_over():
            if self.t.get_phase() < 4:
                actions = self.t.get_self_actions()
            elif self.t.get_phase() < 16:
                actions = self.t.get_response_actions()
            else:
                break
            if len(actions) > 1:
                break
            self.t.make_selection(0)

    # ─── Convenience accessors ───────────────────────────────────────────────

    def is_over(self) -> bool:
        return self.t.get_phase() == int(pm.PhaseEnum.GAME_OVER)

    def get_phase(self) -> int:
        return int(self.t.get_phase())

    def get_curr_player(self) -> int:
        return int(self.t.who_make_selection())

    def is_self_action(self) -> bool:
        return self.get_phase() < 4

    def get_result(self):
        return self.t.get_result() if self.is_over() else None

    # ─── Action validation ───────────────────────────────────────────────────

    def get_valid_actions_mask(self, player_id: int) -> np.ndarray:
        if self._riichi_stage2:
            mask = np.zeros(54, dtype=np.int8)
            mask[RIICHI] = 1
            mask[PASS_RIICHI] = 1
            return mask.astype(bool)
        container = np.zeros(54, dtype=np.int8)
        pm.encv1_encode_action(self.t, player_id, container)
        return container.astype(bool)

    def get_valid_actions(self, player_id: int) -> list[int]:
        mask = self.get_valid_actions_mask(player_id)
        return [int(i) for i in range(54) if mask[i]]

    # ─── Action resolution ───────────────────────────────────────────────────

    def step(self, player_id: int, action_idx: int) -> None:
        """Apply one action. Raises ValueError if invalid."""
        if player_id != self.get_curr_player():
            raise ValueError(
                f"Player {player_id} cannot act now (current={self.get_curr_player()})"
            )

        # Riichi stage 2 (confirm/cancel)
        if self._riichi_stage2:
            if action_idx not in (RIICHI, PASS_RIICHI):
                raise ValueError("In riichi stage 2 you must choose RIICHI or PASS_RIICHI")
            self._apply_riichi_stage2(player_id, action_idx)
            return

        mask = self.get_valid_actions_mask(player_id)
        if not mask[action_idx]:
            raise ValueError(f"Action {action_idx} is not valid for player {player_id}")

        # Riichi stage 1 detection: discard chosen + RIICHI is valid + tile is in riichi tile list
        if mask[RIICHI] and self._is_discard_action(action_idx):
            riichi_tiles = set(int(r) for r in pm.encv1_get_riichi_tiles(self.t))
            if action_idx in riichi_tiles:
                self._riichi_stage2 = True
                self._may_riichi_tile_id = action_idx
                return

        action_type, tiles, use_red = self._resolve_action(player_id, action_idx)
        self._submit_to_engine(action_type, tiles, use_red)
        self._fire_on_step()
        # Note: do NOT auto-skip here. The C++ engine handles the discarder's
        # auto-pass internally in _handle_response_action(). Auto-skipping in
        # Python would consume multiple game steps at once, causing the frontend
        # to miss intermediate turns (e.g. jumping from P1_RESPONSE straight to
        # P4_ACTION and showing "P3 thinking" instead of the human's response).

    def _is_discard_action(self, action_idx: int) -> bool:
        return action_idx <= 36

    def _apply_riichi_stage2(self, player_id: int, action_idx: int) -> None:
        riichi_idx = self._may_riichi_tile_id
        self._riichi_stage2 = False
        self._may_riichi_tile_id = None
        if riichi_idx is None:
            raise ValueError("No pending riichi tile")
        if action_idx == RIICHI:
            # The C++ engine has one Riichi self-action per riichi-eligible tile,
            # each carrying the specific discard tile in correspond_tiles.
            # Selecting that Riichi action automatically handles the discard.
            _, basetiles, use_red = self._resolve_discard(riichi_idx)
            target_bt = basetiles[0]
            self_actions = self.t.get_self_actions()
            for i, a in enumerate(self_actions):
                if a.action == pm.BaseAction.Riichi and a.correspond_tiles:
                    ct = a.correspond_tiles[0]
                    if int(ct.tile) == target_bt and bool(ct.red_dora) == use_red:
                        self.t.make_selection(i)
                        self._auto_skip_pass()
                        self._fire_on_step()
                        return
            raise ValueError(
                f"No Riichi action found for basetile={target_bt} red={use_red}"
            )
        else:
            # PASS_RIICHI: discard normally without declaring riichi
            d_type, d_tiles, d_red = self._resolve_discard(riichi_idx)
            self.t.make_selection_from_action_basetile(
                d_type, [pm.BaseTile(t) for t in d_tiles], d_red
            )
            self._auto_skip_pass()
            self._fire_on_step()

    def _resolve_discard(self, action_idx: int) -> tuple:
        if action_idx < 34:
            return (pm.BaseAction.Discard, [action_idx], False)
        if action_idx == 34:  # red 5m
            return (pm.BaseAction.Discard, [4], True)
        if action_idx == 35:  # red 5p
            return (pm.BaseAction.Discard, [13], True)
        if action_idx == 36:  # red 5s
            return (pm.BaseAction.Discard, [22], True)
        return (pm.BaseAction.Discard, [min(action_idx, 33)], False)

    def _resolve_action(self, player_id: int, action_idx: int) -> tuple:
        if self._is_discard_action(action_idx):
            return self._resolve_discard(action_idx)

        t = self.t
        # In response phase, the action_tile is the just-discarded tile.
        sel_id = -1
        try:
            sel_tile = t.get_selected_action_tile()
            if sel_tile is not None:
                sel_id = int(sel_tile.tile)
        except Exception:
            pass

        if action_idx in _CHI_SET:
            use_red = action_idx >= CHILEFT_R
            kind = (action_idx - CHILEFT) % 3  # 0=left,1=mid,2=right
            if kind == 0:
                tiles = [sel_id + 1, sel_id + 2]
            elif kind == 1:
                tiles = [sel_id - 1, sel_id + 1]
            else:
                tiles = [sel_id - 2, sel_id - 1]
            return (pm.BaseAction.Chi, tiles, use_red)
        if action_idx in (PON, PON_USERED):
            return (pm.BaseAction.Pon, [sel_id, sel_id], action_idx == PON_USERED)
        if action_idx == MINKAN:
            return (pm.BaseAction.Kan, [sel_id, sel_id, sel_id], False)
        if action_idx == ANKAN:
            for a in t.get_self_actions():
                if a.action == pm.BaseAction.AnKan and a.correspond_tiles:
                    bt = int(a.correspond_tiles[0].tile)
                    return (pm.BaseAction.AnKan, [bt] * 4, False)
            return (pm.BaseAction.AnKan, [sel_id] * 4, False)
        if action_idx == KAKAN:
            for a in t.get_self_actions():
                if a.action == pm.BaseAction.KaKan and a.correspond_tiles:
                    bt = int(a.correspond_tiles[0].tile)
                    return (pm.BaseAction.KaKan, [bt], False)
            return (pm.BaseAction.KaKan, [sel_id], False)
        if action_idx == RON:
            return (pm.BaseAction.Ron, [], False)
        if action_idx == TSUMO:
            return (pm.BaseAction.Tsumo, [], False)
        if action_idx == KYUSHU:
            return (pm.BaseAction.Kyushukyuhai, [], False)
        if action_idx in (PASS_RESPONSE, PASS_RIICHI):
            return (pm.BaseAction.Pass, [], False)
        return (pm.BaseAction.Pass, [], False)

    def _submit_to_engine(self, action_type, tiles, use_red) -> None:
        self.t.make_selection_from_action_basetile(
            action_type, [pm.BaseTile(t) for t in tiles], use_red
        )

    # ─── Random helper ───────────────────────────────────────────────────────

    def random_action(self, player_id: int) -> int:
        return int(np.random.choice(self.get_valid_actions(player_id)))


# ─── Serialization ─────────────────────────────────────────────────────────────

_WIND_NAMES = ("East", "South", "West", "North")
_PHASE_NAMES = (
    "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION",
    "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE", "P4_RESPONSE",
    "P1_CHANKAN", "P2_CHANKAN", "P3_CHANKAN", "P4_CHANKAN",
    "P1_CHANANKAN", "P2_CHANANKAN", "P3_CHANANKAN", "P4_CHANANKAN",
    "GAME_OVER",
)


def _tile_dict(tile) -> dict:
    bt = int(tile.tile)
    return {
        "id": int(tile.id),
        "basetile": bt,
        "str": basetile_to_str(bt),
        "red_dora": bool(tile.red_dora),
    }


def _player_dict(t: pm.Table, pid: int, hide_hand: bool) -> dict:
    p = t.players[pid]
    if hide_hand:
        hand = [{"count": len(p.hand)}]
    else:
        hand = [_tile_dict(x) for x in p.hand]

    river = []
    for rt in p.get_river().river:
        river.append({
            "tile": _tile_dict(rt.tile),
            "number": int(rt.number),
            "riichi": bool(rt.riichi),
            "remain": bool(rt.remain),
            "fromhand": bool(rt.fromhand),
        })

    calls = []
    for cg in p.get_fuuros():
        try:
            type_str = pm.CallGroupToString(cg)
        except Exception:
            type_str = "Unknown"
        # Determine the player from whose discard this call was made.
        # Default to -1 (unknown / AnKan). The C++ engine's CallGroup may not
        # expose this directly; we encode meld type so the front-end can
        # render orientation correctly.
        from_who = -1
        try:
            from_who = int(getattr(cg, "from_who", -1))
        except Exception:
            pass
        calls.append({
            "type": type_str,
            "tiles": [_tile_dict(x) for x in cg.tiles],
            "take": int(cg.take),
            "from_who": from_who,
        })

    return {
        "player_id": pid,
        "wind": _WIND_NAMES[int(p.wind)],
        "is_oya": bool(p.oya),
        "score": int(p.score),
        "hand": hand,
        "river": river,
        "calls": calls,
        "tenpai": [basetile_to_str(int(at)) for at in p.atari_tiles],
        "riichi": bool(p.riichi),
        "double_riichi": bool(p.double_riichi),
        "menzen": bool(p.menzen),
        "furiten": bool(p.is_furiten()),
    }


def build_state(adapter: MahjongEnvAdapter, hansou: HansouSession,
                hide_hands_except: Optional[int] = None) -> dict:
    """Serialize the full table + hansou state for the frontend.

    ``hide_hands_except``:
        None → reveal all hands (4-AI/replay viewer)
        i ∈ 0..3 → hide all hands except player i (human-vs-AI)
    """
    t = adapter.t
    phase = adapter.get_phase()
    curr = adapter.get_curr_player() if not adapter.is_over() else -1

    players = []
    for i in range(4):
        hide = hide_hands_except is not None and i != hide_hands_except
        players.append(_player_dict(t, i, hide))

    valid = []
    valid_mask = [False] * 54
    if curr >= 0:
        valid = adapter.get_valid_actions(curr)
        valid_mask = adapter.get_valid_actions_mask(curr).tolist()

    result = None
    if adapter.is_over():
        r = t.get_result()
        if r is not None:
            try:
                loser_list = list(r.loser) if r.loser is not None else []
            except TypeError:
                loser_list = [int(r.loser)] if r.loser is not None else []
            try:
                winner_list = [int(w) for w in list(r.winner)] if r.winner is not None else []
            except TypeError:
                winner_list = [int(r.winner)] if r.winner is not None else []
            result = {
                "type": str(r.result_type).split(".")[-1],
                "scores": list(r.score),
                "winner": winner_list,
                "loser": loser_list,
                "honba": int(r.n_honba),
                "kyoutaku": int(r.n_riichibo),
                "renchan": bool(r.renchan),
            }

    snapshot = {
        "phase": phase,
        "phase_name": _PHASE_NAMES[phase] if phase < len(_PHASE_NAMES) else "GAME_OVER",
        "turn": curr,
        "oya": int(t.oya),
        "game_wind": _WIND_NAMES[int(t.game_wind)],
        "honba": int(t.honba),
        "kyoutaku": int(t.riichibo),
        "tiles_left": int(t.get_remain_tile()),
        "dora": [basetile_to_str(int(d)) for d in t.get_dora()],
        "ura_dora": [basetile_to_str(int(d)) for d in t.get_ura_dora()],
        "players": players,
        "valid_actions": valid,
        "valid_actions_mask": valid_mask,
        "riichi_stage2": adapter._riichi_stage2,
        "riichi_tile": adapter._may_riichi_tile_id,
        "is_over": adapter.is_over(),
        "result": result,
        "hansou": hansou.snapshot(),
    }
    return snapshot


# ─── Session bookkeeping ──────────────────────────────────────────────────────


@dataclass
class GameSession:
    session_id: str
    mode: GameMode
    adapter: MahjongEnvAdapter
    hansou: HansouSession
    human_player_id: int = -1
    action_log: list = field(default_factory=list)
    logger: Optional[SessionLogger] = None

    def get_state(self, for_player: Optional[int] = None) -> dict:
        hide = None
        if self.mode == GameMode.HUMAN_AI and for_player is not None:
            hide = for_player
        return build_state(self.adapter, self.hansou, hide_hands_except=hide)

    def step(self, player_id: int, action_idx: int) -> dict:
        # Snapshot pre-step context for verbose log.
        if self.logger is not None:
            try:
                pre_phase = self.adapter.get_phase()
                pre_curr = self.adapter.get_curr_player()
                pre_valid = self.adapter.get_valid_actions(player_id)
                self.logger.log("step_in", {
                    "player": player_id,
                    "action_idx": action_idx,
                    "phase": pre_phase,
                    "curr_player": pre_curr,
                    "valid_actions": pre_valid,
                    "riichi_stage2": self.adapter._riichi_stage2,
                    "tiles_left": int(self.adapter.t.get_remain_tile()),
                })
            except Exception as e:
                self.logger.log_exception("step_in_snapshot_fail", e)
        try:
            self.adapter.step(player_id, action_idx)
        except Exception as e:
            if self.logger is not None:
                self.logger.log_exception("step_error", e,
                                          player=player_id, action_idx=action_idx)
            raise
        self.action_log.append({"player": player_id, "action": action_idx})
        if self.logger is not None:
            try:
                self.logger.log("step_out", {
                    "player": player_id,
                    "action_idx": action_idx,
                    "phase": self.adapter.get_phase(),
                    "curr_player": self.adapter.get_curr_player() if not self.adapter.is_over() else -1,
                    "is_over": self.adapter.is_over(),
                })
            except Exception as e:
                self.logger.log_exception("step_out_snapshot_fail", e)
        return self.get_state(for_player=self.human_player_id if self.human_player_id >= 0 else None)


class GameManager:
    """Manages active game sessions."""

    def __init__(self):
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        mode: GameMode = GameMode.HUMAN_AI,
        seed: Optional[int] = None,
        max_round: int = 1,
    ) -> GameSession:
        adapter = MahjongEnvAdapter(mode=mode, seed=seed)
        hansou = HansouSession(env=adapter, max_round=max_round)
        hansou.start_first_kyoku(seed=seed)
        sid = str(uuid.uuid4())
        slogger = SessionLogger(sid, mode.value, seed, max_round)
        slogger.log("kyoku_init", {
            "kyoku": hansou.snapshot(),
            "phase": adapter.get_phase(),
            "curr_player": adapter.get_curr_player(),
        })
        session = GameSession(
            session_id=sid,
            mode=mode,
            adapter=adapter,
            hansou=hansou,
            human_player_id=0 if mode == GameMode.HUMAN_AI else -1,
            logger=slogger,
        )
        with self._lock:
            self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[GameSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        with self._lock:
            return [
                {"session_id": sid, "mode": s.mode.value,
                 "kyoku_count": s.hansou.kyoku_count,
                 "finished": s.hansou.finished}
                for sid, s in self._sessions.items()
            ]

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            sess = self._sessions.pop(session_id, None)
        if sess is None:
            return False
        if sess.logger is not None:
            sess.logger.close()
        return True

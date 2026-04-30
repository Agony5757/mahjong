"""
Game session manager for the mahjong web server.
Wraps MahjongEnv and provides clean state serialization for the frontend.
"""
import uuid
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

import numpy as np

import MahjongPyWrapper as pm


class GameMode(str, Enum):
    HUMAN_AI = "human_ai"   # Human vs 3 AI
    FOUR_AI = "4ai"         # 4 AI battle


@dataclass
class GameSession:
    """A single mahjong game session."""
    session_id: str
    mode: GameMode
    env: 'MahjongEnvWrapper'
    status: str = "playing"   # "playing", "waiting_ai", "finished"
    action_log: list = field(default_factory=list)
    human_player_id: int = 0  # Which player is the human (only in human_ai mode)

    def step(self, player_id: int, action_idx: int) -> dict:
        """Execute an action and return the result."""
        return self.env.step(player_id, action_idx)

    def ai_step(self, ai_player_id: int) -> int:
        """Execute AI action for the given player. Returns action index."""
        action_idx = self.env.get_random_action(ai_player_id)
        self.env.step(ai_player_id, action_idx)
        self.action_log.append({"player": ai_player_id, "action": action_idx})
        return action_idx

    def get_state(self, for_player: int) -> dict:
        """Get full game state from perspective of for_player."""
        return self.env.get_state(for_player)

    def get_public_state(self) -> dict:
        """Get public state (for observers like AI battle spectators)."""
        return self.env.get_public_state()

    def to_paipu(self) -> dict:
        """Export the game as a paipu-compatible dict."""
        return self.env.to_paipu()


class MahjongEnvWrapper:
    """Wraps MahjongEnv for web server use."""

    # Action indices
    CHILEFT, CHIMIDDLE, CHIRIGHT = 37, 38, 39
    CHILEFT_USERED, CHIMIDDLE_USERED, CHIRIGHT_USERED = 40, 41, 42
    PON, PON_USERED = 43, 44
    ANKAN, MINKAN, KAKAN = 45, 46, 47
    RIICHI = 48
    RON = 49
    TSUMO = 50
    PUSH = 51
    PASS_RIICHI = 52
    PASS_RESPONSE = 53

    ACTION_TYPES = (
        [pm.BaseAction.Discard] * 37 +
        [pm.BaseAction.Chi] * 6 +
        [pm.BaseAction.Pon] * 2 +
        [pm.BaseAction.AnKan, pm.BaseAction.Kan, pm.BaseAction.KaKan] +
        [pm.BaseAction.Riichi, pm.BaseAction.Ron, pm.BaseAction.Tsumo,
         pm.BaseAction.Pass, pm.BaseAction.Pass, pm.BaseAction.Pass]
    )

    def __init__(self, mode: GameMode = GameMode.HUMAN_AI, ai_model_path: Optional[str] = None, seed: Optional[int] = None):
        import gymnasium as gym
        from pymahjong.env_pymahjong import MahjongEnv

        self.mode = mode
        self.ai_model_path = ai_model_path
        self._env = MahjongEnv()
        self._seed = seed
        self._riichi_stage2 = False
        self._may_riichi_tile_id = None

        # Initialize
        self._env.t = pm.Table()
        if seed is not None:
            self._env.t.set_seed(seed)
        self._env.t.game_init_with_config(
            [],  # random yama
            [25000, 25000, 25000, 25000],
            0, 0, 0, 0  # kyoutaku, honba, game_wind=East, oya=0
        )
        self._env.riichi_stage2 = False
        self._env.may_riichi_tile_id = None
        self._env.game_count = 1
        self._proceed()

    def _proceed(self):
        """Auto-advance through pass-only phases."""
        while not self.is_over():
            phase = self._env.t.get_phase()
            if phase < 4:
                aval = self._env.t.get_self_actions()
            elif phase < 16:
                aval = self._env.t.get_response_actions()
            else:
                aval = [-1]
            if len(aval) > 1:
                break
            self._env.t.make_selection(0)

    def is_over(self) -> bool:
        return self._env.t.get_phase() == 16  # GAME_OVER

    def get_curr_player(self) -> int:
        """Returns the player ID who needs to act."""
        return self._env.t.who_make_selection()

    def is_self_action(self) -> bool:
        return self._env.t.get_phase() < 4

    def get_phase(self) -> int:
        return self._env.t.get_phase()

    def get_scores(self) -> list:
        return list(self._env.t.get_scores())

    def get_result(self):
        if not self.is_over():
            return None
        return self._env.t.get_result()

    # ─── Action Validation ───────────────────────────────────────────────────────

    def _build_act_container(self, player_id: int) -> np.ndarray:
        container = np.zeros(54, dtype=np.int8)
        pm.encv1_encode_action(self._env.t, player_id, container)
        return container

    def get_valid_actions(self, player_id: int) -> list:
        """Returns list of valid action indices."""
        if self._riichi_stage2:
            # Only RIICHI (48) or PASS_RIICHI (52)
            return [48, 52]
        container = self._build_act_container(player_id)
        return [i for i in range(54) if container[i] == 1]

    def get_valid_actions_mask(self, player_id: int) -> np.ndarray:
        """Returns 54-dim boolean mask."""
        container = self._build_act_container(player_id)
        return container.astype(bool)

    def _resolve_action(self, player_id: int, action_idx: int) -> tuple:
        """
        Resolve action index to (BaseAction, list of basetiles, use_red_dora).
        Returns the C++ make_selection parameters.
        """
        if self._riichi_stage2:
            # Riichi confirmed or cancelled
            riichi_idx = self._may_riichi_tile_id
            self._riichi_stage2 = False
            self._may_riichi_tile_id = None

            if action_idx == 48:  # RIICHI confirmed
                # First, execute the discard (with riichi flag)
                discard_type, discard_tiles, discard_red = \
                    self._resolve_discard_action(riichi_idx)
                self._env.t.make_selection_from_action_basetile(
                    discard_type,
                    [pm.BaseTile(t) for t in discard_tiles],
                    discard_red)
                # Then call make_selection with Riichi to complete the two-step
                self._env.t.make_selection(48)  # RIICHI = index 48
                self._proceed()
                return (None, [], False)  # Already handled
            else:  # PASS_RIICHI (52) — cancel riichi, just discard
                discard_type, discard_tiles, discard_red = \
                    self._resolve_discard_action(riichi_idx)
                self._env.t.make_selection_from_action_basetile(
                    discard_type,
                    [pm.BaseTile(t) for t in discard_tiles],
                    discard_red)
                self._proceed()
                return (None, [], False)

        action_type = self.ACTION_TYPES[action_idx]
        corresponding_tiles = []
        use_red_dora = False

        t = self._env.t
        selected_tile = t.get_selected_action_tile()

        if action_idx < 37:  # Normal discard
            corresponding_tiles = [action_idx]
        elif action_idx == 37:  # red 5m
            corresponding_tiles = [4]; use_red_dora = True
        elif action_idx == 38:  # red 5p
            corresponding_tiles = [13]; use_red_dora = True
        elif action_idx == 39:  # red 5s
            corresponding_tiles = [22]; use_red_dora = True
        elif action_idx == 40:  # chi left + red
            tile_id = int(selected_tile.tile)
            corresponding_tiles = [tile_id + 1, tile_id + 2]; use_red_dora = True
        elif action_idx == 41:  # chi middle + red
            tile_id = int(selected_tile.tile)
            corresponding_tiles = [tile_id - 1, tile_id + 1]; use_red_dora = True
        elif action_idx == 42:  # chi right + red
            tile_id = int(selected_tile.tile)
            corresponding_tiles = [tile_id - 2, tile_id - 1]; use_red_dora = True
        elif action_idx in (40, 41, 42):  # already handled above, skip
            pass
        elif action_idx in (self.CHILEFT, self.CHIMIDDLE, self.CHIRIGHT):
            tile_id = int(selected_tile.tile)
            if action_idx == self.CHILEFT:
                corresponding_tiles = [tile_id + 1, tile_id + 2]
            elif action_idx == self.CHIMIDDLE:
                corresponding_tiles = [tile_id - 1, tile_id + 1]
            elif action_idx == self.CHIRIGHT:
                corresponding_tiles = [tile_id - 2, tile_id - 1]
        elif action_idx == self.PON:
            corresponding_tiles = [int(selected_tile.tile), int(selected_tile.tile)]
        elif action_idx == self.PON_USERED:
            corresponding_tiles = [int(selected_tile.tile), int(selected_tile.tile)]
            use_red_dora = True
        elif action_idx == self.MINKAN:
            kan_id = int(selected_tile.tile)
            corresponding_tiles = [kan_id, kan_id, kan_id]
        elif action_idx == self.ANKAN:
            player = self._env.t.players[player_id]
            if player.riichi or player.double_riichi:
                kan_id = int(player.hand[-1].tile)
            else:
                valid = self.get_valid_actions_mask(player_id)
                kan_candidates = [i for i in range(54) if valid[i] == 1 and self.ACTION_TYPES[i] == pm.BaseAction.AnKan]
                kan_id = kan_candidates[0] if kan_candidates else int(player.hand[-1].tile)
            corresponding_tiles = [kan_id, kan_id, kan_id, kan_id]
        elif action_idx == self.KAKAN:
            obs = self._env.get_obs(player_id)
            valid = self.get_valid_actions_mask(player_id)
            kan_candidates = [i for i in range(54) if valid[i] == 1 and self.ACTION_TYPES[i] == pm.BaseAction.KaKan]
            kan_id = kan_candidates[0] if kan_candidates else int(selected_tile.tile)
            corresponding_tiles = [kan_id]
        elif action_idx in (self.RON, self.TSUMO, self.PUSH, self.PASS_RESPONSE):
            corresponding_tiles = []

        return (action_type, corresponding_tiles, use_red_dora)

    def _resolve_discard_action(self, action_idx: int) -> tuple:
        """Resolve a discard action index to (BaseAction, basetiles, use_red_dora)."""
        if action_idx < 37:
            return (pm.BaseAction.Discard, [action_idx], False)
        elif action_idx == 37:
            return (pm.BaseAction.Discard, [4], True)
        elif action_idx == 38:
            return (pm.BaseAction.Discard, [13], True)
        elif action_idx == 39:
            return (pm.BaseAction.Discard, [22], True)
        return (pm.BaseAction.Discard, [action_idx], False)

    def step(self, player_id: int, action_idx: int) -> dict:
        """Execute a step. Returns the new game state."""
        if player_id != self.get_curr_player():
            raise ValueError(f"Player {player_id} cannot act (current: {self.get_curr_player()})")

        # Validate action
        container = self._build_act_container(player_id)
        if self._riichi_stage2:
            if action_idx not in (48, 52):
                raise ValueError("In riichi stage 2, must choose RIICHI (48) or PASS_RIICHI (52)")
        else:
            if container[action_idx] == 0:
                raise ValueError(f"Action {action_idx} is not valid for player {player_id}")

        # Riichi stage 1: player chose a riichi-eligible tile — defer until confirm
        if not self._riichi_stage2:
            riichi_tiles = pm.encv1_get_riichi_tiles(self._env.t)
            riichi_tile_ids = set(int(r) for r in riichi_tiles)
            if action_idx in riichi_tile_ids and container[self.RIICHI]:
                self._riichi_stage2 = True
                self._may_riichi_tile_id = action_idx
                return self._build_state(player_id)

        # Riichi stage 2: player confirmed (48) or cancelled (52)
        if self._riichi_stage2:
            self._resolve_action(player_id, action_idx)
            return self._build_state(player_id)

        # Normal action
        action_type, tiles, use_red = self._resolve_action(player_id, action_idx)
        self._env.t.make_selection_from_action_basetile(
            action_type, [pm.BaseTile(t) for t in tiles], use_red)
        self._proceed()
        return self._build_state(player_id)

    def get_random_action(self, player_id: int) -> int:
        """Get a random valid action for AI."""
        valid = self.get_valid_actions(player_id)
        return int(np.random.choice(valid))

    # ─── State Serialization ────────────────────────────────────────────────────

    def _basetile_to_str(self, bt: int) -> str:
        """Convert basetile (0-33) to string like '5m', '1z'."""
        if bt < 9:
            return f"{bt+1}m"
        elif bt < 18:
            return f"{bt-9+1}p"
        elif bt < 27:
            return f"{bt-18+1}s"
        else:
            names = ["1z", "2z", "3z", "4z", "5z", "6z", "7z"]
            return names[bt - 27]

    def _tile_to_dict(self, tile) -> dict:
        """Serialize a Tile to dict."""
        return {
            "id": int(tile.id),
            "basetile": int(tile.tile),
            "str": self._basetile_to_str(int(tile.tile)),
            "red_dora": bool(tile.red_dora)
        }

    def _player_to_dict(self, pid: int, for_pid: int, hide_hand: bool) -> dict:
        """Serialize a Player's visible state."""
        p = self._env.t.players[pid]
        t = self._env.t

        # Hand
        if hide_hand:
            hand = [{"count": len(p.hand)}]  # Only show count
        else:
            hand = [self._tile_to_dict(t) for t in p.hand]

        # River
        river = []
        for rt in p.river.river:
            river.append({
                "tile": self._tile_to_dict(rt.tile),
                "number": int(rt.number),
                "riichi": bool(rt.riichi),
                "fromhand": bool(rt.fromhand)
            })

        # Call groups
        calls = []
        for cg in p.call_groups:
            calls.append({
                "type": str(cg.type).split("::")[-1],
                "tiles": [self._tile_to_dict(t) for t in cg.tiles],
                "take": int(cg.take)
            })

        # Atari tiles (tenpai)
        atari = [self._basetile_to_str(int(at)) for at in p.atari_tiles]

        wind_names = ["East", "South", "West", "North"]

        return {
            "player_id": pid,
            "wind": wind_names[int(p.wind)],
            "is_oya": bool(p.oya),
            "score": int(p.score),
            "hand": hand,
            "river": river,
            "calls": calls,
            "tenpai": atari,
            "riichi": bool(p.riichi),
            "double_riichi": bool(p.double_riichi),
            "menzen": bool(p.menzen),
            "furiten": bool(p.is_furiten()),
        }

    def _build_state(self, for_pid: int) -> dict:
        """Build a full state dict from perspective of for_pid."""
        t = self._env.t
        phase = t.get_phase()

        wind_names = ["East", "South", "West", "North"]
        phase_names = [
            "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION",
            "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE", "P4_RESPONSE",
            "P1_CHANKAN", "P2_CHANKAN", "P3_CHANKAN", "P4_CHANKAN",
            "P1_CHANANKAN", "P2_CHANANKAN", "P3_CHANANKAN", "P4_CHANANKAN",
            "GAME_OVER"
        ]

        curr = self.get_curr_player()
        valid = self.get_valid_actions(for_pid)
        phase_name = phase_names[phase] if phase < 17 else "GAME_OVER"

        # Dora
        dora = [self._basetile_to_str(int(d)) for d in t.get_dora()]
        ura_dora = [self._basetile_to_str(int(d)) for d in t.get_ura_dora()]

        # Players
        hide_hands = (self.mode == GameMode.HUMAN_AI)
        players = [self._player_to_dict(i, for_pid, hide_hands and i != for_pid) for i in range(4)]

        # Result
        result = None
        if self.is_over():
            r = t.get_result()
            if r:
                result = {
                    "type": str(r.result_type).split("::")[-1],
                    "scores": list(r.score),
                    "winner": list(r.winner) if r.winner else [],
                    "loser": int(r.loser) if r.loser else None,
                    "honba": int(r.n_honba),
                    "renchan": bool(r.renchan)
                }

        return {
            "phase": phase,
            "phase_name": phase_name,
            "turn": int(curr),
            "oya": int(t.oya),
            "game_wind": wind_names[int(t.game_wind)],
            "honba": int(t.honba),
            "kyoutaku": int(t.kyoutaku),
            "river_counter": int(t.river_counter),
            "dora": dora,
            "ura_dora": ura_dora,
            "players": players,
            "valid_actions": valid,
            "valid_actions_mask": self.get_valid_actions_mask(for_pid).tolist(),
            "riichi_stage2": self._riichi_stage2,
            "riichi_tile": self._may_riichi_tile_id,
            "is_over": self.is_over(),
            "result": result
        }

    def get_state(self, for_pid: int) -> dict:
        return self._build_state(for_pid)

    def get_public_state(self) -> dict:
        """Full state for all 4 players (used in AI battle spectator mode)."""
        return self._build_state(0)  # all hands visible

    def to_paipu(self) -> dict:
        """Export game as paipu JSON."""
        t = self._env.t
        gl = t.gamelog
        return {
            "init_yama": [int(y) for y in gl.init_yama],
            "init_scores": list(self.get_scores()),
            "oya": int(t.oya),
            "game_wind": int(t.game_wind),
            "honba": int(t.honba),
            "kyoutaku": int(t.kyoutaku),
            "result": {
                "type": str(t.result.result_type).split("::")[-1],
                "scores": list(t.result.score),
            } if self.is_over() else None,
            "action_log": self._env.action_log if hasattr(self._env, 'action_log') else []
        }


class GameManager:
    """Manages all active game sessions."""

    def __init__(self):
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    def create_session(self, mode: GameMode = GameMode.HUMAN_AI,
                       ai_model_path: Optional[str] = None,
                       seed: Optional[int] = None) -> GameSession:
        with self._lock:
            session_id = str(uuid.uuid4())
            env_wrapper = MahjongEnvWrapper(mode=mode, ai_model_path=ai_model_path, seed=seed)
            session = GameSession(
                session_id=session_id,
                mode=mode,
                env=env_wrapper,
                human_player_id=0 if mode == GameMode.HUMAN_AI else -1,
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[GameSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "session_id": sid,
                    "mode": s.mode.value,
                    "status": s.status,
                }
                for sid, s in self._sessions.items()
            ]

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

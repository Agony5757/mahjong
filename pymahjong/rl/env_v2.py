"""Modern Gymnasium environments using the tokenized encoding.

Two flavours are provided:

* :class:`TokenizedMahjongEnv` -- single-agent (POV = player 0). Compatible
  with stable-baselines3 / gymnasium APIs. Opponents are played by an
  injectable callable ``opponent_policy(obs_dict) -> action`` (or
  ``"random"``).

* :class:`TokenizedMultiAgentEnv` -- 4-player environment exposing one
  observation per acting player. Designed for self-play PPO training.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, Dict as DictSpace, Discrete

from .tokenization import (
    ACTION_DIM,
    MAX_SEQ_LEN,
    MahjongTokenizer,
    SCALAR_DIM,
    TOKEN_FEATURES,
    A_RIICHI,
    A_PASS_RIICHI,
)

try:  # pragma: no cover
    import MahjongPyWrapper as pm
except Exception:  # noqa: BLE001
    pm = None  # type: ignore


def _build_observation_space(max_seq_len: int = MAX_SEQ_LEN) -> DictSpace:
    return DictSpace(
        {
            "tokens": Box(
                low=0,
                high=255,
                shape=(max_seq_len, TOKEN_FEATURES),
                dtype=np.int32,
            ),
            "scalars": Box(
                low=-np.inf,
                high=np.inf,
                shape=(max_seq_len, SCALAR_DIM),
                dtype=np.float32,
            ),
            "attention_mask": Box(low=0, high=1, shape=(max_seq_len,), dtype=bool),
            "action_mask": Box(low=0, high=1, shape=(ACTION_DIM,), dtype=bool),
            "seq_len": Box(low=0, high=max_seq_len, shape=(), dtype=np.int32),
            "current_player": Box(low=0, high=3, shape=(), dtype=np.int32),
            "phase": Box(low=0, high=31, shape=(), dtype=np.int32),
        }
    )


# ---------------------------------------------------------------------------
# Action translation: 54-action discrete → engine selection index
# ---------------------------------------------------------------------------

def _resolve_action(env, action: int) -> int:
    """Translate a 54-action index into an engine ``make_selection`` index.

    For the engine, we re-use the existing ``get_selection_from_action_basetile``
    helper. ``MahjongEnv.step`` already implements the same translation, so
    we simply delegate to its underlying ``pm.Table`` via index search.
    """
    from pymahjong.env_pymahjong import MahjongEnv  # local import

    table = env._inner.t  # type: ignore[attr-defined]
    phase = table.get_phase()
    actions = table.get_self_actions() if phase < 4 else table.get_response_actions()

    BA = pm.BaseAction
    # Map our action id → (BaseAction, tile-spec or None)
    if 0 <= action < 34:
        target = (BA.Discard, [action], False)
    elif action in (MahjongEnv.CHILEFT, MahjongEnv.CHIMIDDLE, MahjongEnv.CHIRIGHT):
        target = (BA.Chi, None, False)
    elif action in (MahjongEnv.CHILEFT_USERED, MahjongEnv.CHIMIDDLE_USERED, MahjongEnv.CHIRIGHT_USERED):
        target = (BA.Chi, None, True)
    elif action == MahjongEnv.PON:
        target = (BA.Pon, None, False)
    elif action == MahjongEnv.PON_USERED:
        target = (BA.Pon, None, True)
    elif action == MahjongEnv.ANKAN:
        target = (BA.AnKan, None, False)
    elif action == MahjongEnv.MINKAN:
        target = (BA.Kan, None, False)
    elif action == MahjongEnv.KAKAN:
        target = (BA.KaKan, None, False)
    elif action == MahjongEnv.RIICHI:
        target = (BA.Riichi, None, False)
    elif action == MahjongEnv.RON:
        target = (BA.Ron, None, False)
    elif action == MahjongEnv.TSUMO:
        target = (BA.Tsumo, None, False)
    elif action == MahjongEnv.PUSH:
        target = (BA.Kyushukyuhai, None, False)
    elif action in (MahjongEnv.PASS_RIICHI, MahjongEnv.PASS_RESPONSE):
        target = (BA.Pass, None, False)
    else:
        raise ValueError(f"action {action} out of range")

    base_action, tile_basetiles, _ = target
    # Linear scan over engine-provided actions to find a matching candidate.
    for i, sel in enumerate(actions):
        if int(sel.action) != int(base_action):
            continue
        if tile_basetiles is None:
            return i
        tiles = sel.correspond_tiles
        if tiles and int(tiles[0].tile) == tile_basetiles[0]:
            return i
    raise ValueError(
        f"No engine selection matches action={action}, base={base_action}"
    )


# ---------------------------------------------------------------------------
# Single-agent env
# ---------------------------------------------------------------------------

class TokenizedMahjongEnv(gym.Env):
    """Single-agent gymnasium env using tokenized observations.

    Args:
        opponent_policy: callable ``policy(obs_dict) -> int`` or ``"random"``.
        oracle: include opponent-hand tokens in the observation
            (use only for offline training / oracle-guided learning).
        max_seq_len: max token sequence length.
        agent_seat: which seat (0..3) the learning agent occupies.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        opponent_policy: Any = "random",
        oracle: bool = False,
        max_seq_len: int = MAX_SEQ_LEN,
        agent_seat: int = 0,
    ):
        super().__init__()
        from pymahjong.env_pymahjong import MahjongEnv

        self._inner = MahjongEnv()
        self._tokenizer = MahjongTokenizer(max_seq_len=max_seq_len, include_oracle=oracle)
        self.observation_space = _build_observation_space(max_seq_len)
        self.action_space = Discrete(ACTION_DIM)

        self.opponent_policy = opponent_policy
        self.agent_seat = agent_seat
        self.max_seq_len = max_seq_len

    # ---- helpers ------------------------------------------------------------

    def _obs(self) -> Dict[str, Any]:
        seat = self._inner.get_curr_player_id()
        tok = self._tokenizer.encode(
            self._inner.t,
            current_player=seat,
            riichi_stage2=self._inner.riichi_stage2,
        )
        return tok.to_dict()

    def _opponent_act(self):
        seat = self._inner.get_curr_player_id()
        if self.opponent_policy == "random":
            valid = self._inner.get_valid_actions(nhot=False)
            action = int(np.random.choice(valid))
        else:
            action = int(self.opponent_policy(self._obs()))
        engine_idx = _resolve_action(self, action)
        # NOTE: MahjongEnv.step does its own riichi_stage2 bookkeeping; we
        # bypass it here because we already translated to the engine index.
        self._inner.t.make_selection(engine_idx)
        # Riichi stage handling (kept consistent with MahjongEnv.step):
        from pymahjong.env_pymahjong import MahjongEnv
        if action == MahjongEnv.RIICHI or action == MahjongEnv.PASS_RIICHI:
            self._inner.riichi_stage2 = False
        else:
            # If the engine just declared a riichi-eligible discard, the
            # next action will be RIICHI/PASS_RIICHI for the same player.
            ph = self._inner.t.get_phase()
            if ph < 4:
                acts = self._inner.t.get_self_actions()
                if any(int(a.action) == int(pm.BaseAction.Riichi) for a in acts):
                    self._inner.riichi_stage2 = True
                else:
                    self._inner.riichi_stage2 = False

    def _proceed_to_agent(self):
        while not self._inner.is_over() and self._inner.get_curr_player_id() != self.agent_seat:
            valid = self._inner.get_valid_actions(nhot=False)
            if len(valid) <= 1:
                # forced single-action move (e.g. forced pass) -- engine handles
                self._inner.step(self._inner.get_curr_player_id(), int(valid[0]))
            else:
                self._opponent_act()

    # ---- gym API ------------------------------------------------------------

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed, options=options)
        opts = options or {}
        self._inner.reset(
            oya=opts.get("oya"),
            game_wind=opts.get("game_wind"),
            seed=seed,
        )
        self._proceed_to_agent()
        if self._inner.is_over():
            return self.reset(seed=None)
        return self._obs(), {}

    def step(self, action: int):
        if self._inner.get_curr_player_id() != self.agent_seat:
            raise RuntimeError("Step called when it is not the agent's turn.")
        # Use the wrapped MahjongEnv.step so its riichi bookkeeping is preserved.
        self._inner.step(self.agent_seat, int(action))
        self._proceed_to_agent()
        terminated = self._inner.is_over()
        reward = 0.0
        if terminated:
            reward = float(self._inner.get_payoffs()[self.agent_seat]) / 25000.0
        truncated = False
        return self._obs() if not terminated else self._terminal_obs(), reward, terminated, truncated, {}

    def _terminal_obs(self) -> Dict[str, Any]:
        # Provide a dummy observation at terminal step.
        return {
            "tokens": np.zeros((self.max_seq_len, TOKEN_FEATURES), dtype=np.int32),
            "scalars": np.zeros((self.max_seq_len, SCALAR_DIM), dtype=np.float32),
            "attention_mask": np.zeros((self.max_seq_len,), dtype=bool),
            "action_mask": np.zeros((ACTION_DIM,), dtype=bool),
            "seq_len": np.int32(0),
            "current_player": np.int32(self.agent_seat),
            "phase": np.int32(16),
        }

    def render(self):
        self._inner.render()


# ---------------------------------------------------------------------------
# Multi-agent env (for self-play PPO)
# ---------------------------------------------------------------------------

class TokenizedMultiAgentEnv:
    """Lightweight 4-player multi-agent env (not a strict gym.Env).

    The :meth:`step` API takes a single action for the *current* acting
    player (returned by :attr:`current_player`). This matches the
    underlying engine's turn-based model and avoids bookkeeping for
    simultaneous moves.

    Use this with PPO self-play by collecting trajectories one player at a
    time and assigning the final ``payoffs[seat]`` reward to all
    transitions for that seat at episode end.
    """

    def __init__(
        self,
        oracle: bool = False,
        max_seq_len: int = MAX_SEQ_LEN,
    ):
        from pymahjong.env_pymahjong import MahjongEnv
        self._inner = MahjongEnv()
        self._tokenizer = MahjongTokenizer(max_seq_len=max_seq_len, include_oracle=oracle)
        self.action_space = Discrete(ACTION_DIM)
        self.observation_space = _build_observation_space(max_seq_len)
        self.max_seq_len = max_seq_len

    @property
    def current_player(self) -> int:
        return self._inner.get_curr_player_id()

    def is_over(self) -> bool:
        return self._inner.is_over()

    def reset(self, seed: Optional[int] = None, **kwargs):
        self._inner.reset(seed=seed, **kwargs)
        self._skip_forced()
        return self.observe()

    def _skip_forced(self):
        # Auto-advance through forced single-option steps (true single-choice).
        while not self._inner.is_over():
            valid = self._inner.get_valid_actions(nhot=False)
            if len(valid) > 1:
                break
            self._inner.step(self._inner.get_curr_player_id(), int(valid[0]))

    def observe(self) -> Dict[str, Any]:
        seat = self.current_player
        return self._tokenizer.encode(
            self._inner.t,
            current_player=seat,
            riichi_stage2=self._inner.riichi_stage2,
        ).to_dict()

    def step(self, action: int) -> Tuple[Dict[str, Any], np.ndarray, bool, dict]:
        seat = self.current_player
        self._inner.step(seat, int(action))
        self._skip_forced()
        done = self._inner.is_over()
        if done:
            payoffs = self._inner.get_payoffs() / 25000.0
        else:
            payoffs = np.zeros(4, dtype=np.float32)
        return (None if done else self.observe()), payoffs, done, {"acting_seat": seat}

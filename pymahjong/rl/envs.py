"""Encoding-agnostic Gymnasium environments for Mahjong.

These environments accept an ``encoding`` parameter (``"v1"``, ``"v2"``,
``"v3"``, ``"v4"``) and delegate observation encoding to the corresponding
:class:`~pymahjong.rl.encoding.EncodingStrategy`.

Both classes wrap the existing :class:`~pymahjong.env_pymahjong.MahjongEnv`
as the C++ engine interface; only the observation encoding layer differs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium.spaces import Discrete

from .action_space import ACTION_DIM, ActionEncoder
from .encoding import EncodingVersion, get_strategy
from . import encodings  # noqa: F401 -- ensures all strategies are registered

try:
    import MahjongPyWrapper as pm
except Exception:  # noqa: BLE001
    pm = None  # type: ignore


class EncodingMahjongEnv(gym.Env):
    """Single-agent Mahjong env with configurable observation encoding.

    Args:
        encoding: one of ``"v1"``, ``"v2"``, ``"v3"``, ``"v4"`` or an
            :class:`EncodingVersion` enum member.  Defaults to ``"v3"``.
        opponent_policy: callable ``policy(obs_dict) -> int`` or ``"random"``.
        oracle: include hidden information in the observation (encoding-dependent).
        agent_seat: which seat (0-3) the learning agent occupies.
        **kwargs: forwarded to the strategy's ``observation_space()`` call.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        encoding: str | EncodingVersion = "v3",
        opponent_policy: Any = "random",
        oracle: bool = False,
        agent_seat: int = 0,
        **kwargs,
    ):
        super().__init__()
        from pymahjong.env_pymahjong import MahjongEnv

        if isinstance(encoding, str):
            encoding = EncodingVersion(encoding)
        self._encoding = encoding
        self._strategy = get_strategy(encoding)
        self._inner = MahjongEnv()
        self._oracle = oracle
        self.opponent_policy = opponent_policy
        self.agent_seat = agent_seat

        self.observation_space = self._strategy.observation_space(**kwargs)
        self.action_space = Discrete(ACTION_DIM)

    # -- helpers ---------------------------------------------------------------

    def _obs(self) -> Dict[str, Any]:
        seat = self._inner.get_curr_player_id()
        return self._strategy.encode_observation(
            self._inner.t,
            current_player=seat,
            riichi_stage2=self._inner.riichi_stage2,
            include_oracle=self._oracle,
        )

    def _opponent_act(self):
        seat = self._inner.get_curr_player_id()
        if self.opponent_policy == "random":
            valid = self._inner.get_valid_actions(nhot=False)
            action = int(np.random.choice(valid))
        else:
            action = int(self.opponent_policy(self._obs()))
        engine_idx = ActionEncoder.unified_to_engine(self._inner.t, action)
        self._inner.t.make_selection(engine_idx)
        # Riichi stage handling
        if action in (ActionEncoder.A_RIICHI, ActionEncoder.A_PASS_RIICHI):
            self._inner.riichi_stage2 = False
        else:
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
                self._inner.step(self._inner.get_curr_player_id(), int(valid[0]))
            else:
                self._opponent_act()

    # -- gym API ---------------------------------------------------------------

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
        self._inner.step(self.agent_seat, int(action))
        self._proceed_to_agent()
        terminated = self._inner.is_over()
        reward = 0.0
        if terminated:
            reward = float(self._inner.get_payoffs()[self.agent_seat]) / 25000.0
        return self._obs() if not terminated else self._terminal_obs(), reward, terminated, False, {}

    def _terminal_obs(self) -> Dict[str, Any]:
        """Dummy observation at terminal step."""
        return self._strategy.encode_observation(
            self._inner.t, current_player=self.agent_seat, riichi_stage2=False,
        )

    def render(self):
        self._inner.render()


class EncodingMultiAgentEnv:
    """4-player self-play Mahjong env with configurable encoding.

    Args:
        encoding: one of ``"v1"``, ``"v2"``, ``"v3"``, ``"v4"`` or an
            :class:`EncodingVersion` enum member.  Defaults to ``"v3"``.
        **kwargs: forwarded to the strategy's ``observation_space()`` call.
    """

    def __init__(self, encoding: str | EncodingVersion = "v3", **kwargs):
        from pymahjong.env_pymahjong import MahjongEnv

        if isinstance(encoding, str):
            encoding = EncodingVersion(encoding)
        self._encoding = encoding
        self._strategy = get_strategy(encoding)
        self._inner = MahjongEnv()
        self.action_space = Discrete(ACTION_DIM)
        self.observation_space = self._strategy.observation_space(**kwargs)
        self.max_seq_len = kwargs.get("max_seq_len", 360)

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
        while not self._inner.is_over():
            valid = self._inner.get_valid_actions(nhot=False)
            if len(valid) > 1:
                break
            self._inner.step(self._inner.get_curr_player_id(), int(valid[0]))

    def observe(self) -> Dict[str, Any]:
        seat = self.current_player
        return self._strategy.encode_observation(
            self._inner.t,
            current_player=seat,
            riichi_stage2=self._inner.riichi_stage2,
        )

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

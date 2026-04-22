import gymnasium as gym
import numpy as np
import warnings
from gymnasium.spaces import Discrete, Box
import MahjongPyWrapper as pm

np.set_printoptions(threshold=np.inf)

class MahjongEnv(gym.Env):
    """Multi-agent Japanese Riichi Mahjong environment.

    A 4-player Mahjong environment where each player takes turns making
    decisions. At each step, exactly one player acts until the game ends.
    This environment is suitable for multi-agent reinforcement learning research.

    The environment uses a phase-based state machine: self-action phases
    (P1_ACTION through P4_ACTION) for discard/riichi/tsumo/kan decisions,
    and response phases (P1_RESPONSE through P4_RESPONSE) for chi/pon/ron
    responses. Use ``get_curr_player_id()`` to identify the acting player.

    Observation encoding:
        - Executor observation: 93x34 boolean matrix (visible game state)
        - Oracle observation: 18x34 boolean matrix (hidden info: opponents' hands)
        - Full observation: 111x34 (concatenation of both)

    Action space:
        54 discrete actions covering discard, chi, pon, kan, riichi,
        ron, tsumo, and pass decisions. Not all actions are valid at
        every step -- use ``get_valid_actions()`` to check.
    """

    PLAYER_OBS_DIM = 93
    """int: Number of channels in executor observation."""
    ORACLE_OBS_DIM = 18
    """int: Number of channels in oracle observation."""
    ACTION_DIM = 54
    """int: Total number of discrete actions."""
    MAHJONG_TILE_TYPES = 34
    """int: Number of distinct tile types in Mahjong (1-9m, 1-9p, 1-9s, 1-7z)."""
    INIT_POINTS = 25000
    """int: Initial points for each player."""

    # ACTION INDICES
    CHILEFT = 37
    CHIMIDDLE = 38
    CHIRIGHT = 39

    CHILEFT_USERED = 40
    CHIMIDDLE_USERED = 41
    CHIRIGHT_USERED = 42

    PON = 43
    PON_USERED = 44
    ANKAN = 45
    MINKAN = 46
    KAKAN = 47

    RIICHI = 48
    RON = 49
    TSUMO = 50
    PUSH = 51

    PASS_RIICHI = 52
    PASS_RESPONSE = 53

    # corresponding to self.t.get_phase()
    Phases = ("P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE",
              "P4_RESPONSE", "P1_抢杠RESPONSE", "P2_抢杠RESPONSE", "P3_抢杠RESPONSE", "P4_抢杠RESPONSE",
              "P1_抢暗杠RESPONSE", "P2_抢暗杠RESPONSE", " P3_抢暗杠RESPONSE", " P4_抢暗杠RESPONSE", "GAME_OVER",
              "P1_DRAW, P2_DRAW, P3_DRAW, P4_DRAW")

    # pymahjhong.BaseAction
    ACTION_TYPES = [pm.BaseAction.Discard] * (MAHJONG_TILE_TYPES + 3) + [pm.BaseAction.Chi] * 6 + [pm.BaseAction.Pon] * 2 \
                   + [pm.BaseAction.AnKan] + [pm.BaseAction.Kan] + [pm.BaseAction.KaKan] \
                   + [pm.BaseAction.Riichi] + [pm.BaseAction.Ron] + [pm.BaseAction.Tsumo] \
                   + [pm.BaseAction.Kyushukyuhai] + [pm.BaseAction.Pass] * 2

    def __init__(self):
        self.t = pm.Table()
        self.game_count = 0

        self.observation_space = Box(dtype=bool, low=0, high=1,
                                     shape=[self.PLAYER_OBS_DIM, self.MAHJONG_TILE_TYPES])
        self.oracle_observation_space = Box(dtype=bool, low=0, high=1,
                                            shape=[self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES])
        self.full_observation_space = Box(dtype=bool, low=0, high=1,
                                          shape=[self.PLAYER_OBS_DIM + self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES])

        self.action_space = Discrete(self.ACTION_DIM)

        self.obs_container = np.zeros([self.PLAYER_OBS_DIM + self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES], dtype=np.int8)
        self.act_container = np.zeros([self.ACTION_DIM], dtype=np.int8)

        self.use_red_dora = False

    def _check_player(self, player_id):
        if not player_id == self.t.who_make_selection():
            raise ValueError("You are trying to obtain information from a player who is not making decision !!!! \
                (current acting player ID is {}, you are trying to get information of player {}".format(
                    self.t.who_make_selection(), player_id))

    def _proceed(self):
        while not self.is_over():  # continue until game over or one player has choices
            phase = self.t.get_phase()
            if phase < 4:
                aval_actions = self.t.get_self_actions()
            elif phase < 16:
                aval_actions = self.t.get_response_actions()
            else:
                aval_actions = [-1]
            if len(aval_actions) > 1:
                break
            else:
                self.t.make_selection(0)

    def _get_num_aval_actions(self):

        phase = self.t.get_phase()

        if phase < 4:
            aval_actions = self.t.get_self_actions()
        elif phase < 16:
            aval_actions = self.t.get_response_actions()
        else:
            aval_actions = [-1]

        return len(aval_actions)

    def reset(
        self, *,
        oya=None,
        game_wind=None,
        scores=None,
        seed=None,
        kyoutaku=0,
        honba=0,
        debug_mode=None
    ):
        """Initialize a new game.

        Args:
            oya: Parent (dealer) player ID (0-3). Defaults to rotating by game count.
            game_wind: Initial game wind. One of ``"east"``, ``"south"``,
                ``"west"``, ``"north"``. Defaults to ``"east"``.
            scores: List of 4 integers for initial player scores.
                Defaults to ``[25000, 25000, 25000, 25000]``.
            seed: Random seed for tile shuffling. None for random shuffle.
            kyoutaku: Number of riichi deposit sticks on the table. Defaults to 0.
            honba: Number of repeat counters. Defaults to 0.
            debug_mode: Debug mode for the C++ engine (1 or 2). Generates
                replayable code for debugging.
        """
        if scores is None:
            scores = [25000, 25000, 25000, 25000]
        else:
            assert len(scores) == 4, "scores should be a list of length 4"

        assert isinstance(kyoutaku, int)
        assert isinstance(honba, int)

        if oya is None:
            oya = self.game_count % 4  # Each player alternatively be the "Oya" (parent)
        else:
            assert oya in [0, 1, 2, 3]

        if game_wind is None:
            game_wind = "east"
        else:
            assert game_wind in ["east", "south", "west", "north"]

        self.t = pm.Table()
        if seed is not None:
            self.t.seed = seed

        if debug_mode is not None:
            self.t.set_debug_mode(debug_mode)

        self.t.game_init_with_config(
            [],
            scores,
            kyoutaku,
            honba,
            ["east", "south", "west", "north"].index(game_wind),
            oya,
        )

        # self.t.game_init_with_metadata({"oya": str(oya), "wind": game_wind})
        self.riichi_stage2 = False
        self.may_riichi_tile_id = None
        self.game_count += 1

        self._proceed()

    def step(self, player_id: int, action: int):
        """Execute one action for the specified player.

        Riichi is a two-step action: first, the player discards a tile
        (which must be a valid riichi discard); then on the next call,
        choose between ``RIICHI`` or ``PASS_RIICHI``.

        Unlike standard gym environments, this method does not return
        observation/reward. Use ``get_obs()``, ``get_oracle_obs()``, and
        ``get_payoffs()`` to retrieve information.

        Args:
            player_id: ID of the player making the action (0-3). Must match
                ``get_curr_player_id()``.
            action: Action index from the 54 discrete actions. Must be in
                ``get_valid_actions()``.

        Raises:
            ValueError: If player_id is not the current acting player, or
                if the action is not valid at this step.
        """
        # self.use_red_dora = False

        if not player_id == self.get_curr_player_id():
            raise ValueError("current acting player ID is {}, but you are trying to ask player {} to act !!".format(
                self.get_curr_player_id(), player_id))

        if not self.riichi_stage2:
            self.act_container.fill(0)
            curr_pid = self.get_curr_player_id()
            pm.encv1_encode_action(self.t, curr_pid, self.act_container)  # no need zeros

            if self.act_container[action] == 0:
                raise ValueError("Not an action in available actions! (use get_valid_actions(player_id))")

            # ------- IF riichi is possible -------------
            # riichi is divided to 2 steps: first choosing a tile to discard, then decide if to riichi (if possible)
            if self.act_container[self.RIICHI]:
                riichi_tiles = pm.encv1_get_riichi_tiles(self.t)
                riichi_tiles_id = set()
                for riichi_tile in riichi_tiles:
                    riichi_tiles_id.add(int(riichi_tile))
                if action in riichi_tiles_id:
                    self.riichi_stage2 = True
                    self.may_riichi_tile_id = action

            # not involving riichi
            if not self.riichi_stage2:
                action_type = self.ACTION_TYPES[action]

                if action < self.MAHJONG_TILE_TYPES:
                    corresponding_tiles = [action]
                    self.use_red_dora = False
                elif action == 34: # red 5m
                    corresponding_tiles = [4]
                    self.use_red_dora = True
                elif action == 35: # red 5p
                    corresponding_tiles = [13]
                    self.use_red_dora = True
                elif action == 36: # red 5s
                    corresponding_tiles = [22]
                    self.use_red_dora = True

                elif action in (self.CHILEFT, self.CHILEFT_USERED, self.CHIMIDDLE, self.CHIMIDDLE_USERED, self.CHIRIGHT, self.CHIRIGHT_USERED):
                    chi_tile_id = int(self.t.get_selected_action_tile().tile)
                    if action == self.CHILEFT:
                        corresponding_tiles = [chi_tile_id + 1, chi_tile_id + 2]
                        self.use_red_dora = False
                    elif action == self.CHIMIDDLE:
                        corresponding_tiles = [chi_tile_id - 1, chi_tile_id + 1]
                        self.use_red_dora = False
                    elif action == self.CHIRIGHT:
                        corresponding_tiles = [chi_tile_id - 2, chi_tile_id - 1]
                        self.use_red_dora = False
                    if action == self.CHILEFT_USERED:
                        corresponding_tiles = [chi_tile_id + 1, chi_tile_id + 2]
                        self.use_red_dora = True
                    elif action == self.CHIMIDDLE_USERED:
                        corresponding_tiles = [chi_tile_id - 1, chi_tile_id + 1]
                        self.use_red_dora = True
                    elif action == self.CHIRIGHT_USERED:
                        corresponding_tiles = [chi_tile_id - 2, chi_tile_id - 1]
                        self.use_red_dora = True

                elif action == self.PON:
                    pon_tile_id = int(self.t.get_selected_action_tile().tile)
                    corresponding_tiles = [pon_tile_id, pon_tile_id]
                    self.use_red_dora = False

                elif action == self.PON_USERED:
                    pon_tile_id = int(self.t.get_selected_action_tile().tile)
                    corresponding_tiles = [pon_tile_id, pon_tile_id]
                    self.use_red_dora = True

                elif action == self.MINKAN:
                    kan_tile_id = int(self.t.get_selected_action_tile().tile)
                    corresponding_tiles = [kan_tile_id] * 3

                elif action == self.ANKAN:
                    if self.t.players[player_id].double_riichi or self.t.players[player_id].riichi:
                        # If has riichi, the player can only ANKAN the latest drawed tile
                        kan_tile_id = int(self.t.players[player_id].hand[-1].tile)
                    else:

                        # Here we have an approximation, it a player has multiple options to KaKan or AnKan,
                        # the player will random select one if action == ANKAN or KAKAN
                        # However, this case should be very rare in normal play
                        kan_tile_id = np.random.choice(np.argwhere(self.get_obs(curr_pid)[3]).flatten())

                    corresponding_tiles = [kan_tile_id] * 4

                elif action == self.KAKAN:
                    obs = self.get_obs(curr_pid)
                    kan_tile_id = np.random.choice(
                        np.argwhere((np.sum(obs[:4], axis=0) == 1) * (np.sum(obs[6:10], axis=0) == 3)).flatten())
                    corresponding_tiles = [kan_tile_id]

                elif action == self.RON:
                    # include Chan-Kan, Chan-An-Kan
                    corresponding_tiles = []

                elif action in (self.TSUMO, self.PUSH, self.PASS_RESPONSE):
                    corresponding_tiles = []

                else:
                    raise SystemError("This should not happen, please report to the authors")

                try:
                    if action == self.RON:  # normal ron-agari, chan-kan or chan-an-kan
                        for ron_type in [pm.BaseAction.Ron, pm.BaseAction.ChanKan, pm.BaseAction.ChanAnKan]:
                            try:
                                self.t.make_selection_from_action_basetile(
                                    ron_type, corresponding_tiles, self.use_red_dora)
                            except:
                                pass
                    else:
                        try:
                            self.t.make_selection_from_action_basetile(
                                action_type, corresponding_tiles, self.use_red_dora)
                        except:
                            # If riichi and ANKAN the latest drawed tile failed
                            self.t.make_selection_from_action_basetile(
                                pm.BaseAction.Discard, [int(self.t.players[player_id].hand[-1].tile)], self.t.players[player_id].hand[-1].red_dora)

                except Exception as inst:
                    print("-------------- execption in make_selection_from_action_basetile ------------------")
                    print(inst)
                    print(action_type, corresponding_tiles)
                    obs = self.get_obs(curr_pid)
                    print(obs.astype(int))
                    self.render()
                    raise SystemError

        else:  # riichi step 2
            assert action in (self.RIICHI, self.PASS_RIICHI)
            if action == self.RIICHI:
                action_type = pm.BaseAction.Riichi
            else:
                action_type = pm.BaseAction.Discard

            self.t.make_selection_from_action_basetile(action_type, [self.may_riichi_tile_id], self.use_red_dora)
            self.riichi_stage2 = False
            self.may_riichi_tile_id = None

        self._proceed()

    def _get_obs_from_table(self, player_id):
        self.obs_container.fill(0)  # passing zeros array to C++
        pm.encv1_encode_table(self.t, player_id, True, self.obs_container)
        if self.riichi_stage2:
            pm.encv1_encode_table_riichi_step2(self.t, self.may_riichi_tile_id, self.obs_container)

    def get_obs(self, player_id: int):
        """Get executor observation for the specified player.

        The executor observation is a 93x34 boolean matrix encoding the
        visible game state from the player's perspective, including their
        own hand, discards, called tiles, dora indicators, and scores.

        Args:
            player_id: Player ID (0-3). Must be the current acting player.

        Returns:
            np.ndarray: Boolean array of shape (93, 34).

        Raises:
            ValueError: If player_id is not the current acting player.
        """
        self._check_player(player_id)
        self._get_obs_from_table(player_id)
        return self.obs_container[:self.PLAYER_OBS_DIM].astype(bool)

    def get_oracle_obs(self, player_id: int):
        """Get oracle observation for the specified player.

        The oracle observation is an 18x34 boolean matrix encoding hidden
        information -- the tiles in other players' hands. This is useful
        for oracle-guided learning research.

        Args:
            player_id: Player ID (0-3). Must be the current acting player.

        Returns:
            np.ndarray: Boolean array of shape (18, 34).

        Raises:
            ValueError: If player_id is not the current acting player.
        """
        self._check_player(player_id)
        self._get_obs_from_table(player_id)
        return self.obs_container[-self.ORACLE_OBS_DIM:].astype(bool)

    def get_full_obs(self, player_id: int):
        """Get full observation (executor + oracle) for the specified player.

        The full observation is a 111x34 boolean matrix formed by
        concatenating the executor and oracle observations.

        Args:
            player_id: Player ID (0-3). Must be the current acting player.

        Returns:
            np.ndarray: Boolean array of shape (111, 34).

        Raises:
            ValueError: If player_id is not the current acting player.
        """
        self._check_player(player_id)
        self._get_obs_from_table(player_id)
        return self.obs_container.copy().astype(bool)

    def get_valid_actions(self, nhot=False):
        """Get valid action indices at the current step.

        During riichi step 2 (after discarding a valid riichi tile),
        only ``RIICHI`` and ``PASS_RIICHI`` are valid.

        Args:
            nhot: If True, return a one-hot boolean array of shape (54,)
                where valid actions are True. If False, return an array
                of valid action indices.

        Returns:
            np.ndarray: Either a boolean array of shape (54,) if nhot is True,
                or an integer array of valid action indices if nhot is False.
        """
        if not self.riichi_stage2:
            self.act_container.fill(0)
            pm.encv1_encode_action(self.t, self.get_curr_player_id(), self.act_container)
            act_container = self.act_container.copy().astype(bool)
            act_container[self.RIICHI] = 0
            act_container[self.PASS_RIICHI] = 0
        else:
            act_container = np.zeros([self.ACTION_DIM], dtype=bool)
            act_container[self.RIICHI] = 1
            act_container[self.PASS_RIICHI] = 1

        if nhot:
            return act_container
        else:
            return np.argwhere(act_container).reshape([-1])

    def get_payoffs(self):
        """Get the payoff for each player relative to the initial points.

        Payoff is calculated as ``final_score - INIT_POINTS`` for each player.

        Returns:
            np.ndarray: Float32 array of shape (4,) with payoffs for players 0-3.
        """
        payoffs = np.zeros([4], dtype=np.float32)
        for i in range(4):
            payoffs[i] = self.t.get_result().score[i] - self.INIT_POINTS
        return payoffs

    def is_over(self):
        """Check whether the current game has ended.

        Returns:
            bool: True if the game is over (GAME_OVER phase).
        """
        return self.Phases[self.t.get_phase()] == "GAME_OVER"

    def get_curr_player_id(self):
        """Get the ID of the player who should act next.

        Returns:
            int: Player ID (0-3), or -1 if the game is over.
        """
        if self.t.get_phase() < 16:
            return self.t.who_make_selection()
        elif self.t.get_phase() == 16:
            warnings.warn("This game has ended, get_curr_player_id return -1 !!")
            return -1
        else:
            raise SystemError

    def render(self, mode='human'):
        """Print the current game state for all players.

        Shows each player's hand, river, and status information.
        """
        print("----------- current player: {} -----------------".format(self.get_curr_player_id()))
        print("[Player 0]")
        print(self.t.players[0].to_string())
        print("[Player 1]")
        print(self.t.players[1].to_string())
        print("[Player 2]")
        print(self.t.players[2].to_string())
        print("[Player 3]")
        print(self.t.players[3].to_string())


class SingleAgentMahjongEnv(gym.Env):
    """Single-agent Japanese Riichi Mahjong environment (Gymnasium-compatible).

    The agent controls player 0 and plays against 3 opponents. The opponents
    can be either random agents or pretrained VLOG models.

    This environment follows the standard Gymnasium API: call ``reset()`` to
    start a new episode, then repeatedly call ``step(action)`` until the
    episode terminates. Only the agent's decision steps are exposed; opponent
    turns are handled automatically.

    Observation encoding:
        Same as :class:`MahjongEnv` -- 93x34 executor, 18x34 oracle,
        111x34 full observation.

    Action space:
        54 discrete actions. Use ``get_valid_actions()`` to check which
        actions are valid at each step.

    Args:
        opponent_agent: Either ``"random"`` for random opponents, or a path
            to a pretrained model file (.pth). Available models:
            ``mahjong_VLOG_CQL.pth`` (CQL) and ``mahjong_VLOG_BC.pth`` (BC).
            Download from `GitHub releases
            <https://github.com/Agony5757/mahjong/releases/tag/v1.0.2>`_.
    """

    THIS_AGENT_ID = 0
    # The agent is the player 0 in MahjongEnv (while Oya may be others)

    def __init__(self, opponent_agent="random"):

        super(SingleAgentMahjongEnv, self).__init__()

        if opponent_agent == "random":
            self.opponent_agent = "random"
        else:
            try:
                import torch
                from .models import VLOGMahjong
                state_dict = torch.load(opponent_agent, map_location="cpu")
                if "f_s2q.network_modules.0.weight" in state_dict:
                    alg = "ddqn"
                elif "f_s2pi0.network_modules.0.weight" in state_dict:
                    alg = "bc"
                else:
                    raise Exception("Unknown model")
                self.opponent_agent = VLOGMahjong(algorithm=alg)

                keys = list(state_dict.keys())
                for key in keys:
                    if key not in list(self.opponent_agent.state_dict().keys()):
                        state_dict.pop(key)
                self.opponent_agent.load_state_dict(state_dict)

                if torch.cuda.is_available():
                    device = torch.device("cuda")
                    self.opponent_agent.device = device
                    self.opponent_agent.to(device=device)
                    print("----- CUDA detected, using CUDA for inference. -----")

                self.opponent_agent.eval()  # not necessary now, but remained for future

            except Exception as e:
                print(e)
                raise FileNotFoundError("opponent_agent should be 'random' or the path of a pre-trained model (You can download the pre-trained model from pymahjong github release: https://github.com/Agony5757/mahjong/releases ")

        self.env = MahjongEnv()

        self.observation_space = self.env.observation_space
        self.oracle_observation_space = self.env.oracle_observation_space
        self.full_observation_space = self.env.full_observation_space
        self.action_space = self.env.action_space

    def _proceed_until_agent_turn(self):
        while (not self.env.is_over()) and self.env.get_curr_player_id() != self.THIS_AGENT_ID:
            if self.opponent_agent == "random":
                aval_actions = self.env.get_valid_actions(nhot=False)
                self.env.step(self.env.get_curr_player_id(), np.random.choice(aval_actions))
            else:
                action_mask =  self.env.get_valid_actions(nhot=True)
                obs = self.env.get_obs(self.env.get_curr_player_id())
                action = self.opponent_agent.select(obs, action_mask=action_mask, greedy=True)
                self.env.step(self.env.get_curr_player_id(), action)

    def reset(self, *, oya=None, game_wind=None, seed=None, options=None):
        """Reset the environment and start a new game.

        Automatically advances past opponent turns until it is the agent's
        turn. If the game ends before the agent gets a turn (rare edge case),
        a new game is started automatically.

        Args:
            oya: Parent (dealer) player ID (0-3). Defaults to rotating.
            game_wind: Initial game wind (``"east"``, ``"south"``,
                ``"west"``, ``"north"``). Defaults to ``"east"``.
            seed: Random seed for tile shuffling.
            options: Additional options (unused, for Gymnasium compatibility).

        Returns:
            tuple[np.ndarray, dict]: Executor observation of shape (93, 34)
                and an empty info dict.
        """
        super().reset(seed=seed, options=options)
        self.env.reset(oya=oya, game_wind=game_wind, seed=seed)
        self._proceed_until_agent_turn()

        if self.env.is_over():
            # if espisode length == 0 for the current player, ignore this game and re-start a new game
            return self.reset()
        else:
            return self.get_obs(), {}

    def step(self, action):
        """Execute one action for the agent (player 0).

        After the agent acts, opponent turns are automatically processed
        until the agent's next turn or the game ends.

        Args:
            action: Action index (0-53). Must be in ``get_valid_actions()``.

        Returns:
            tuple[np.ndarray, float, bool, bool, dict]:
                - observation: Executor observation of shape (93, 34)
                - reward: Payoff relative to initial points (0 during game,
                  final payoff when game ends)
                - terminated: True if the game is over
                - truncated: Always False
                - info: Empty dict
        """
        assert self.env.get_curr_player_id() == self.THIS_AGENT_ID

        self.env.step(0, action)
        self._proceed_until_agent_turn()

        if self.env.is_over():
            r = self.env.get_payoffs()[self.THIS_AGENT_ID]
            terminated = True
        else:
            r = 0
            terminated = False

        return self.env.get_obs(self.THIS_AGENT_ID), r, terminated, False, {}

    def get_obs(self):
        """Get executor observation for the agent.

        Returns:
            np.ndarray: Boolean array of shape (93, 34).
        """
        return self.env.get_obs(self.THIS_AGENT_ID)

    def get_oracle_obs(self):
        """Get oracle observation for the agent.

        Returns:
            np.ndarray: Boolean array of shape (18, 34).
        """
        return self.env.get_oracle_obs(self.THIS_AGENT_ID)

    def get_full_obs(self):
        """Get full observation (executor + oracle) for the agent.

        Returns:
            np.ndarray: Boolean array of shape (111, 34).
        """
        return self.env.get_full_obs(self.THIS_AGENT_ID)

    def get_valid_actions(self):
        """Get valid action indices at the current step.

        Returns:
            np.ndarray: Integer array of valid action indices.
        """
        return self.env.get_valid_actions(nhot=False)

    def render(self, mode='human'):
        """Print the current game state for all players."""
        print("-----------------------------------")
        print("[Player 0 (this agent)]")
        print(self.env.t.players[0].to_string())
        print("[Player 1 (the first opponent counterclockwise)]")
        print(self.env.t.players[1].to_string())
        print("[Player 2 (the second opponent counterclockwise)]")
        print(self.env.t.players[2].to_string())
        print("[Player 3 (the third opponent counterclockwise)]")
        print(self.env.t.players[3].to_string())

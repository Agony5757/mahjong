import gym
import numpy as np
import warnings
from gym.spaces import Discrete, Box
import MahjongPyWrapper as pm

try:
    import torch
except:
    pass

np.set_printoptions(threshold=np.inf)


class MahjongEnv(gym.Env):

    PLAYER_OBS_DIM = 93
    ORACLE_OBS_DIM = 18
    ACTION_DIM = 47
    MAHJONG_TILE_TYPES = 34
    INIT_POINTS = 25000

    # ACTION INDICES
    CHILEFT = 34
    CHIMIDDLE = 35
    CHIRIGHT = 36
    PON = 37
    ANKAN = 38
    MINKAN = 39
    KAKAN = 40

    RIICHI = 41
    RON = 42
    TSUMO = 43
    PUSH = 44

    PASS_RESPONSE = 45
    PASS_RIICHI = 46

    # corresponding to self.t.get_phase()
    Phases = ("P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE",
              "P4_RESPONSE", "P1_抢杠RESPONSE", "P2_抢杠RESPONSE", "P3_抢杠RESPONSE", "P4_抢杠RESPONSE",
              "P1_抢暗杠RESPONSE", "P2_抢暗杠RESPONSE", " P3_抢暗杠RESPONSE", " P4_抢暗杠RESPONSE", "GAME_OVER",
              "P1_DRAW, P2_DRAW, P3_DRAW, P4_DRAW")

    # pymahjhong.BaseAction
    ACTION_TYPES = [pm.BaseAction.Play] * MAHJONG_TILE_TYPES + [pm.BaseAction.Chi] * 3 + [pm.BaseAction.Pon] \
                   + [pm.BaseAction.AnKan] + [pm.BaseAction.Kan] + [pm.BaseAction.KaKan] \
                   + [pm.BaseAction.Riichi] + [pm.BaseAction.Ron] + [pm.BaseAction.Tsumo] \
                   + [pm.BaseAction.KyuShuKyuHai] + [pm.BaseAction.Pass] * 2

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

    def reset(self, oya=None, game_wind=None, seed=None):
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

        self.t.game_init_with_metadata({"oya": str(oya), "wind": game_wind})
        self.riichi_stage2 = False
        self.may_riichi_tile_id = None

        self.game_count += 1

        self._proceed()

    def step(self, player_id: int, action: int):
        # Different from single-agent gym env, one should not get the information needed here,
        # because the next player to act may be different from the current player.
        # Instead, one should get the information need as follows:
        # Use .is_over() to know whether this game has finished
        # Use get_obs(player_id) or get_full_obs(player_id) or get_oracle_obs(player_id) to get observation
        # For rewards, after the game is over, one may use .get_payoffs

        if not player_id == self.get_curr_player_id():
            raise ValueError("current acting player ID is {}, but you are trying to ask player {} to act !!".format(
                self.get_curr_player_id(), player_id))

        if not self.riichi_stage2:
            self.act_container.fill(0)
            curr_pid = self.get_curr_player_id()
            pm.encode_action(self.t, curr_pid, self.act_container)  # no need zeros

            if self.act_container[action] == 0:
                raise ValueError("Not an action in available actions! (use get_valid_actions(player_id))")

            # ------- IF riichi is possible -------------
            # riichi is divided to 2 steps: first choosing a tile to discard, then decide if to riichi (if possible)
            if self.act_container[self.RIICHI]:
                riichi_tiles = pm.get_riichi_tiles(self.t)
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

                elif action in (self.CHILEFT, self.CHIMIDDLE, self.CHIRIGHT):
                    chi_tile_id = int(self.t.get_selected_action_tile().tile)
                    if action == self.CHILEFT:
                        corresponding_tiles = [chi_tile_id + 1, chi_tile_id + 2]
                    elif action == self.CHIMIDDLE:
                        corresponding_tiles = [chi_tile_id - 1, chi_tile_id + 1]
                    elif action == self.CHIRIGHT:
                        corresponding_tiles = [chi_tile_id - 2, chi_tile_id - 1]

                elif action == self.PON:
                    pon_tile_id = int(self.t.get_selected_action_tile().tile)
                    corresponding_tiles = [pon_tile_id, pon_tile_id]

                elif action == self.MINKAN:
                    kan_tile_id = int(self.t.get_selected_action_tile().tile)
                    corresponding_tiles = [kan_tile_id] * 3

                # Here we have an approximation, it a player has multiple options to KaKan or AnKan,
                # the player will random select one if action == ANKAN or KAKAN
                # However, this case should be very rare in normal play

                elif action == self.ANKAN:
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
                                    ron_type, corresponding_tiles, action >= self.MAHJONG_TILE_TYPES)
                            except:
                                pass
                    else:
                        self.t.make_selection_from_action_basetile(
                            action_type, corresponding_tiles, action >= self.MAHJONG_TILE_TYPES)

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
                action_type = pm.BaseAction.Play

            self.t.make_selection_from_action_basetile(action_type, [self.may_riichi_tile_id], False)
            self.riichi_stage2 = False
            self.may_riichi_tile_id = None

        self._proceed()

    def _get_obs_from_table(self, player_id):
        self.obs_container.fill(0)  # passing zeros array to C++
        pm.encode_table(self.t, player_id, True, self.obs_container)
        if self.riichi_stage2:
            pm.encode_table_riichi_step2(self.t, self.may_riichi_tile_id, self.obs_container)

    def get_obs(self, player_id: int):
        self._check_player(player_id)
        self._get_obs_from_table(player_id)
        return self.obs_container[:self.PLAYER_OBS_DIM].astype(bool)

    def get_oracle_obs(self, player_id: int):
        self._check_player(player_id)
        self._get_obs_from_table(player_id)
        return self.obs_container[-self.ORACLE_OBS_DIM:].astype(bool)

    def get_full_obs(self, player_id: int):
        self._check_player(player_id)
        self._get_obs_from_table(player_id)
        return self.obs_container.copy().astype(bool)

    def get_valid_actions(self, nhot=False):
        if not self.riichi_stage2:
            self.act_container.fill(0)
            pm.encode_action(self.t, self.get_curr_player_id(), self.act_container)
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
        payoffs = np.zeros([4], dtype=np.float32)
        for i in range(4):
            payoffs[i] = self.t.get_result().score[i] - self.INIT_POINTS
        return payoffs

    def is_over(self):
        return self.Phases[self.t.get_phase()] == "GAME_OVER"

    def get_curr_player_id(self):
        if self.t.get_phase() < 16:
            return self.t.who_make_selection()
        elif self.t.get_phase() == 16:
            warnings.warn("This game has ended, get_curr_player_id return -1 !!")
            return -1
        else:
            raise SystemError

    def render(self, mode='human'):
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
    THIS_AGENT_ID = 0
    # The agent is the player 0 in MahjongEnv (while Oya may be others)

    def __init__(self, opponent_agent="random"):

        super(SingleAgentMahjongEnv, self).__init__()

        assert opponent_agent in ["random", "vlog-bc", "vlog-cql"]

        if not torch.cuda.is_available():
            device = torch.device("cpu")
        else:
            device = torch.device("cuda")

        if opponent_agent =="vlog-cql":
            self.opponent_agent = torch.load("mahjong_VLOG_CQL.model", map_location=device)
            self.opponent_agent.device = device
        elif opponent_agent == "vlog-bc":
            self.opponent_agent = torch.load("mahjong_VLOG_BC.model", map_location=device)
            self.opponent_agent.device = device
        else:
            self.opponent_agent = "random"

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

    def reset(self, oya=None, game_wind=None, seed=None):
        self.env.reset(oya=oya, game_wind=game_wind, seed=seed)
        self._proceed_until_agent_turn()

        if self.env.is_over():
            # if espisode length == 0 for the current player, ignore this game and re-start a new game
            return self.reset()
        else:
            return self.get_obs()

    def step(self, action):
        assert self.env.get_curr_player_id() == self.THIS_AGENT_ID

        self.env.step(0, action)
        self._proceed_until_agent_turn()

        if self.env.is_over():
            r = self.env.get_payoffs()[self.THIS_AGENT_ID]
            done = True
        else:
            r = 0
            done = False

        return self.env.get_obs(self.THIS_AGENT_ID), r, done, {}

    def get_obs(self):
        return self.env.get_obs(self.THIS_AGENT_ID)

    def get_oracle_obs(self):
        return self.env.get_oracle_obs(self.THIS_AGENT_ID)

    def get_full_obs(self):
        return self.env.get_full_obs(self.THIS_AGENT_ID)

    def get_valid_actions(self):
        return self.env.get_valid_actions(nhot=False)

    def render(self, mode='human'):
        print("-----------------------------------")
        print("[Player 0 (this agent)]")
        print(self.env.t.players[0].to_string())
        print("[Player 1 (the first opponent counterclockwise)]")
        print(self.env.t.players[1].to_string())
        print("[Player 2 (the second opponent counterclockwise)]")
        print(self.env.t.players[2].to_string())
        print("[Player 3 (the third opponent counterclockwise)]")
        print(self.env.t.players[3].to_string())




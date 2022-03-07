import gym
import numpy as np
import pymahjong as pm
import warnings
from copy import deepcopy
from gym.spaces import Discrete, Box

class MahjongEnv(gym.Env):

    PLAYER_OBS_DIM = 93
    ORACLE_OBS_DIM = 18
    ACTION_DIM = 37
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

    Phases = ("P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE",
              "P4_RESPONSE", "P1_抢杠RESPONSE", "P2_抢杠RESPONSE", "P3_抢杠RESPONSE", "P4_抢杠RESPONSE",
              "P1_抢暗杠RESPONSE", "P2_抢暗杠RESPONSE", " P3_抢暗杠RESPONSE", " P4_抢暗杠RESPONSE", "GAME_OVER",
              "P1_DRAW, P2_DRAW, P3_DRAW, P4_DRAW")

    def __init__(self, printing=True, reward_unit=100):
        self.t = pm.Table()
        self.game_count = 0

        self.observation_space = Box(low=0, high=1, shape=[self.PLAYER_OBS_DIM, self.MAHJONG_TILE_TYPES])
        self.full_observation_space = Box(low=0, high=1, shape=[self.PLAYER_OBS_DIM + self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES])
        self.oracle_observation_space = Box(low=0, high=1, shape=[self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES])

        self.action_space = Discrete(47)

        self.obs_container = np.zeros([self.PLAYER_OBS_DIM + self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES], dtype=np.int8)
        self.act_container = np.zeros([self.ACTION_DIM], dtype=np.int8)

    def _check_player(self, player_id):
        if not player_id == self.t.who_make_selection():
            raise ValueError("You are trying to obtain information from a player who is not making decision !!!! \
                (current player ID is {}, you are trying to get information of player {}".format(
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

    def reset(self, oya=None, game_wind=None):
        if oya is None:
            oya = self.game_count % 4  # Each player alternatively be the "Oya" (parent)
        else:
            assert oya in [0, 1, 2, 3]

        if game_wind is None:
            game_wind = "east"
        else:
            assert game_wind in ["east", "south", "west", "north"]

        self.t = pm.Table()
        self.t.game_init_with_metadata({"oya": str(oya), "wind": game_wind})

        self.game_count += 1

        self._proceed()

    def step(self, action: int):
        # Different from single-agent gym env, one should not get the information needed here,
        # because the next player to act may be different from the current player.
        # Instead, one should get the information need as follows:
        # Use .is_over() to know whether this game has finished
        # Use get_obs(player_id) or get_full_obs(player_id) or get_oracle_obs(player_id) to get observation
        # For rewards, after the game is over, one may use .get_payoffs

        pm.encode_action(self.t, self.get_curr_player_id(), self.act_container)  # no need zeros

        if self.act_container[action] == 0:
            raise ValueError("Not an action in available actions! (use get_valid_actions(player_id))")

        # action_no = TODO
        # TODO: !!!!!!!!!!!!!!
        # print(np.count_nonzero(self.act_container))
        self.t.make_selection(np.random.randint(2))

        self._proceed()

    def step_riichi_stage2(self):
        pass


    def get_obs(self, player_id: int):
        self._check_player(player_id)
        self.obs_container = self.obs_container - self.obs_container  # passing zeros array to C++
        pm.encode_table(self.t, player_id, True, self.obs_container)
        return self.obs_container[:self.PLAYER_OBS_DIM]

    def get_oracle_obs(self, player_id: int):
        self._check_player(player_id)
        self.obs_container = self.obs_container - self.obs_container  # passing zeros array to C++
        pm.encode_table(self.t, player_id, True, self.obs_container)
        return self.obs_container[-self.ORACLE_OBS_DIM:]

    def get_full_obs(self, player_id: int):
        self._check_player(player_id)
        self.obs_container = self.obs_container - self.obs_container  # passing zeros array to C++
        pm.encode_table(self.t, player_id, True, self.obs_container)
        return deepcopy(self.obs_container)

    def get_valid_actions(self, player_id: int, nhot=True):
        self._check_player(player_id)
        pm.encode_action(self.t, player_id, self.act_container)  # no need zeros
        if nhot:
            return deepcopy(self.act_container)
        else:
            return np.argwhere(self.act_container).reshape([-1])

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
        raise NotImplementedError

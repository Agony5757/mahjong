import numpy as np
from copy import deepcopy
import gym
import MahjongPy as mp


class EnvMahjong2(gym.Env):
    """
    Mahjong Environment for FrOst Ver2
    """

    metadata = {'name': 'Mahjong', 'render.modes': ['human', 'rgb_array'], 'video.frames_per_second': 50}
    spec = {'id': 'TaskT'}

    def __init__(self, printing=True):
        self.t = mp.Table()
        self.Phases = (
            "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE",
            "P4_RESPONSE", "P1_抢杠RESPONSE", "P2_抢杠RESPONSE", "P3_抢杠RESPONSE", "P4_抢杠RESPONSE",
            "P1_抢暗杠RESPONSE", "P2_抢暗杠RESPONSE", " P3_抢暗杠RESPONSE", " P4_抢暗杠RESPONSE", "GAME_OVER",
            "P1_DRAW, P2_DRAW, P3_DRAW, P4_DRAW")
        self.horas = [False, False, False, False]
        self.played_a_tile = [False, False, False, False]
        self.tile_in_air = None
        self.final_score_changes = []
        self.game_count = 0
        self.printing = printing

        self.matrix_feature_size = [34, 58]
        self.vector_feature_size = 29

        self.scores_init = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_init[i] = self.t.players[i].score

        self.scores_before = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_before[i] = self.t.players[i].score

    def reset(self):
        self.t = mp.Table()
        self.t.game_init()
        self.game_count += 1

        self.horas = [False, False, False, False]
        self.played_a_tile = [False, False, False, False]

        self.scores_init = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_init[i] = self.t.players[i].score

        self.scores_before = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_before[i] = self.t.players[i].score

        return [self.get_state_(i) for i in range(4)]

    def get_phase_text(self):
        return self.Phases[self.t.get_phase()]

    # def step_draw(self, playerNo):
    #     current_playerNo = self.t.who_make_selection()
    #
    #     if not self.t.get_phase() < 4:
    #         raise Exception("Current phase is not draw phase!!")
    #     if not current_playerNo == playerNo:
    #         raise Exception("Current player is not the one neesd to execute action!!")
    #
    #     info = {"playerNo": playerNo}
    #     score_before = self.t.players[playerNo].score
    #
    #     self.played_a_tile[playerNo] = False
    #     new_state = self.get_state_(playerNo)
    #
    #     # the following should be unnecessary but OK
    #     if self.Phases[self.t.get_phase()] == "GAME_OVER":
    #         reward = self.get_final_score_change()[playerNo]
    #     else:
    #         reward = self.t.players[playerNo].score - score_before
    #
    #     if self.Phases[self.t.get_phase()] == "GAME_OVER":
    #         done = 1
    #         self.final_score_changes.append(self.get_final_score_change())
    #     else:
    #         done = 0
    #
    #     for i in range(4):
    #         self.scores_before[i] = self.t.players[i].score
    #
    #     return new_state, reward, done, info

    def step_play(self, action, playerNo):
        # self action phase
        current_playerNo = self.t.who_make_selection()

        if not self.t.get_phase() < 4:
            raise Exception("Current phase is not self-action phase!!")
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one neesd to execute action!!")

        info = {"playerNo": playerNo}
        score_before = self.t.players[playerNo].score

        aval_actions = self.t.get_self_actions()
        if aval_actions[action].action == mp.Action.Tsumo or aval_actions[action].action == mp.Action.KyuShuKyuHai:
            self.horas[playerNo] = True

        self.t.make_selection(action)

        if self.t.get_selected_action() == mp.Action.Play:
            self.played_a_tile[playerNo] = True

        new_state = self.get_state_(playerNo)

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            reward = self.get_final_score_change()[playerNo]
        else:
            reward = self.t.players[playerNo].score - score_before

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            done = 1
            self.final_score_changes.append(self.get_final_score_change())

        else:
            done = 0

        for i in range(4):
            self.scores_before[i] = self.t.players[i].score

        return new_state, reward, done, info

    def step_response(self, action:int, playerNo:int):
        # response phase

        current_playerNo = self.t.who_make_selection()

        if not self.t.get_phase() >= 4 and not self.t.get_phase == 16:
            raise Exception("Current phase is not response phase!!")
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one neesd to execute action!!")

        info = {"playerNo": playerNo}
        score_before = self.t.players[playerNo].score

        aval_actions = self.t.get_response_actions()

        if aval_actions[action].action == mp.Action.Ron or aval_actions[action].action == mp.Action.ChanKan or aval_actions[action].action == mp.Action.ChanAnKan:
            self.horas[playerNo] = True

        self.t.make_selection(action)

        self.played_a_tile[playerNo] = False
        new_state = self.get_state_(playerNo)

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            reward = self.get_final_score_change()[playerNo]
        else:
            reward = self.t.players[playerNo].score - score_before

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            done = 1
            self.final_score_changes.append(self.get_final_score_change())
        else:
            done = 0

        for i in range(4):
            self.scores_before[i] = self.t.players[i].score

        return new_state, reward, done, info

    def get_final_score_change(self):
        rewards = np.zeros([4], dtype=np.float32)

        for i in range(4):
            rewards[i] = self.t.get_result().score[i] - self.scores_before[i]

        return rewards

    def get_state_(self, playerNo):
        return 0

    def symmetric_matrix_features(self, matrix_features):
        """
        Generating a random alternative of features, which is symmetric to the original one
        !!!! Exception !!!! Green one color!!!
        :param hand_matrix_tensor: a B by 34 by 4 matrix, where B is batch_size
        :return: a new, symmetric matrix
        """
        perm_msp = np.random.permutation(3)
        perm_eswn = np.random.permutation(4)
        perm_chh = np.random.permutation(3)

        matrix_features_new = np.zeros_like(matrix_features)

        ## msp
        tmp = []

        tmp.append(matrix_features[:, 0:9, :])
        tmp.append(matrix_features[:, 9:18, :])
        tmp.append(matrix_features[:, 18:27, :])

        matrix_features_new[:, 0:9, :] = tmp[perm_msp[0]]
        matrix_features_new[:, 9:18, :] = tmp[perm_msp[1]]
        matrix_features_new[:, 18:27, :] = tmp[perm_msp[2]]

        ## eswn
        tmp = []

        tmp.append(matrix_features[:, 27, :])
        tmp.append(matrix_features[:, 28, :])
        tmp.append(matrix_features[:, 29, :])
        tmp.append(matrix_features[:, 30, :])

        matrix_features_new[:, 27, :] = tmp[perm_eswn[0]]
        matrix_features_new[:, 28, :] = tmp[perm_eswn[1]]
        matrix_features_new[:, 29, :] = tmp[perm_eswn[2]]
        matrix_features_new[:, 30, :] = tmp[perm_eswn[3]]

        # chh
        tmp = []

        tmp.append(matrix_features[:, 31, :])
        tmp.append(matrix_features[:, 32, :])
        tmp.append(matrix_features[:, 33, :])

        matrix_features_new[:, 31, :] = tmp[perm_chh[0]]
        matrix_features_new[:, 32, :] = tmp[perm_chh[1]]
        matrix_features_new[:, 33, :] = tmp[perm_chh[2]]

        return matrix_features_new

    def get_aval_next_states(self, playerNo: int):

        current_playerNo = self.t.who_make_selection()
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one needs to execute action!!")

        S0 = self.t.get_next_aval_states_matrix_features_frost2(playerNo)
        s0 = self.t.get_next_aval_states_vector_features_frost2(playerNo)
        matrix_features = np.array(S0).reshape([-1, 34, 58])
        vector_features = np.array(s0).reshape([-1, 29])

        return matrix_features, vector_features

    def tile_to_id(self, tile):
        # if tile == mp.BaseTile._1m:
        #     return 0
        # elif tile == mp.BaseTile._2m:
        #     return 1
        # elif tile == mp.BaseTile._3m:
        #     return 2
        # elif tile == mp.BaseTile._4m:
        #     return 3
        # elif tile == mp.BaseTile._5m:
        #     return 4
        # elif tile == mp.BaseTile._6m:
        #     return 5
        # elif tile == mp.BaseTile._7m:
        #     return 6
        # elif tile == mp.BaseTile._8m:
        #     return 7
        # elif tile == mp.BaseTile._9m:
        #     return 8
        # elif tile == mp.BaseTile._1p:
        #     return 9
        # elif tile == mp.BaseTile._2p:
        #     return 10
        # elif tile == mp.BaseTile._3p:
        #     return 11
        # elif tile == mp.BaseTile._4p:
        #     return 12
        # elif tile == mp.BaseTile._5p:
        #     return 13
        # elif tile == mp.BaseTile._6p:
        #     return 14
        # elif tile == mp.BaseTile._7p:
        #     return 15
        # elif tile == mp.BaseTile._8p:
        #     return 16
        # elif tile == mp.BaseTile._9p:
        #     return 17
        # elif tile == mp.BaseTile._1s:
        #     return 18
        # elif tile == mp.BaseTile._2s:
        #     return 19
        # elif tile == mp.BaseTile._3s:
        #     return 20
        # elif tile == mp.BaseTile._4s:
        #     return 21
        # elif tile == mp.BaseTile._5s:
        #     return 22
        # elif tile == mp.BaseTile._6s:
        #     return 23
        # elif tile == mp.BaseTile._7s:
        #     return 24
        # elif tile == mp.BaseTile._8s:
        #     return 25
        # elif tile == mp.BaseTile._9s:
        #     return 26
        # elif tile == mp.BaseTile.east:
        #     return 27
        # elif tile == mp.BaseTile.south:
        #     return 28
        # elif tile == mp.BaseTile.west:
        #     return 29
        # elif tile == mp.BaseTile.north:
        #     return 30
        # elif tile == mp.BaseTile.haku:
        #     return 31
        # elif tile == mp.BaseTile.hatsu:
        #     return 32
        # elif tile == mp.BaseTile.chu:
        #     return 33
        # else:
        #     raise Exception("Input must be a tile!!")
        return int(tile)

    def dora_ind_2_dora_id(self, ind_id):
        if ind_id == 8:
            return 0
        elif ind_id == 8 + 9:
            return 0 + 9
        elif ind_id == 8 + 9 + 9:
            return 0 + 9 + 9
        elif ind_id == 33:
            return 31
        else:
            return ind_id + 1

    def who_do_what(self):
        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            return self.t.who_make_selection(), "response"
        elif self.t.get_phase() < 4:  # action phase
            return self.t.who_make_selection(), "play"

    def render(self, mode='human'):
        print(self.t.get_selected_action.action)



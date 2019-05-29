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

        self.xuanpai_start = 5 + 6 * 4 + 6 * 4
        self.fulu_start = 5 + 6 * 4
        self.river_start = 5
        self.hand_features = 5

        self.hand_dora_id = 4
        self.fulu_dora_id = self.fulu_start + 4
        self.xuanpai_dora_id = self.xuanpai_start + 1

        self.hora_id = 28
        self.riichi_id = 0
        self.double_riichi_id = 4
        self.kannum_id = 26

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

    def step_draw(self, playerNo):
        current_playerNo = self.t.who_make_selection()

        if not self.t.get_phase() < 4:
            raise Exception("Current phase is not draw phase!!")
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one neesd to execute action!!")

        info = {"playerNo": playerNo}
        score_before = self.t.players[playerNo].score

        self.played_a_tile[playerNo] = False
        new_state = self.get_state_(playerNo)

        # the following should be unnecessary but OK
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
            self.tile_in_air = self.t.get_selected_action_tile()

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

    def get_state_(self, playerNo: int):

        matrix_features = np.zeros(self.matrix_feature_size, dtype=np.float16)
        vector_features = np.zeros(self.vector_feature_size, dtype=np.float16)

        # ------------- self hand tiles (34 x 5) -----------------
        tile_num = np.zeros([34,], dtype=np.int)
        hand = self.t.players[playerNo].hand
        for k in range(len(hand)):
            id = self.tile_to_id(hand[k].tile)
            matrix_features[id, tile_num[id]] = 1.
            tile_num[id] += 1

            if hand[k].red_dora:
                matrix_features[id, 4] += 1.

            for m in range(self.t.dora_spec):
                if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                    matrix_features[id, 4] += 1.

        # -------------rivers x 4(tegiri or mogiri ) (34 x 6 x 4) --------------------

        for i in range(4):
            i_relative = (i - playerNo + 4) % 4
            tile_num = np.zeros([34, ], dtype=np.int)
            for k in range (len(self.t.players[i].river.river)):

                tile = self.t.players[i].river.river[k].tile
                id = self.tile_to_id(tile.tile)
                fromhand = 1 if self.t.players[i].river.river[k].fromhand else 0

                matrix_features[id, self.river_start + 6 * i_relative + tile_num[id]] = 1.
                tile_num[id] += 1

                if fromhand:
                    matrix_features[id, self.river_start + 6 * i_relative + 5] = 1.

                if tile.red_dora:
                    matrix_features[id, self.river_start + 6 * i_relative + 4] += 1.

                for m in range(self.t.dora_spec):
                    if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                        matrix_features[id, self.river_start + 6 * i_relative + 4] += 1.

        # ------------- fulus x 4 (34 x 6 x 4)  -----------------------
        for i in range(4):
            i_relative = (i - playerNo + 4) % 4
            fulus = self.t.players[i].fulus
            tile_num = np.zeros([34, ], dtype=np.int)
            for k in range(len(fulus)):

                tiles = fulus[k].tiles

                for p in range(len(tiles)):
                    tile = tiles[p]
                    id = self.tile_to_id(tile.tile)

                    matrix_features[id, self.fulu_start + 6 * i_relative + tile_num[id]] = 1.
                    tile_num[id] += 1

                    if tile.red_dora:  # red dora
                        matrix_features[id, self.fulu_start + 6 * i_relative + 4] += 1.

                    for m in range(self.t.dora_spec):
                        if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                            matrix_features[id, self.fulu_start + 6 * i_relative + 4] += 1.

                take = fulus[k].take
                if not tiles[0].tile == tiles[1].tile: # if is Chi, record which one is taken
                    take_id = self.tile_to_id(tiles[take].tile)
                    matrix_features[take_id, self.fulu_start + 6 * i_relative + 5] += 1.

        # ------------- self xuan pai (34 x 2)  -----------------------
        if self.played_a_tile[playerNo]:
            id = self.tile_to_id(self.tile_in_air.tile)

            matrix_features[id, self.xuanpai_start] = 1.

            if self.tile_in_air.red_dora:  # red dora
                matrix_features[id, self.xuanpai_start + 1] += 1.

            for m in range(self.t.dora_spec):
                if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                    matrix_features[id, self.xuanpai_start + 1] += 1.

        # -------------宝牌指示牌 场风 自风 ---------
        for m in range(self.t.dora_spec):
            dora_spec_id = self.tile_to_id(self.t.DORA[m].tile)
            matrix_features[dora_spec_id, -3] = 1
        matrix_features[26 + int(self.t.game_wind), -2] = 1
        matrix_features[26 + int(self.t.players[playerNo].wind), -1] = 1

        # --------------- Vector Features ---------------------

        vector_features[0:4] = np.array([1 if self.t.players[(i - playerNo + 4) % 4].riichi else 0
                                        for i in range(4)]).astype(np.float16)
        vector_features[4:8] = np.array([1 if self.t.players[(i - playerNo + 4) % 4].double_riichi else 0
                                         for i in range(4)]).astype(np.float16)
        vector_features[8:12] = np.array([1 if self.t.players[(i - playerNo + 4) % 4].ippatsu else 0
                                          for i in range(4)]).astype(np.float16)
        vector_features[12:16] = np.array([1 if self.t.players[(i - playerNo + 4) % 4].oya else 0
                                           for i in range(4)]).astype(np.float16)
        vector_features[16:20] = np.array([1 if self.t.players[(i - playerNo + 4) % 4].menchin else 0
                                           for i in range(4)]).astype(np.float16)
        vector_features[20:24] = np.array([len(self.t.players[(i - playerNo + 4) % 4].hand) / 13.0
                                           for i in range(4)]).astype(np.float16)
        vector_features[24] = self.t.turn / 18.0
        vector_features[25] = len(self.t.YAMA) / 72.0
        vector_features[26] = (self.t.dora_spec - 1.0) / 4
        vector_features[27] = 1. if self.t.players[playerNo].first_round else 0.

        vector_features[28] = 1.0 if self.horas[playerNo] else 0.0

        return matrix_features, vector_features

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

    def get_next_state(self, action: int, playerNo: int):
        # table = t
        hand = self.t.players[playerNo].hand

        matrix_features, vector_features = self.get_state_(playerNo)

        S = deepcopy(matrix_features)
        s = deepcopy(vector_features)

        tile_num = np.zeros([34], dtype=np.int)
        for t in range(34):
            tile_num[t] = np.sum(matrix_features[t, 0:4])

        tile_num_fulus = np.zeros([34], dtype=np.int)
        for t in range(34):
            tile_num_fulus[t] = np.sum(matrix_features[t, self.fulu_start:self.fulu_start+4])

        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            aval_actions = self.t.get_response_actions()
        elif self.t.get_phase() < 4:  # action phase
            aval_actions = self.t.get_self_actions()
        else:
            raise Exception("No next state because game end!!")

        if aval_actions[action].action == mp.Action.Ankan:
            id = self.tile_to_id(aval_actions[action].correspond_tiles[0].tile)
            S[id, self.fulu_start: self.fulu_start + self.hand_features] = deepcopy(S[id, 0:self.hand_features])
            S[id, 0:self.hand_features] = 0
            s[self.kannum_id] += 1  # 杠数

        elif aval_actions[action].action == mp.Action.Chi or aval_actions[action].action == mp.Action.Pon:
            corr_tiles = aval_actions[action].correspond_tiles
            for k in range(len(corr_tiles)):
                tile = corr_tiles[k]
                id = self.tile_to_id(tile.tile)

                S[id, tile_num[id] - 1] = 0.
                tile_num[id] -= 1

                if tile.red_dora:
                    S[id, self.hand_dora_id] -= 1.

                for m in range(self.t.dora_spec):
                    if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                        S[id, self.hand_dora_id] -= 1.

            tile = self.t.get_selected_action_tile()
            id = self.tile_to_id(tile.tile)

            S[id, tile_num_fulus[id] - 1 + 1] = 1.
            tile_num_fulus[id] += 1

            if tile.red_dora:
                S[id, self.fulu_dora_id] += 1.

            for m in range(self.t.dora_spec):
                if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                    S[id, self.fulu_dora_id] += 1.

        elif aval_actions[action].action == mp.Action.Kakan:
            id = self.tile_to_id(aval_actions[action].correspond_tiles[0].tile)
            S[id, self.fulu_start + 3] = 1
            S[id, 0] = 0
            S[id, self.fulu_dora_id] += S[id, 4]  # dora num
            S[id, self.hand_dora_id] = 0

        elif aval_actions[action].action == mp.Action.Kan:
            id = self.tile_to_id(aval_actions[action].correspond_tiles[0].tile)
            S[id, self.fulu_start: self.fulu_start + self.hand_features] = deepcopy(S[id, 0:self.hand_features])
            S[id, self.fulu_start + 3] = 1  # kan tile
            S[id, self.fulu_dora_id] += S[id, 4]  # dora num
            S[id, 0:self.hand_features] = 0 # hand no tile

            tile = self.t.get_selected_action_tile()
            id = self.tile_to_id(tile.tile)

            if tile.red_dora:
                S[id, self.fulu_dora_id] += 1.
            for m in range(self.t.dora_spec):
                if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                    S[id, self.fulu_dora_id] += 1.

        elif aval_actions[action].action == mp.Action.KyuShuKyuHai:
            s[self.hora_id] = 1.

        elif aval_actions[action].action == mp.Action.Play:
            tile = aval_actions[action].correspond_tiles[0]

            id = self.tile_to_id(tile.tile)
            S[id, tile_num[id] - 1] = 0.
            tile_num[id] -= 1
            S[id, self.xuanpai_start] = 1.

            if tile.red_dora:
                S[id, self.hand_dora_id] -= 1.
                S[id, self.xuanpai_start + 1] += 1.

            for m in range(self.t.dora_spec):
                if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                    S[id, self.hand_dora_id] -= 1.
                    S[id, self.xuanpai_start + 1] += 1.

        elif aval_actions[action].action == mp.Action.Riichi:
            if self.t.players[playerNo].first_round:  # double Riichi
                s[self.double_riichi_id] = 1
            else:
                s[self.riichi_id] = 1

        elif aval_actions[action].action == mp.Action.Ron or aval_actions[action].action == mp.Action.ChanKan or \
                        aval_actions[action].action == mp.Action.ChanAnKan:

            tile = self.t.get_selected_action_tile()
            id = self.tile_to_id(tile.tile)

            S[id, tile_num[id] - 1 + 1] = 1.
            tile_num[id] += 1

            if tile.red_dora:
                S[id, self.hand_dora_id] += 1.

            for m in range(self.t.dora_spec):
                if self.dora_ind_2_dora_id(self.tile_to_id(self.t.DORA[m].tile)) == id:  # dora
                    S[id, self.hand_dora_id] += 1.

            s[self.hora_id] = 1.

        elif aval_actions[action].action == mp.Action.Tsumo:
            s[self.hora_id] = 1.

        else:
            pass

        return S, s

    def get_aval_next_states(self, playerNo: int):

        current_playerNo = self.t.who_make_selection()
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one needs to execute action!!")

        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            aval_actions = self.t.get_response_actions()
        elif self.t.get_phase() < 4:  # action phase
            aval_actions = self.t.get_self_actions()

        matrix_features = []
        vector_features = []

        for j in range(len(aval_actions)):
            S, s = self.get_next_state(j, playerNo)
            matrix_features.append(S)
            vector_features.append(s)

        return (matrix_features, vector_features)

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
        # elif tile == mp.BaseTile._1s:
        #     return 9
        # elif tile == mp.BaseTile._2s:
        #     return 10
        # elif tile == mp.BaseTile._3s:
        #     return 11
        # elif tile == mp.BaseTile._4s:
        #     return 12
        # elif tile == mp.BaseTile._5s:
        #     return 13
        # elif tile == mp.BaseTile._6s:
        #     return 14
        # elif tile == mp.BaseTile._7s:
        #     return 15
        # elif tile == mp.BaseTile._8s:
        #     return 16
        # elif tile == mp.BaseTile._9s:
        #     return 17
        # elif tile == mp.BaseTile._1p:
        #     return 18
        # elif tile == mp.BaseTile._2p:
        #     return 19
        # elif tile == mp.BaseTile._3p:
        #     return 20
        # elif tile == mp.BaseTile._4p:
        #     return 21
        # elif tile == mp.BaseTile._5p:
        #     return 22
        # elif tile == mp.BaseTile._6p:
        #     return 23
        # elif tile == mp.BaseTile._7p:
        #     return 24
        # elif tile == mp.BaseTile._8p:
        #     return 25
        # elif tile == mp.BaseTile._9p:
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



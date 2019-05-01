import numpy as np
from copy import deepcopy
import gym
import MahjongPy as mp


class EnvMahjong(gym.Env):

    metadata = {'name': 'Mahjong', 'render.modes': ['human', 'rgb_array'], 'video.frames_per_second': 50}
    spec = {'id': 'TaskT'}

    def __init__(self, printing=True):
        self.t = mp.Table()
        self.Phases = (
            "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE",
            "P4_RESPONSE", "P1_抢杠RESPONSE", "P2_抢杠RESPONSE", "P3_抢杠RESPONSE", "P4_抢杠RESPONSE",
            "P1_抢暗杠RESPONSE", "P2_抢暗杠RESPONSE", " P3_抢暗杠RESPONSE", " P4_抢暗杠RESPONSE", "GAME_OVER")
        self.rons = []
        self.game_count = 0
        self.printing = printing

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

        return [self.get_state_(i) for i in range(4)]

    def get_phase_text(self):
        return self.Phases[self.t.get_phase()]

    def step_play(self, action, playerNo):
        # self action phase
        current_playerNo = self.t.who_make_selection()

        if not self.t.get_phase() < 4:
            raise Exception("Current phase is not self-action phase!!")
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one neesd to execute action!!")

        info = {"playerNo": playerNo}
        score_before = self.t.players[playerNo].score

        self.t.make_selection(action)

        new_state = self.get_state_(playerNo)

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            reward = self.get_final_score_change()[playerNo]
        else:
            reward = self.t.players[playerNo].score - score_before

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            done = 1
            self.rons.append(self.get_final_score_change())

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

        self.t.make_selection(action)

        new_state = self.get_state_(playerNo)

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            reward = self.get_final_score_change()[playerNo]
        else:
            reward = self.t.players[playerNo].score - score_before

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            done = 1
            self.rons.append(self.get_final_score_change())
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

        hand = self.t.players[playerNo].hand

        hand_matrix_naive = np.zeros([34, 4], dtype=np.float32)
        tile_num = np.zeros([34], dtype=np.int32)

        for k in range(len(hand)):
            id = self.tile_to_id(hand[k].tile)
            hand_matrix_naive[id, tile_num[id]] = 1.
            tile_num[id] += 1

        return hand_matrix_naive

    def symmetric_hand(self, hand_matrix_tensor):
        """
        Generating a random alternative of hand_matrix, which is symmetric to the original one
        !!!! Not applicable to AI naive since it only cares about itself's hand
        :param hand_matrix_tensor: a B by 34 by 4 matrix, where B is batch_size
        :return: a new, symmetric hand_matrix
        """
        perm_msp = np.random.permutation(3)
        perm_eswn = np.random.permutation(4)
        perm_chh = np.random.permutation(3)

        hand_matrix_tensor_new = np.zeros_like(hand_matrix_tensor)

        ## msp
        tmp = []

        tmp.append(hand_matrix_tensor[:, 0:9, :])
        tmp.append(hand_matrix_tensor[:, 9:18, :])
        tmp.append(hand_matrix_tensor[:, 18:27, :])

        hand_matrix_tensor_new[:, 0:9, :] = tmp[perm_msp[0]]
        hand_matrix_tensor_new[:, 9:18, :] = tmp[perm_msp[1]]
        hand_matrix_tensor_new[:, 18:27, :] = tmp[perm_msp[2]]

        ## eswn
        tmp = []

        tmp.append(hand_matrix_tensor[:, 27, :])
        tmp.append(hand_matrix_tensor[:, 28, :])
        tmp.append(hand_matrix_tensor[:, 29, :])
        tmp.append(hand_matrix_tensor[:, 30, :])

        hand_matrix_tensor_new[:, 27, :] = tmp[perm_eswn[0]]
        hand_matrix_tensor_new[:, 28, :] = tmp[perm_eswn[1]]
        hand_matrix_tensor_new[:, 29, :] = tmp[perm_eswn[2]]
        hand_matrix_tensor_new[:, 30, :] = tmp[perm_eswn[3]]

        tmp = []

        tmp.append(hand_matrix_tensor[:, 31, :])
        tmp.append(hand_matrix_tensor[:, 32, :])
        tmp.append(hand_matrix_tensor[:, 33, :])

        hand_matrix_tensor_new[:, 31, :] = tmp[perm_chh[0]]
        hand_matrix_tensor_new[:, 32, :] = tmp[perm_chh[1]]
        hand_matrix_tensor_new[:, 33, :] = tmp[perm_chh[2]]

        return hand_matrix_tensor_new

    def get_next_state(self, action: int, playerNo: int):
        # table = t
        hand = self.t.players[playerNo].hand

        hand_matrix_naive = np.zeros([34, 4], dtype=np.float32)
        tile_num = np.zeros([34], dtype=np.int32)

        for k in range(len(hand)):
            id = self.tile_to_id(hand[k].tile)
            hand_matrix_naive[id, tile_num[id]] = 1.
            tile_num[id] += 1

        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            aval_actions = self.t.get_response_actions()
        elif self.t.get_phase() < 4:  # action phase
            aval_actions = self.t.get_self_actions()
        else:
            raise Exception("No next state because game end!!")

        if aval_actions[action].action == mp.Action.Pon:
            id = self.tile_to_id(aval_actions[action].correspond_tiles[0].tile)
            hand_matrix_naive[id, tile_num[id]-2:tile_num[id]] = 0

        elif aval_actions[action].action == mp.Action.Chi:
            for k in range(len(aval_actions[action].correspond_tiles)):
                id = self.tile_to_id(aval_actions[action].correspond_tiles[k].tile)
                hand_matrix_naive[id, tile_num[id]-1] = 0

        elif aval_actions[action].action == mp.Action.Ankan:
            for k in range(len(aval_actions[action].correspond_tiles)):
                id = self.tile_to_id(aval_actions[action].correspond_tiles[k].tile)
                hand_matrix_naive[id, tile_num[id]-1] = 0

        elif aval_actions[action].action == mp.Action.Kan:
            for k in range(len(aval_actions[action].correspond_tiles)):
                id = self.tile_to_id(aval_actions[action].correspond_tiles[k].tile)
                hand_matrix_naive[id, tile_num[id]-1] = 0

        elif aval_actions[action].action == mp.Action.Ron:
            for k in range(len(aval_actions[action].correspond_tiles)):
                id = self.tile_to_id(aval_actions[action].correspond_tiles[k].tile)
                hand_matrix_naive[id, tile_num[id]] = 1

        elif aval_actions[action].action == mp.Action.Tsumo:
            for k in range(len(aval_actions[action].correspond_tiles)):
                id = self.tile_to_id(aval_actions[action].correspond_tiles[k].tile)
                hand_matrix_naive[id, tile_num[id]] = 1

        elif aval_actions[action].action == mp.Action.Play:
            id = self.tile_to_id(aval_actions[action].correspond_tiles[0].tile)
            hand_matrix_naive[id, tile_num[id]-1] = 0

        return hand_matrix_naive

    def get_aval_next_states(self, playerNo: int):

        current_playerNo = self.t.who_make_selection()
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one needs to execute action!!")

        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            aval_actions = self.t.get_response_actions()
        elif self.t.get_phase() < 4:  # action phase
            aval_actions = self.t.get_self_actions()

        aval_next_states = []
        for j in range(len(aval_actions)):
            aval_next_states.append(self.get_next_state(j, playerNo))

        return aval_next_states

    def tile_to_id(self, tile):
        if tile == mp.BaseTile._1m:
            return 0
        elif tile == mp.BaseTile._2m:
            return 1
        elif tile == mp.BaseTile._3m:
            return 2
        elif tile == mp.BaseTile._4m:
            return 3
        elif tile == mp.BaseTile._5m:
            return 4
        elif tile == mp.BaseTile._6m:
            return 5
        elif tile == mp.BaseTile._7m:
            return 6
        elif tile == mp.BaseTile._8m:
            return 7
        elif tile == mp.BaseTile._9m:
            return 8
        elif tile == mp.BaseTile._1p:
            return 9
        elif tile == mp.BaseTile._2p:
            return 10
        elif tile == mp.BaseTile._3p:
            return 11
        elif tile == mp.BaseTile._4p:
            return 12
        elif tile == mp.BaseTile._5p:
            return 13
        elif tile == mp.BaseTile._6p:
            return 14
        elif tile == mp.BaseTile._7p:
            return 15
        elif tile == mp.BaseTile._8p:
            return 16
        elif tile == mp.BaseTile._9p:
            return 17
        elif tile == mp.BaseTile._1s:
            return 18
        elif tile == mp.BaseTile._2s:
            return 19
        elif tile == mp.BaseTile._3s:
            return 20
        elif tile == mp.BaseTile._4s:
            return 21
        elif tile == mp.BaseTile._5s:
            return 22
        elif tile == mp.BaseTile._6s:
            return 23
        elif tile == mp.BaseTile._7s:
            return 24
        elif tile == mp.BaseTile._8s:
            return 25
        elif tile == mp.BaseTile._9s:
            return 26
        elif tile == mp.BaseTile.east:
            return 27
        elif tile == mp.BaseTile.south:
            return 28
        elif tile == mp.BaseTile.west:
            return 29
        elif tile == mp.BaseTile.north:
            return 30
        elif tile == mp.BaseTile.chu:
            return 31
        elif tile == mp.BaseTile.hatsu:
            return 32
        elif tile == mp.BaseTile.haku:
            return 33
        else:
            raise Exception("Input must be a tile!!")

    def who_do_what(self):
        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            return self.t.who_make_selection(), "response"
        elif self.t.get_phase() < 4:  # action phase
            return self.t.who_make_selection(), "play"

    def render(self, mode='human'):
        print(self.t.get_selected_action.action)


import warnings
import time

import numpy as np
from copy import deepcopy
import gym
import MahjongPy as mp

from mahjong.shanten import Shanten
from mahjong.tile import TilesConverter

shanten = Shanten()

from gym.spaces import Discrete, Box


# ------------- OBS INDICES -----------

player_i_hand_start_ind = [0, 81, 87, 93]  # later 3 in oracle_obs
player_i_side_start_ind = [6, 12, 18, 24]
player_i_river_start_ind = [30, 40, 50, 60]

dora_indicator_ind = 70
dora_ind = 74
game_wind_ind = 78
self_wind_ind = 79
latest_tile_ind = 80

aka_tile_ints = [16, 16 + 36, 16 + 36 + 36]

player_obs_width = 81
oracle_obs_width = 18

# ------------- ACTION INDICES -----------
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

# Pass KAKAN, ANKAN, TSUMO and PUSH can be done by discard

# ----------- ACTION REPRESENTING OBS INDICES ----------

DISCARD_ACT_IND = 0

CHILEFT_ACT_IND = 1
CHIMIDDLE_ACT_IND = 2
CHIRIGHT_ACT_IND = 3
PON_ACT_IND = 4
ANKAN_ACT_IND = 5
MINKAN_ACT_IND = 6
KAKAN_ACT_IND = 7

RIICHI_ACT_IND = 8
RON_ACT_IND = 9
TSUMO_ACT_IND = 10
PUSH_ACT_IND = 11

aval_actions_obs_dim = 12


UNICODE_TILES = """
    🀇 🀈 🀉 🀊 🀋 🀌 🀍 🀎 🀏 
    🀙 🀚 🀛 🀜 🀝 🀞 🀟 🀠 🀡
    🀐 🀑 🀒 🀓 🀔 🀕 🀖 🀗 🀘
    🀀 🀁 🀂 🀃
    🀆 🀅 🀄
""".split()


def shift(matrix, n):

    tmp = deepcopy(matrix)

    matrix[:, :-n] = tmp[:, n:]
    matrix[:, -n:] = tmp[:, :n]

    return matrix


def TileTo136(Tile):
    if Tile.red_dora:
        return int(Tile.tile) * 4
    else:
        return int(Tile.tile) * 4 + 3


def dora_ind_2_dora_id(ind_id):
    if ind_id == 8:
        return 0
    elif ind_id == 8 + 9:
        return 0 + 9
    elif ind_id == 8 + 9 + 9:
        return 0 + 9 + 9
    elif ind_id == 30:
        return 27
    elif ind_id == 33:
        return 31
    else:
        return ind_id + 1


def dora2indicator(dora_id):
    if dora_id == 0:  # 1m
        indicator_id = 8  # 9m
    elif dora_id == 9:  # 1p
        indicator_id = 17  # 9p
    elif dora_id == 18:  # 1s
        indicator_id = 26  # 9s
    elif dora_id == 27:  # East
        indicator_id = 30  # North
    elif dora_id == 31:  # Hake
        indicator_id = 33  # Chu
    else:
        indicator_id = dora_id - 1
    return indicator_id


def is_consecutive(a: int, b: int, c: int):
    array = np.array([a, b, c])
    return array[1] - array[0] == 1 and array[2] - array[1] == 1 and c < 27 and int(a / 9) == int(b / 9) == int(c / 9)


def generate_obs(playerNo, hand_tiles, river_tiles, side_tiles, dora_tiles, game_wind: str, oya_id: int, latest_tile=None):

    all_obs_0p = np.zeros([34, player_obs_width + oracle_obs_width], dtype=bool)

    global player_i_hand_start_ind
    global player_i_side_start_ind
    global player_i_river_start_ind

    global dora_indicator_ind
    global dora_ind
    global game_wind_ind
    global self_wind_ind
    global latest_tile_ind

    global aka_tile_ints

    # ----------------- Side Tiles Process ------------------
    for player_id, player_side_tiles in enumerate(side_tiles):
        side_tile_num = np.zeros(34, dtype=np.uint8)
        for side_tile in player_side_tiles:
            side_tile_id = int(side_tile[0] / 4)
            side_tile_num[side_tile_id] += 1

            if side_tile[0] in aka_tile_ints:
                # Red dora
                all_obs_0p[side_tile_id, player_i_side_start_ind[player_id] + 5] = 1
            if side_tile[1]:
                all_obs_0p[side_tile_id, player_i_side_start_ind[player_id] + 4] = 1

        for t_id in range(34):
            for k in range(4):
                if side_tile_num[t_id] > k:
                    all_obs_0p[t_id, player_i_side_start_ind[player_id] + k] = 1

    # ----------------- River Tiles Procces ------------------
    for player_id, player_river_tiles in enumerate(river_tiles):  # 副露也算在牌河里, also include Riichi info
        river_tile_num = np.zeros(34, dtype=np.uint8)
        river_tile_tekiri = np.zeros([34, 4], dtype=bool)
        for river_tile in player_river_tiles:
            river_tile_id = int(river_tile[0] / 4)

            all_obs_0p[river_tile_id, player_i_hand_start_ind[player_id] + 4] = 1

            river_tile_num[river_tile_id] += 1
            river_tile_tekiri[river_tile_id, river_tile_num[river_tile_id] - 1] = river_tile[1]

            if river_tile[0] in aka_tile_ints:  # Red dora
                all_obs_0p[river_tile_id, player_i_river_start_ind[player_id] + 8] = 1

            # is riichi-announcement tile
            if river_tile[2] and all_obs_0p[river_tile_id, player_i_river_start_ind[player_id] + 9]:
                raise ValueError  # riichi for twice, not possible
            if river_tile[2]:
                all_obs_0p[river_tile_id, player_i_river_start_ind[player_id] + 9] = 1

        for t_id in range(34):
            for k in range(4):
                if river_tile_num[t_id] > k:
                    all_obs_0p[t_id, player_i_river_start_ind[player_id] + k] = 1
                    # te-kiri (from hand)
                    all_obs_0p[t_id, player_i_river_start_ind[player_id] + 4 + k] = river_tile_tekiri[t_id, k]

    # ----------------- Hand Tiles Process ------------------
    for player_id, player_hand_tiles in enumerate(hand_tiles):
        hand_tile_num = np.zeros(34, dtype=np.uint8)
        for hand_tile in player_hand_tiles:
            hand_tile_id = int(hand_tile / 4)
            hand_tile_num[hand_tile_id] += 1

            if hand_tile in aka_tile_ints:
                # Aka dora
                all_obs_0p[hand_tile_id, player_i_hand_start_ind[player_id] + 5] = 1

            # how many times this tile has been discarded before by this player
            all_obs_0p[hand_tile_id, player_i_hand_start_ind[player_id] + 4] = (np.sum(
                all_obs_0p[hand_tile_id,
                    player_i_river_start_ind[player_id]:player_i_river_start_ind[player_id] + 4])) > 0

        for t_id in range(34):
            for k in range(4):
                if hand_tile_num[t_id] > k:
                    all_obs_0p[t_id, player_i_hand_start_ind[player_id] + k] = 1

    # ----------------- Dora Process ------------------
    dora_tile_num = np.zeros(34, dtype=np.uint8)
    for dora_tile in dora_tiles:
        dora_hai_id = int(dora_tile / 4)
        dora_tile_num[dora_hai_id] += 1

    for t_id in range(34):
        for k in range(4):
            if dora_tile_num[t_id] > k:
                all_obs_0p[t_id, dora_ind + k] = 1
                all_obs_0p[dora2indicator(t_id), dora_indicator_ind + k] = 1

    # ----------------- Public Game State ----------------
    # self wind and game wind
    if game_wind == "east":
        game_wind_tile_id = 27
    elif game_wind == "south":
        game_wind_tile_id = 28
    elif game_wind == "west":
        game_wind_tile_id = 29
    elif game_wind == "north":
        game_wind_tile_id = 30
    else:
        raise ValueError

    self_wind_tile_id = 27 + (playerNo - oya_id + 8) % 4

    all_obs_0p[game_wind_tile_id, game_wind_ind] = 1  # Case 1 to 4 in dim 0
    all_obs_0p[self_wind_tile_id, self_wind_ind] = 1

    # ------------ Latest Tile -------------
    if latest_tile is not None:
        all_obs_0p[int(latest_tile / 4), latest_tile_ind] = 1

    # players_obs = all_obs_0p[:, :player_obs_width]
    # oracles_obs = all_obs_0p[:, player_obs_width:]

    if playerNo == 0:
        return all_obs_0p
    else:
        k = playerNo

        all_obs_kp = deepcopy(all_obs_0p)

        # self-wind given by the input

        hand_indices_obs = np.concatenate([all_obs_0p[:, :player_i_side_start_ind[0]],
                                           all_obs_0p[:, player_i_hand_start_ind[1]:]], axis=-1)
        hand_indices_obs_playerk = shift(hand_indices_obs, int(k * (player_i_hand_start_ind[2] - player_i_hand_start_ind[1])))

        all_obs_kp[:, :player_i_side_start_ind[0]] = hand_indices_obs_playerk[:, :player_i_side_start_ind[0]]

        all_obs_kp[:, player_i_hand_start_ind[1]:] = hand_indices_obs_playerk[:, player_i_side_start_ind[0]:]

        all_obs_kp[:, player_i_side_start_ind[0]:player_i_river_start_ind[0]] = shift(
            all_obs_0p[:, player_i_side_start_ind[0]:player_i_river_start_ind[0]],
            player_i_side_start_ind[k] - player_i_side_start_ind[0])

        all_obs_kp[:, player_i_river_start_ind[0]:dora_indicator_ind] = shift(
            all_obs_0p[:, player_i_river_start_ind[0]:dora_indicator_ind],
            player_i_river_start_ind[k] - player_i_river_start_ind[0])

        return all_obs_kp


class EnvMahjong(gym.Env):
    """
    Mahjong Environment
    """

    metadata = {'name': 'Mahjong'}

    def __init__(self, printing=True, reward_unit=100, force_win=False, force_riichi=False, append_aval_action_obs=True):
        self.t = mp.Table()
        self.Phases = (
            "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE",
            "P4_RESPONSE", "P1_ChanKanRESPONSE", "P2_ChanKanRESPONSE", "P3_ChanKanRESPONSE", "P4_ChanKanRESPONSE",
            "P1_ChanAnKanRESPONSE", "P2_ChanAnKanRESPONSE", " P3_ChanAnKanRESPONSE", " P4_ChanAnKanRESPONSE",
            "GAME_OVER", "P1_DRAW, P2_DRAW, P3_DRAW, P4_DRAW")
        self.horas = [False, False, False, False]
        self.played_a_tile = [False, False, False, False]
        self.tile_in_air = None
        self.final_score_changes = []
        self.game_count = 0
        self.printing = printing
        self.reward_unit = reward_unit

        self.force_win = force_win
        self.force_riichi = force_riichi

        self.vector_feature_size = 30

        self.append_aval_action_obs = append_aval_action_obs

        self.scores_init = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_init[i] = self.t.players[i].score

        self.scores_before = np.zeros([4], dtype=np.float32)
        self.scores_reset = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_before[i] = self.t.players[i].score
            self.scores_reset[i] = self.t.players[i].score

        if not self.append_aval_action_obs:
            self.observation_space = Box(low=0, high=1, shape=[player_obs_width, 34])
            self.full_observation_space = Box(low=0, high=1, shape=[player_obs_width + oracle_obs_width, 34])
        else:
            self.observation_space = Box(low=0, high=1, shape=[player_obs_width + aval_actions_obs_dim, 34])
            self.full_observation_space = Box(low=0, high=1, shape=[player_obs_width + oracle_obs_width + aval_actions_obs_dim, 34])

        self.oracle_observation_space = Box(low=0, high=1, shape=[oracle_obs_width, 34])

        self.action_space = Discrete(47)

    def reset(self, oya, game_wind):
        self.t = mp.Table()

        # oya = np.random.random_integers(0, 3)
        # winds = ['east', 'south', 'west', 'north']
        oya = '{}'.format(oya)

        self.oya_id = int(oya)
        self.game_wind = game_wind

        # self.t.game_init()
        meta = {"oya": oya, "wind": game_wind}
        print(meta)
        print('Init...')
        self.t.game_init_with_metadata(meta)
        print('Initialized.')
        # ----------------- Statistics ------------------
        self.game_count += 1

        self.played_a_tile = [False, False, False, False]

        self.scores_init = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_init[i] = self.t.players[i].score

        self.scores_before = np.zeros([4], dtype=np.float32)
        self.scores_reset = np.zeros([4], dtype=np.float32)
        for i in range(4):
            self.scores_before[i] = self.t.players[i].score
            self.scores_reset[i] = self.t.players[i].score

        # ---------------- Table raw state ----------------
        self.curr_all_obs = np.zeros([4, 34, player_obs_width + oracle_obs_width])

        self.hand_tiles = [[], [], [], []]
        self.river_tiles = [[], [], [], []]
        self.side_tiles = [[], [], [], []]
        self.dora_tiles = []
        # self.game_wind_obs = np.zeros(34)  # index: -4

        self.dora_tiles.append(dora_ind_2_dora_id(int(self.t.DORA[0].tile)) * 4 + 3)

        self.latest_tile = None

        for pid in range(4):
            for i in range(len(self.t.players[pid].hand)):
                if self.t.players[pid].hand[i].red_dora:
                    self.hand_tiles[pid].append(int(self.t.players[pid].hand[i].tile) * 4)
                else:
                    self.hand_tiles[pid].append(int(self.t.players[pid].hand[i].tile) * 4 + 3)

        who, what = self.who_do_what()

        self.is_deciding_riichi = False
        self.can_riichi = False
        self.do_not_update_hand_and_latest_tiles_this_time = False
        self.prev_step_is_naru = False
        self.riichi_tile_id = -1
        self.curr_valid_actions = []
        self.non_valid_discard_tiles_id = [[], [], [], []]
        self.ron_tile = None

        self.aval_action_obs = np.zeros([34, aval_actions_obs_dim], dtype=np.uint8)

        return self.get_state()

    def get_valid_actions(self, nhot=True):


        self.update_hand_and_latest_tiles()

        self.curr_valid_actions = []

        self.aval_action_obs = np.zeros([34, aval_actions_obs_dim], dtype=np.uint8)

        phase = self.t.get_phase()
        if phase < 4:
            aval_actions = self.t.get_self_actions()


            if self.is_deciding_riichi:
                self.curr_valid_actions += [RIICHI, PASS_RIICHI]
                self.aval_action_obs[self.riichi_tile_id, RIICHI_ACT_IND] = 1

            else:
                for act in aval_actions:
                    if act.action == mp.BaseAction.Play:
                        self.curr_valid_actions.append(int(act.correspond_tiles[0].tile))  # considered shiti
                        self.aval_action_obs[int(act.correspond_tiles[0].tile), DISCARD_ACT_IND] = 1
                    elif act.action == mp.BaseAction.Ankan:
                        self.curr_valid_actions.append(ANKAN)
                        self.aval_action_obs[int(act.correspond_tiles[0].tile), ANKAN_ACT_IND] = 1
                    elif act.action == mp.BaseAction.Kakan:
                        self.curr_valid_actions.append(KAKAN)
                        self.aval_action_obs[int(act.correspond_tiles[0].tile), KAKAN_ACT_IND] = 1
                    elif act.action == mp.BaseAction.Tsumo:
                        self.curr_valid_actions.append(TSUMO)
                        self.aval_action_obs[int(self.latest_tile / 4), TSUMO_ACT_IND] = 1
                    elif act.action == mp.BaseAction.KyuShuKyuHai:
                        self.curr_valid_actions.append(PUSH)
                        for ht in self.hand_tiles[self.t.who_make_selection()]:
                            if int(ht / 4) in [0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33]:
                                self.aval_action_obs[int(ht / 4), PUSH_ACT_IND] = 1
                    elif act.action != mp.BaseAction.Riichi:
                        print(act.action)
                        raise ValueError

        elif phase < 16:
            aval_actions = self.t.get_response_actions()

            if len(aval_actions) == 1:
                self.curr_valid_actions = [PASS_RESPONSE]
            else:
                for act in aval_actions:
                    if act.action == mp.BaseAction.Pon:
                        self.curr_valid_actions.append(PON)
                        self.aval_action_obs[int(act.correspond_tiles[0].tile), PON_ACT_IND] = 1
                    elif act.action == mp.BaseAction.Kan:
                        self.curr_valid_actions.append(MINKAN)
                        self.aval_action_obs[int(act.correspond_tiles[0].tile), MINKAN_ACT_IND] = 1
                    elif act.action in [mp.BaseAction.Ron, mp.BaseAction.ChanKan, mp.BaseAction.ChanAnKan]:
                        self.curr_valid_actions.append(RON)
                        self.aval_action_obs[int(self.t.get_selected_action_tile().tile), RON_ACT_IND] = 1
                    elif act.action == mp.BaseAction.Pass:
                        self.curr_valid_actions.append(PASS_RESPONSE)
                    elif act.action == mp.BaseAction.Chi:
                        chi_parents_tiles = act.correspond_tiles
                        if is_consecutive(int(self.t.get_selected_action_tile().tile), int(chi_parents_tiles[0].tile),
                                          int(chi_parents_tiles[1].tile)):
                            chi_side = CHILEFT
                            self.curr_valid_actions.append(chi_side)
                            self.aval_action_obs[int(self.t.get_selected_action_tile().tile), CHILEFT_ACT_IND] = 1
                        elif is_consecutive(int(chi_parents_tiles[0].tile), int(self.t.get_selected_action_tile().tile),
                                            int(chi_parents_tiles[1].tile)):
                            chi_side = CHIMIDDLE
                            self.curr_valid_actions.append(chi_side)
                            self.aval_action_obs[int(self.t.get_selected_action_tile().tile), CHIMIDDLE_ACT_IND] = 1
                        elif is_consecutive(int(chi_parents_tiles[0].tile), int(chi_parents_tiles[1].tile),
                                            int(self.t.get_selected_action_tile().tile)):
                            chi_side = CHIRIGHT
                            self.curr_valid_actions.append(chi_side)
                            self.aval_action_obs[int(self.t.get_selected_action_tile().tile), CHIRIGHT_ACT_IND] = 1
                        else:
                            print("==================== Abnormal Chi ====================")
                            print(chi_parents_tiles[0].tile, chi_parents_tiles[1].tile, int(self.t.get_selected_action_tile().tile))
                            print("======================================================")
                            # raise ValueError

                    else:
                        print(act.action)
                        raise ValueError
        else:
            self.curr_valid_actions = [-1]

        self.curr_valid_actions = list(set(self.curr_valid_actions))

        if not nhot:
            return self.curr_valid_actions
        else:
            curr_valid_actions_mask = np.zeros(self.action_space.n, dtype=np.bool)
            curr_valid_actions_mask[self.curr_valid_actions] = 1
            return curr_valid_actions_mask

    def get_curr_player_id(self):
        who, what = self.who_do_what()
        return who

    def get_payoffs(self):
        scores_change = self.get_final_score_change()
        payoff = [sc / self.reward_unit for sc in scores_change]
        return payoff

    def is_over(self):
        return self.Phases[self.t.get_phase()] == "GAME_OVER"

    def step(self, player_id, action, raw_action=False):

        who, what = self.who_do_what()

        self.prev_step_is_naru = False  # to make latest_tiles available
        self.update_hand_and_latest_tiles()

        assert who == player_id

        valid_actions = self.get_valid_actions(nhot=False)
        if action not in valid_actions:
            raise ValueError("action is not valid!! \
                Current valid actions can be obtained by env.get_valid_actions(onehot=False)")

        if what == "response":
            results = self.step_response(action, player_id)
        elif what == "play":
            ## !! Riici and discard are separate
            if self.is_deciding_riichi:
                if action == RIICHI:
                    riichi = True
                elif action == PASS_RIICHI:
                    riichi = False
                else:
                    raise ValueError
            else:
                riichi = False
            results = self.step_play(action, player_id, riichi)

        while not self.has_done() and len(self.get_valid_actions(nhot=False)) == 1:
            self.t.make_selection(0)

        if self.has_done():
            return results[0], results[1], 1, results[3]
        else:
            return results

    def get_aval_action_obs(self, player_id):
        if not player_id == self.t.who_make_selection():
            print("You are trying to obtain observation from a player who is not making decision !!!! This is not encouraged!")
            print("current player {}, get obs of {}".format(self.t.who_make_selection(), player_id))
        self.get_valid_actions()
        return self.aval_action_obs

    def get_obs(self, player_id):
        self.update_hand_and_latest_tiles()

        self.curr_all_obs[player_id] = generate_obs(player_id,
            self.hand_tiles, self.river_tiles, self.side_tiles, self.dora_tiles,
            self.game_wind, self.oya_id, latest_tile=self.latest_tile)

        if self.append_aval_action_obs:
            return np.concatenate([self.curr_all_obs[player_id, :, :player_obs_width].swapaxes(0, 1),
                                   self.get_aval_action_obs(player_id).swapaxes(0, 1)], axis=-2)
        else:
            return self.curr_all_obs[player_id, :, :self.observation_space.shape[0]].swapaxes(0, 1)

    def get_full_obs(self, player_id):
        self.update_hand_and_latest_tiles()

        self.curr_all_obs[player_id] = generate_obs(player_id,
            self.hand_tiles, self.river_tiles, self.side_tiles, self.dora_tiles,
            self.game_wind, self.oya_id, latest_tile=self.latest_tile)

        if self.append_aval_action_obs:
            return np.concatenate([self.curr_all_obs[player_id, :, :player_obs_width].swapaxes(0, 1),
                                   self.get_aval_action_obs(player_id).swapaxes(0, 1),
                                   self.curr_all_obs[player_id, :, -oracle_obs_width:].swapaxes(0, 1)], axis=-2)
        else:
            return self.curr_all_obs[player_id].swapaxes(0, 1)

    def get_oracle_obs(self, player_id):
        self.update_hand_and_latest_tiles()

        self.curr_all_obs[player_id] = generate_obs(player_id,
            self.hand_tiles, self.river_tiles, self.side_tiles, self.dora_tiles,
            self.game_wind, self.oya_id, latest_tile=self.latest_tile)

        return self.curr_all_obs[player_id, :, -oracle_obs_width:].swapaxes(0, 1)

    def get_state(self):
        # get raw state
        self.hand_tiles = [[], [], [], []]
        for pid in range(4):
            for i in range(len(self.t.players[pid].hand)):
                if self.t.players[pid].hand[i].red_dora:
                    self.hand_tiles[pid].append(int(self.t.players[pid].hand[i].tile) * 4)
                else:
                    self.hand_tiles[pid].append(int(self.t.players[pid].hand[i].tile) * 4 + 3)

        return self.hand_tiles, self.river_tiles, self.side_tiles, self.dora_tiles, \
               self.game_wind, self.oya_id, self.latest_tile

    def get_phase_text(self):
        return self.Phases[self.t.get_phase()]

    def update_hand_and_latest_tiles(self):

        if self.t.get_phase() != 16:
            playerNo = self.get_curr_player_id()

            if not self.do_not_update_hand_and_latest_tiles_this_time:
                self.hand_tiles = [[], [], [], []]
                for pid in range(4):
                    for i in range(len(self.t.players[pid].hand)):
                        if self.t.players[pid].hand[i].red_dora:
                            self.hand_tiles[pid].append(int(self.t.players[pid].hand[i].tile) * 4)
                        else:
                            self.hand_tiles[pid].append(int(self.t.players[pid].hand[i].tile) * 4 + 3)
                if self.t.get_phase() < 4:
                    self.latest_tile = self.hand_tiles[playerNo][-1]
        else:
            pass

    def step_play(self, action, playerNo, riichi=False):
        # self action phase
        action = int(action)

        # -------------------- update latest tile for drawing a tile ----------
        self.update_hand_and_latest_tiles()
        # --------------------------------------------------------------------------

        current_playerNo = self.t.who_make_selection()

        if not self.t.get_phase() < 4:
            raise Exception("Current phase is not self-action phase!!")
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one neesd to execute action!!")

        info = {"playerNo": playerNo}
        score_before = self.t.players[playerNo].score

        aval_actions = self.t.get_self_actions()

        can_win = False
        win_action_no = 0
        aval_self_actions = aval_actions
        for self_action in aval_self_actions:
            if self_action.action == mp.BaseAction.Tsumo:
                can_win = True
                break
            win_action_no += 1

        # ------------- if can win, just win -----------
        if self.force_win and can_win:
            warnings.warn("Can win, automatically choose to win !!")
            self.t.make_selection(win_action_no)
            desired_action_type = mp.BaseAction.Tsumo
            self.do_not_update_hand_and_latest_tiles_this_time = False
        elif action == TSUMO:
            self.t.make_selection(win_action_no)
            desired_action_type = mp.BaseAction.Tsumo
            self.do_not_update_hand_and_latest_tiles_this_time = False
        else:
            self.can_riichi = False
            self.can_riichi_tiles_id = []
            for act in aval_actions:
                if act.action == mp.BaseAction.Riichi:
                    self.can_riichi = True
                    self.can_riichi_tiles_id.append(int(act.correspond_tiles[0].tile))

            if self.can_riichi and action < 34 and (not self.is_deciding_riichi) and (action in self.can_riichi_tiles_id):
                self.riichi_tile_id = int(action)
                self.is_deciding_riichi = True

                reward = 0
                done = 0

                # ------ update state -------
                self.update_hand_and_latest_tiles()

                if self.riichi_tile_id == int(self.hand_tiles[playerNo][-1] / 4):
                    is_from_hand = 1
                else:
                    is_from_hand = 0

                discard_tile_id = action

                correctly_discarded = False
                for xx in range(4):
                    try:
                        self.hand_tiles[playerNo].remove(discard_tile_id * 4 + 3 - xx)
                        correctly_discarded = True
                        removed_tile = discard_tile_id * 4 + 3 - xx
                        break
                    except:
                        pass
                if not correctly_discarded:
                    raise ValueError

                self.river_tiles[playerNo].append([removed_tile, is_from_hand, 0])

                # remove from hand tiles
                self.do_not_update_hand_and_latest_tiles_this_time = True
                self.latest_tile = removed_tile

            else:
                self.do_not_update_hand_and_latest_tiles_this_time = False
                self.update_hand_and_latest_tiles()

                if self.force_riichi:
                    for act in aval_actions:
                        if act.action == mp.BaseAction.Riichi and int(act.correspond_tiles[0].tile) == self.riichi_tile_id:
                            riichi = True
                            warnings.warn("Can richii, automatically choose to riichi !!")
                            break
                if riichi:
                    desired_action_type = mp.BaseAction.Riichi
                    desired_action_tile_id = self.riichi_tile_id
                    if self.riichi_tile_id == int(self.latest_tile / 4):
                        is_from_hand = 1
                    else:
                        is_from_hand = 0
                else:  # normal step
                    if action < 34:
                        desired_action_type = mp.BaseAction.Play
                        desired_action_tile_id = action
                        if action != int(self.hand_tiles[playerNo][-1] / 4):
                            is_from_hand = 1
                        else:
                            is_from_hand = 0
                    elif action == ANKAN:
                        desired_action_tile_id = None  # TODO: There is some simplification
                        desired_action_type = mp.BaseAction.Ankan
                    elif action == KAKAN:
                        desired_action_tile_id = None  # TODO: There is some simplification
                        desired_action_type = mp.BaseAction.Kakan
                    elif action == TSUMO:
                        desired_action_type = mp.BaseAction.Tsumo
                        desired_action_tile_id = None
                    elif action == PUSH:
                        desired_action_type = mp.BaseAction.KyuShuKyuHai
                        desired_action_tile_id = None
                    elif action == PASS_RIICHI:
                        desired_action_type = mp.BaseAction.Play
                        desired_action_tile_id = self.riichi_tile_id
                        action = self.riichi_tile_id
                        if action != int(self.hand_tiles[playerNo][-1] / 4):
                            is_from_hand = 1
                        else:
                            is_from_hand = 0
                    else:
                        print(action)
                        raise ValueError

                action_no = 0
                has_valid_action = False
                for act in aval_actions:
                    if act.action == desired_action_type and \
                            (desired_action_tile_id is None or int(act.correspond_tiles[0].tile) == desired_action_tile_id):
                        has_valid_action = True

                        if desired_action_type in [mp.BaseAction.Ankan, mp.BaseAction.Kakan]:
                            kan_tile_id = int(act.correspond_tiles[0].tile)

                        break
                    action_no += 1

                if not has_valid_action:
                    print(desired_action_tile_id)
                    print(act.action)
                    print(desired_action_type)
                    raise ValueError
                assert has_valid_action is True

                self.t.make_selection(action_no)

                if self.t.get_selected_base_action() == mp.BaseAction.Play or self.t.get_selected_base_action() == mp.BaseAction.Riichi:
                    self.played_a_tile[playerNo] = True
                    assert aval_actions[action_no].correspond_tiles[0].tile == self.t.get_selected_action_tile().tile
                    if aval_actions[action_no].correspond_tiles[0].red_dora:
                        self.latest_tile = 4 * int(self.t.get_selected_action_tile().tile)
                    else:
                        self.latest_tile = 4 * int(self.t.get_selected_action_tile().tile) + 3
                    # print("played a tile!!!!", self.latest_tile)


                # ----------------- State update -------------------

                # if is riici or discard:
                if desired_action_type == mp.BaseAction.Riichi or desired_action_type == mp.BaseAction.Play:
                    discard_tile_id = int(self.t.get_selected_action_tile().tile)
                    assert desired_action_tile_id == int(self.t.get_selected_action_tile().tile)

                    if desired_action_type == mp.BaseAction.Play:
                        if not self.is_deciding_riichi:
                            correctly_discarded = False
                            for xx in range(4):
                                try:
                                    self.hand_tiles[playerNo].remove(discard_tile_id * 4 + 3 - xx)
                                    correctly_discarded = True
                                    removed_tile = discard_tile_id * 4 + 3 - xx
                                    break
                                except:
                                    pass
                            if not correctly_discarded:
                                raise ValueError

                            self.river_tiles[playerNo].append([removed_tile, is_from_hand, 0])
                            self.latest_tile = removed_tile

                    if desired_action_type == mp.BaseAction.Riichi:  # discard already done
                        self.river_tiles[playerNo][-1][-1] = 1  # make riichi obs True

                elif action == TSUMO or action == PUSH:
                    # Does not need to do anything
                    pass

                elif action == KAKAN:
                    # --------------- update game states  -------------
                    side_tiles_added_by_naru = [[kan_tile_id * 4, 0]]  # because aka only 1

                    hand_tiles_removed_by_naru = []

                    for ht in self.hand_tiles[playerNo]:
                        if int(ht / 4) == kan_tile_id:
                            hand_tiles_removed_by_naru.append(ht)

                    self.side_tiles[playerNo] = self.side_tiles[playerNo] + side_tiles_added_by_naru

                    for hh in hand_tiles_removed_by_naru:
                        self.hand_tiles[playerNo].remove(hh)

                    self.prev_step_is_naru = True

                elif action == ANKAN:
                    # --------------- update game states  -------------
                    side_tiles_added_by_naru = [[kan_tile_id * 4, 0], [kan_tile_id * 4 + 1, 0],
                                                [kan_tile_id * 4 + 2, 0], [kan_tile_id * 4 + 3, 0]]

                    hand_tiles_removed_by_naru = []

                    for ht in self.hand_tiles[playerNo]:
                        if int(ht / 4) == kan_tile_id:
                            hand_tiles_removed_by_naru.append(ht)

                    self.side_tiles[playerNo] = self.side_tiles[playerNo] + side_tiles_added_by_naru

                    for hh in hand_tiles_removed_by_naru:
                        self.hand_tiles[playerNo].remove(hh)

                    self.prev_step_is_naru = True
                else:
                    raise ValueError

                self.is_deciding_riichi = False

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            reward = self.get_final_score_change()[playerNo] / self.reward_unit
        else:
            reward = (self.t.players[playerNo].score - score_before) / self.reward_unit
            if riichi:
                reward -= 1000 / self.reward_unit

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            done = 1
            self.final_score_changes.append(self.get_final_score_change())
        else:
            done = 0

        for i in range(4):
            self.scores_before[i] = self.t.players[i].score

        return self.get_state(), reward, done, info

    def has_done(self):
        return self.Phases[self.t.get_phase()] == "GAME_OVER"

    def step_response(self, action: int, playerNo: int):
        # response phase
        action = int(action)

        # -------------------- update latest tile for drawing a tile ----------
        self.update_hand_and_latest_tiles()
        # --------------------------------------------------------------------------

        current_playerNo = self.t.who_make_selection()

        if not self.t.get_phase() >= 4 and not self.t.get_phase == 16:
            raise Exception("Current phase is not response phase!!")
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one needs to execute action!!")

        info = {"playerNo": playerNo}
        score_before = self.t.players[playerNo].score

        can_win = False
        win_action_no = 0
        aval_response_actions = self.t.get_response_actions()
        for response_action in aval_response_actions:
            if response_action.action in [mp.BaseAction.Ron, mp.BaseAction.ChanKan, mp.BaseAction.ChanAnKan]:
                can_win = True
                break
            win_action_no += 1

        # ------------- if can win, just win -----------
        if self.force_win and can_win:
            warnings.warn("Can win, automatically choose to win !!")
            self.t.make_selection(win_action_no)
            if self.t.get_selected_action_tile().red_dora:
                self.ron_tile = int(self.t.get_selected_action_tile().tile) * 4
            else:
                self.ron_tile = int(self.t.get_selected_action_tile().tile) * 4 + 3
            self.hand_tiles[playerNo].append(self.ron_tile)
        else:
            if action == PON:
                desired_action_type = mp.BaseAction.Pon
            elif action == MINKAN:
                desired_action_type = mp.BaseAction.Kan
            elif action in [CHILEFT, CHIMIDDLE, CHIRIGHT]:
                desired_action_type = mp.BaseAction.Chi
            elif action == PASS_RESPONSE:
                desired_action_type = mp.BaseAction.Pass
                if can_win:
                    print("见逃！！！")
            elif action == RON:
                desired_action_type = mp.BaseAction.Ron
            else:
                raise ValueError

            response_action_no = 0
            if action in [PON, MINKAN, PASS_RESPONSE, RON]:
                for response_action in aval_response_actions:
                    if response_action.action == desired_action_type:
                        break
                    response_action_no += 1
            else:  # Chi
                chi_no_problem = False
                for response_action in aval_response_actions:
                    if response_action.action == desired_action_type:

                        chi_parents_tiles = aval_response_actions[response_action_no].correspond_tiles

                        if is_consecutive(int(self.latest_tile / 4), int(chi_parents_tiles[0].tile), int(chi_parents_tiles[1].tile)):
                            chi_side = CHILEFT
                            if int(chi_parents_tiles[1].tile) not in [8, 17, 26, 27, 28, 29, 30, 31, 32, 33]:
                                self.non_valid_discard_tiles_id[playerNo] = [int(chi_parents_tiles[1].tile) + 1]
                            else:
                                self.non_valid_discard_tiles_id[playerNo] = []

                        elif is_consecutive(int(chi_parents_tiles[0].tile), int(self.latest_tile / 4), int(chi_parents_tiles[1].tile)):
                            chi_side = CHIMIDDLE

                        elif is_consecutive(int(chi_parents_tiles[0].tile), int(chi_parents_tiles[1].tile), int(self.latest_tile / 4)):
                            chi_side = CHIRIGHT
                            if int(chi_parents_tiles[0].tile) not in [0, 9, 18, 27, 28, 29, 30, 31, 32, 33]:
                                self.non_valid_discard_tiles_id[playerNo] = [int(chi_parents_tiles[0].tile) - 1]
                            else:
                                self.non_valid_discard_tiles_id[playerNo] = []

                        else:
                            chi_side = -1

                        if chi_side == action:
                            chi_no_problem = True
                            break

                    response_action_no += 1

                assert chi_no_problem is True

            self.t.make_selection(response_action_no)
            self.played_a_tile[playerNo] = False

            if action == PON:
                pon_tile_id = int(aval_response_actions[response_action_no].correspond_tiles[0].tile)
                pon_no_problem = False

                for k in range(len(self.hand_tiles[playerNo])):
                    if int(self.hand_tiles[playerNo][k] / 4) == pon_tile_id:
                        pon_tile = self.hand_tiles[playerNo][k]
                        pon_no_problem = True
                        break
                assert pon_no_problem is True
                side_tiles_added_by_naru = [[TileTo136(aval_response_actions[response_action_no].correspond_tiles[0]), 0],
                                            [TileTo136(aval_response_actions[response_action_no].correspond_tiles[1]), 0],
                                            [pon_tile, 1]]
                self.side_tiles[playerNo] += side_tiles_added_by_naru
                self.prev_step_is_naru = True

            elif action == MINKAN:
                kan_tile_id = int(aval_response_actions[response_action_no].correspond_tiles[0].tile)
                side_tiles_added_by_naru = [[kan_tile_id * 4, 0], [kan_tile_id * 4 + 1, 0],
                                            [kan_tile_id * 4 + 2, 0], [kan_tile_id * 4 + 3, 0]]
                self.side_tiles[playerNo] += side_tiles_added_by_naru
                self.prev_step_is_naru = True

            elif action in [CHILEFT, CHIMIDDLE, CHIRIGHT]:

                side_tiles_added_by_naru = [[self.latest_tile, 1]]

                for chi_tile_id in [int(chi_parents_tiles[0].tile), int(chi_parents_tiles[1].tile)]:
                    chi_no_problem = False
                    for k in range(len(self.hand_tiles[playerNo])):
                        if int(self.hand_tiles[playerNo][k] / 4) == chi_tile_id:
                            chi_tile = self.hand_tiles[playerNo][k]
                            side_tiles_added_by_naru.append([chi_tile, 0])
                            chi_no_problem = True
                            break
                    assert chi_no_problem is True

                self.side_tiles[playerNo] += side_tiles_added_by_naru
                self.prev_step_is_naru = True

            elif action == PASS_RESPONSE:
                pass
            else:
                pass

        # ------------ JIESUAN --------------

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            reward = self.get_final_score_change()[playerNo] / self.reward_unit
        else:
            reward = (self.t.players[playerNo].score - score_before) / self.reward_unit

        if self.Phases[self.t.get_phase()] == "GAME_OVER":
            done = 1
            self.final_score_changes.append(self.get_final_score_change())
        else:
            done = 0

        for i in range(4):
            self.scores_before[i] = self.t.players[i].score

        return self.get_state(), reward, done, info

    def get_final_score_change(self):
        rewards = np.zeros([4], dtype=np.float32)

        for i in range(4):
            rewards[i] = self.t.get_result().score[i] - self.scores_reset[i]

        shanten_num = np.zeros([4])
        if self.t.get_remain_tile() == 0 and np.max(rewards) == 0:  # 荒牌流局 计算罚符

            for pid in range(4):
                shanten_num[pid] = shanten.calculate_shanten(TilesConverter.to_34_array(
                    self.hand_tiles[pid] + [st[0] for st in self.side_tiles[pid]]))

            tenpais = np.argwhere(shanten_num == 0)

            if len(tenpais) == 0 or len(tenpais) == 4:
                pass
            elif len(tenpais) == 1:
                for k in range(4):
                    rewards[k] = 3000 if k == tenpais[0][0] else -1000

            elif len(tenpais) == 2:
                for k in range(4):
                    rewards[k] = 1500 if k in [tenpais[0][0], tenpais[1][0]] else -1500

            elif len(tenpais) == 3:
                for k in range(4):
                    rewards[k] = 1000 if k in [tenpais[0][0], tenpais[1][0], tenpais[2][0]] else -3000
            # print("荒牌流局, 向听数:", shanten_num)

        return rewards

    def get_aval_next_states(self, playerNo: int):

        current_playerNo = self.t.who_make_selection()
        if not current_playerNo == playerNo:
            raise Exception("Current player is not the one needs to execute action!!")

        S0 = self.t.get_next_aval_states_matrix_features_frost2(playerNo)
        s0 = self.t.get_next_aval_states_vector_features_frost2(playerNo)
        matrix_features = np.array(S0).reshape([-1, *self.matrix_feature_size])
        vector_features = np.array(s0).reshape([-1, self.vector_feature_size])

        return matrix_features, vector_features

    def tile_to_id(self, tile):
        return int(tile)

    def who_do_what(self):
        if self.t.get_phase() >= 4 and not self.t.get_phase() == 16:  # response phase
            return self.t.who_make_selection(), "response"
        elif self.t.get_phase() < 4:  # action phase
            return self.t.who_make_selection(), "play"

    def render(self, mode='human'):
        print(self.t.get_selected_base_action().action)


import pymahjong as pm
import numpy as np
import platform
import warnings
import time

from env_mahjong import EnvMahjong4
import pymahjong as mp
import numpy as np
from copy import deepcopy

np.set_printoptions(threshold=np.inf)


# t.game_init()

obs = np.zeros([34, 81], dtype=np.int8)

# ---------------- Test ----------------------
playerNo = np.random.randint(0, 4)




winds = ['east', 'south', 'west', 'north']

oya = str(np.random.randint(0, 4))
game_wind = winds[np.random.randint(0, 4)]
#
# t = pm.Table()
# t.game_init_with_metadata({"oya": oya, "wind": game_wind})
#
# pm.encode_table(t, 0, obs)
# print(np.array2string(obs))


env_test = EnvMahjong4()

times = 100


steps_taken = 0
max_steps = 1000
# -------------- Return vs. pretrained player -------------
start_time = time.time()
game = 0
trials = 0
payoffs_array = []
winning_counts = []
deal_in_counts = []


wrong_dimensions = np.zeros([81])

while game < times:
    trials += 1
    # try:
    # reset each episode

    env_test.reset(game % 4, game_wind)

    payoffs = np.zeros([4])

    for tt in range(max_steps):

        curr_pid = env_test.get_curr_player_id()
        valid_actions = env_test.get_valid_actions(nhot=False)


        if len(valid_actions) == 1:
            env_test.t.make_selection(0)
        else:
            action_mask = env_test.get_valid_actions(nhot=True)


            # --------------- Check encoding !!!!!!!! ---------------


            dq_obs = env_test.get_obs(curr_pid).astype(np.int8)[:81, :]
            obs = obs - obs
            pm.encode_table(env_test.t, curr_pid, obs)

            ag_obs = deepcopy(obs).swapaxes(0, 1)[:81, :]

            if curr_pid == 0 and np.any(dq_obs != ag_obs):
                print("wrong encoding, different elements = {}".format(np.sum(dq_obs != ag_obs)))
                # print("feature dimensions that are wrong:", np.argwhere(np.sum(abs(dq_obs - ag_obs), axis=1)).flatten())
                # print(dq_obs)
                # print(ag_obs)
                wrong_dimensions[np.argwhere(np.sum(abs(dq_obs - ag_obs), axis=1)).flatten()] = 1

            # --------------------------------------------------


            a = np.random.randint(0, len(valid_actions))
            sp, r, done, _ = env_test.step(curr_pid, valid_actions[a])
            steps_taken += 1

        if done or env_test.t.get_phase() == 16:

            payoffs = payoffs + np.array(env_test.get_payoffs())

            curr_wins = np.zeros([4])
            curr_deal_ins = np.zeros([4])

            if env_test.t.get_result().result_type == mp.ResultType.RonAgari:
                for ii in range(4):  # consider multiple players Agari
                    if payoffs[ii] > 0:
                        curr_wins[ii] = 1
                curr_deal_ins[np.argmin(payoffs)] = 1
            elif env_test.t.get_result().result_type == mp.ResultType.TsumoAgari:
                curr_wins[np.argmax(payoffs)] = 1

            if game % 1 == 0:
                print("game", game, payoffs)

            # results
            payoffs_array.append(payoffs)
            winning_counts.append(curr_wins)
            deal_in_counts.append(curr_deal_ins)
            game += 1
            break


print("feature dimensions that are wrong:", np.argwhere(wrong_dimensions).flatten())
print("Test {} games, spend {} s".format(times, time.time() - start_time))


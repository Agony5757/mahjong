import time
import env_pymahjong
import numpy as np
import torch
import pymahjong as pm
import os

def test(num_games=100):

    env = env_pymahjong.MahjongEnv()

    start_time = time.time()
    game = 0
    success_games = 0

    stat = {}
    stat["agari_games"] = np.zeros([4], dtype=np.float32)
    stat["tsumo_games"] = np.zeros([4], dtype=np.float32)
    stat["agari_points"] = np.zeros([4], dtype=np.float32)
    stat["houjyuu_games"] = np.zeros([4], dtype=np.float32)

    while game < num_games:

        try:

            env.reset(oya=game % 4, game_wind="east")

            while not env.is_over():

                curr_player_id = env.get_curr_player_id()

                # --------- get decision information -------------

                valid_actions_mask = env.get_valid_actions(nhot=True)

                executor_obs = env.get_obs(curr_player_id)

                # oracle_obs = env.get_oracle_obs(curr_player_id)
                # full_obs = env.get_full_obs(curr_player_id)
                # full_obs = concat([executor_obs, oracle_obs], axis=0)

                # --------- make decision -------------

                a = np.random.choice(np.argwhere(valid_actions_mask).reshape([-1]))

                env.step(curr_player_id, a)

            # ----------------------- get result ---------------------------------

            payoffs = np.array(env.get_payoffs())
            if verbose >= 1:
                print("Game {}, payoffs: {}".format(game, payoffs))

            success_games += 1
            game += 1

        except Exception as inst:
            game += 1
            time.sleep(0.1)
            print("-------------- execption in game {} -------------------------".format(game))
            print(inst)
            env.render()
            continue

    print("Total {} random-play games, {} without error, takes {} s".format(num_games, success_games, time.time() - start_time))


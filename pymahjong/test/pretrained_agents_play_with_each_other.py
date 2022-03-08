import time
import env_pymahjong
import numpy as np
import torch


def play_mahjong(agent, num_games=100, verbose=1):

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

        # try:
        env.reset()

        while not env.is_over():

            curr_player_id = env.get_curr_player_id()

            # --------- get decision information -------------

            valid_actions_mask = env.get_valid_actions(curr_player_id, nhot=True)
            executor_obs = env.get_obs(curr_player_id)

            oracle_obs = env.get_oracle_obs(curr_player_id)
            # full_obs = env.get_full_obs(curr_player_id)
            # full_obs = concat([executor_obs, oracle_obs], axis=0)

            # --------- make decision -------------

            if agent == "random":
                a = np.random.choice(np.argwhere(valid_actions_mask).reshape([-1]))
            else:
                a = agent.select(executor_obs, oracle_obs, action_mask=valid_actions_mask, greedy=True)

            env.step(a)

        # ----------------------- get result ---------------------------------

        payoffs = env.get_payoffs()
        if verbose >= 2:
            print("Game {}, result: {}".format(game, payoffs))

        for winner in env.t.get_result().winner:
            stat["agari_points"][winner] += payoffs[winner]
            stat["agari_games"][winner] += 1

        if len(env.t.get_result().loser) == 1:
            stat["houjyuu_games"][env.t.get_result().loser] += 1
        else:
            stat["tsumo_games"][env.t.get_result().winner] += 1

        success_games += 1
        game += 1

        if verbose >= 1 and game % 100 == 0:
            print("------------------------ {} games statistics -----------------------".format(success_games))
            print("win rate:                    ", np.array2string(100 * stat["agari_games"] / success_games, precision=2, separator="  "))
            print("tsumo rate:                  ", np.array2string(100 * stat["tsumo_games"] / stat["agari_games"], precision=2, separator="  "))
            print("houjyuu rate:                ", np.array2string(100 * stat["houjyuu_games"] / success_games, precision=2, separator="  "))
            print("average agari points (x100): ", np.array2string(0.01 * stat["agari_points"] / stat["agari_games"], precision=2, separator="  "))
            # print("----------------------------------------------------------------------")
        # except:
        #     game += 1
        #     continue

    print("Total {} game, {} without error, takes {} s".format(num_games, success_games, time.time() - start_time))


if __name__ == "__main__":

    agent = torch.load("./mahjong_VLOG_CQL_0.model", map_location='cpu')
    agent.device = torch.device('cpu')
    # agent = "random"
    play_mahjong(agent, num_games=100000, verbose=1)

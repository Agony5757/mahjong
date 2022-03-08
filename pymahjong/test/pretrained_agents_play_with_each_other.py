import time
import env_pymahjong
import numpy as np


def play_mahjong(agent, num_games=100):

    env = env_pymahjong.MahjongEnv()

    start_time = time.time()
    game = 0
    success_games = 0

    while game < num_games:

        # try:
        env.reset()

        while not env.is_over():

            curr_player_id = env.get_curr_player_id()

            # --------- get decision information -------------

            valid_actions_mask = env.get_valid_actions(curr_player_id, nhot=True)
            executor_obs = env.get_obs(curr_player_id)

            # oracle_obs = env.get_oracle_obs(curr_player_id)
            # full_obs = env.get_full_obs(curr_player_id)
            # full_obs = concat([executor_obs, oracle_obs], axis=0)

            # --------- make decision -------------

            if agent == "random":
                a = np.random.choice(np.argwhere(valid_actions_mask).reshape([-1]))
            else:
                a = agent.select(executor_obs, valid_actions_mask)

            env.step(a)

        # if np.sum(env.get_payoffs() < 0) == 2 and np.sum(env.get_payoffs() > 0) == 2:

        print("Game {}, result: {}".format(game, env.get_payoffs()))

        success_games += 1
        game += 1
        # except:
        #     continue

    print("Total {} game, {} without error, takes {} s".format(num_games, success_games, time.time() - start_time))


if __name__ == "__main__":

    play_mahjong("random", num_games=10000)

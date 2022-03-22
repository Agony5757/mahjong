import time
import numpy as np
from .env_pymahjong import MahjongEnv, SingleAgentMahjongEnv


def test(num_games=100):

    env = MahjongEnv()

    start_time = time.time()
    game = 0
    success_games = 0

    while game < num_games:

        try:

            env.reset(oya=game % 4, game_wind="east", debug_mode=2)

            while not env.is_over():

                curr_player_id = env.get_curr_player_id()

                # --------- get decision information -------------

                valid_actions_mask = env.get_valid_actions(nhot=True)

                executor_obs = env.get_obs(curr_player_id)

                # oracle_obs = env.get_oracle_obs(curr_player_id)
                # full_obs = env.get_full_obs(curr_player_id)
                # full_obs = np.concatenate([executor_obs, oracle_obs], axis=0)

                # --------- make decision -------------

                a = np.random.choice(np.argwhere(valid_actions_mask).reshape([-1]))

                env.step(curr_player_id, a)

            # ----------------------- get result ---------------------------------

            payoffs = np.array(env.get_payoffs())
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

    print("Total {} random-play games, {} games without error, takes {} s".format(num_games, success_games, time.time() - start_time))


def test_with_pretrained(opponent_agent="vlog-bc", num_games=100):

    env = SingleAgentMahjongEnv(opponent_agent)

    start_time = time.time()
    success_games = 0

    for game in range(num_games):

        try:
            env.reset()
            payoff = 0

            while True:

                valid_actions = env.get_valid_actions()

                a = np.random.choice(valid_actions)

                obs, reward, done, _ = env.step(a)

                payoff = payoff + reward  # reward may != 0 only when done

                if done:
                    success_games += 1
                    print("Game {}, agent payoff {}".format(game, payoff))
                    break

        except Exception as inst:
            game += 1
            time.sleep(0.1)
            print("-------------- execption in game {} -------------------------".format(game))
            print(inst)
            env.render()
            continue

    print("Total {} random-play games with pretrained VLOG models as opponents, {} games without error, takes {} s".format(num_games, success_games, time.time() - start_time))

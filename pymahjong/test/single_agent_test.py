import env_pymahjong
import numpy as np


env = env_pymahjong.SingleAgentMahjongEnv(opponent_agent="vlog-bc")


for game in range(100000):

    env.reset()

    payoff = 0

    while True:

        valid_actions = env.get_valid_actions()

        a = np.random.choice(valid_actions)

        obs, reward, done, _ = env.step(a)

        payoff = payoff + reward  # reward may != 0 only when done

        if done:
            print("game {}, payoff {}".format(game, payoff))
            break

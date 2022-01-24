from .env_mahjong import *
import numpy as np

def test():
    env = EnvMahjong()
    max_steps = 1000

    times = 10

    game = 0

    while game < times:
        # reset each episode
        sp = env.reset(0, 'east')  # oya ID and game wind
        
        for tt in range(max_steps):
            # print(tt)
            curr_pid = env.get_curr_player_id()  # Which player to play
            valid_actions = env.get_valid_actions(nhot=False)  # List[int] of valid actions
            action_mask = env.get_valid_actions(nhot=True)  # n-hot vector of valid actions

            # x_executor = env.get_obs(curr_pid)
            # x_oracle = np.concatenate([x_executor, env.get_oracle_obs(curr_pid)], axis=-2)

            # select action
            a = np.random.choice(env.action_space.n, p=action_mask / sum(action_mask))

            sp, r, done, _ = env.step(curr_pid, a)

            if env.has_done():
                print("result:", np.array(env.get_payoffs()))
                game += 1
                break


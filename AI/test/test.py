import MahjongPy
from naiveAI import AgentNaive, NMnaive
import tensorflow as tf
import numpy as np
from copy import deepcopy
from buffer import PrioritizedReplayBuffer

sess = tf.InteractiveSession()



if __name__ == '__main__':

    nn = NMnaive(sess)
    env = EnvMahjong()

    # before the train start, create 4 agents.
    memory = PrioritizedReplayBuffer(state_dim=34*4, action_dim=34)
    agent = AgentNaive(nn, memory)
    n_games = 2

    for n in range(n_games):
        done = 0
        this_state = env.reset()
        step = 0
        while not done and step < 10000:
            next_aval_states = env.get_aval_actions()
            action, policy = agent.select(next_aval_states)
            next_state, score, done, info = env.step(action)
            agent.remember(this_state, action, next_state, score, done, next_aval_states, policy)
            agent.learn()
            this_state = deepcopy(next_state)
            step += 1
            print("Game {}, step {}".format(n, step))
            print(info)




# In[ ]:





# In[ ]:






# coding: utf-8

# In[ ]:


from naiveAI import AgentPER, NMnaive
import tensorflow as tf
import numpy as np
from copy import deepcopy
from buffer import SimpleMahjongBufferPER
import gym
import MahjongPy as mp
from wrapper import EnvMahjong
import scipy.io as sio
from datetime import datetime

now = datetime.now()
datetime_str = now.strftime("%Y%m%d-%H%M%S")

sess = tf.InteractiveSession()

nn = NMnaive(sess)
env = EnvMahjong()

memory = SimpleMahjongBufferPER(size=1024)

agents = [AgentPER(nn, memory, greedy=10.0 ** np.random.uniform(-4, -1)) for _ in range(4)]



# # Note:
# 
# ### This is for AI agents those only cares about itself, i.e., no defense. Therefore, there is no negative reward.

# In[ ]:



n_games = 1000000

print("Start!")

for n in range(n_games):
    
    print("\r Game {}".format(n), end='')
    
    episode_dones = [[], [], [], []]
    episode_states = [[], [], [], []]
    episode_rewards = [[], [], [], []]
    
    done = 0
#     policies = np.zeros([4,], dtype=np.int32)
    actions = np.zeros([4,], dtype=np.int32)
    rs = np.zeros([4,], dtype=np.float32)
    
    this_states = env.reset()  ## for all players
    
    next_aval_states = deepcopy(this_states)
    next_states = [[], [], [], []]
    
    step = 0
    
    while not done and step < 10000:

        who, what = env.who_do_what()
        
        ## make selection
        if what == "play":
            next_aval_states = env.get_aval_next_states(who)  ## for a single player
            action, policy = agents[who].select(next_aval_states)
            next_states[who], r, done, _ = env.step_play(action, playerNo=who)
            
            next_states[who] = env.get_state_(who)
            
            episode_dones[who].append(done)
            episode_states[who].append(this_states[who])
            episode_rewards[who].append(min(0., r))
                        
#             agents[who].learn()
            
            this_states[who] = deepcopy(next_states[who])
            
        elif what == "response":
            next_aval_states_all = []
            policies = [[], [], [], []]
            for i in range(4):
                next_aval_states = env.get_aval_next_states(i)
                next_aval_states_all.append(next_aval_states)
                actions[i], policies[i] = agents[i].select(np.reshape(next_aval_states, [-1, 34, 4, 1]))
            
                next_states[i], rs[i], done, _ = env.step_response(actions[i], playerNo=i)
                ## Note: next_states is agent's prediction, but not the true one
                
            # table change after all players making actions

            for i in range(4):
                next_states[i] = env.get_state_(i)
                episode_dones[i].append(done)
                episode_states[i].append(this_states[i])
                episode_rewards[i].append(min(0., rs[i]))
#                 agents[i].learn()
        
            ## next step
            for i in range(4):
                this_states[i] = deepcopy(next_states[i])
            
        step += 1
        
#         print("Game {}, step {}".format(n, step))
#         print(env.get_phase_text())
        
        if done:      
            final_score_change = env.get_final_score_change()
            for i in range(4):
                episode_states[i].append(env.get_state_(i))
                episode_dones[i][-1] = 1
                #### Disable the following line if not care others
#                 episode_rewards[i][-1] = final_score_change[i]
                ##################################################
            
            if not np.max(final_score_change) == 0: 
                agents[i].remember_episode(episode_states[i], episode_rewards[i], episode_dones[i], weight=np.max(final_score_change))
                print(' ')
                print(env.t.get_result().result_type)
            else:
                if np.random.rand() < 0.002:
                    agents[i].remember_episode(episode_states[i], episode_rewards[i], episode_dones[i], weight=0)
                    print(' ')
                    print(env.t.get_result().result_type)
                    
            for n_train in range(15):
                for i in range(4):
                    agents[i].learn(env.symmetric_hand, care_others=False)
            
        
data = {"rons": env.rons}
sio.savemat("./PERrons" + datetime_str + ".mat", data)


# In[ ]:





# In[ ]:





# In[ ]:






# coding: utf-8


from aiFrost2 import AgentFrost2, MahjongNetFrost2
import tensorflow as tf
import numpy as np
from copy import deepcopy
from buffer import MahjongBufferFrost2
import MahjongPy as mp
from wrapper import EnvMahjong2
import scipy.io as sio
from datetime import datetime
import time

now = datetime.now()
datetime_str = now.strftime("%Y%m%d-%H%M%S")

graphs = [tf.Graph(), tf.Graph(), tf.Graph(), tf.Graph() ]

env = EnvMahjong2()

num_tile_type = env.matrix_feature_size[0]
num_each_tile = env.matrix_feature_size[1]
num_vf = env.vector_feature_size

agents = [AgentFrost2(nn=MahjongNetFrost2(graphs[i], agent_no=i, num_tile_type=num_tile_type, num_each_tile=num_each_tile, num_vf=num_vf),
                      memory=MahjongBufferFrost2(size=4096, num_tile_type=num_tile_type, num_each_tile=num_each_tile, num_vf=num_vf),
                      greedy=10.0 ** np.random.uniform(-1, 1),
                      num_tile_type=num_tile_type, num_each_tile=num_each_tile, num_vf=num_vf)
          for i in range(4)]


episode_start = 256
episode_savebuffer = 1024
mu_size = agents[0].memory.max_action_num
max_steps = agents[0].memory.episode_length


# ##  以下的代码可以让Agent读取保存的对局buffer， 如果comment掉就可以让Agent从头开始训练

# In[ ]:


# # example 
# for i in range(4):
#     buffer_path =  "./buffer/Agent{}".format(i) + "-MahjongBufferFrost220190612-140356.pkl"
#     agents[i].memory.load(buffer_path)


# ##  以下的代码可以让Agent读取保存的网络， 如果comment掉就可以让Agent从头开始训练

# In[ ]:


# # example 
# for i in range(4):
#     model_path =  "../log/Agent{}".format(i) + "-20190531-150059-Game0/naiveAI.ckpt"
#     agents[i].nn.restore(model_path)
    


# # Note:
# 

# In[ ]:




n_games = 1000000

print("Start!")

for n in range(n_games):
#     try:
    if (n + 1) % 10000 == 0:
        for i in range(4):
            agents[i].nn.save(model_dir="Agent{}-".format(i) + datetime_str + "-Game{}".format(
                n - 1))  # save network parameters every 10000 episodes

    for i in range(4):
        if agents[i].memory.filled_size >= episode_savebuffer and agents[i].memory.tail % episode_savebuffer == 0:
            agents[i].memory.save("./buffer/Agent{}-".format(i) + "MahjongBufferFrost2" + datetime_str + ".pkl")

    print("\r Game {}".format(n), end='')

    episode_dones = np.zeros([4, max_steps], dtype=np.float16)
    episode_next_matrix_features = np.zeros([4, max_steps, mu_size, num_tile_type, num_each_tile], dtype=np.float16)
    episode_next_vector_features = np.zeros([4, max_steps, mu_size, num_vf], dtype=np.float16)
    episode_num_aval_actions = np.zeros([4, max_steps], dtype=np.int16)  # number of available actions
    episode_rewards = np.zeros([4, max_steps], dtype=np.float32)
    episode_actions = np.zeros([4, max_steps], dtype=np.int32)
    episode_policies = np.zeros([4, max_steps, mu_size], dtype=np.float32)

    done = 0
    #     policies = np.zeros([4,], dtype=np.int32)
    actions = np.zeros([4, ], dtype=np.int32)
    rs = np.zeros([4, ], dtype=np.float32)
    aval_actions_lens = np.zeros([4, ], dtype=int)

    this_states = env.reset()  ## for all players

    #     next_aval_states = deepcopy(this_states)

    aval_next_matrix_features = np.zeros([4, mu_size, num_tile_type, num_each_tile], dtype=np.float16)
    aval_next_vector_features = np.zeros([4, mu_size, num_vf], dtype=np.float16)

    next_states = [[], [], [], []]

    step = 0
    agent_step = [0, 0, 0, 0]

    while not done and step < 1000:

        who, what = env.who_do_what()

        ## make selection
        if what == "play":
            ###################### Play a tile #######################
            ###### 能和则和，能立直则立直 ############
            aval_actions = env.t.get_self_actions()
            good_actions = []

            #             if agents[who].memory.filled_size < episode_start:  # For collecting data only
            for a in range(len(aval_actions)):
                if aval_actions[a].action == mp.Action.Riichi:
                    good_actions.append(a)

                if aval_actions[a].action == mp.Action.Tsumo:
                    good_actions.append(a)
            #######################################

            next_aval_matrix_states, next_aval_vector_states = env.get_aval_next_states(who)  ## for a single player
            next_aval_states = (next_aval_matrix_states, next_aval_vector_states)

            if len(good_actions) > 0:
                good_actions = np.reshape(good_actions, [-1, ])
                a_in_good_as, policy = agents[who].select([np.array(next_aval_matrix_states)[good_actions],
                                                           np.array(next_aval_vector_states)[good_actions]])
                action = good_actions[a_in_good_as]
                tmp = np.zeros([mu_size, ], dtype=np.float32)
                tmp[good_actions] = policy
                policy = deepcopy(tmp)
            else:
                action, policy = agents[who].select(next_aval_states)
                # covert policy to vector (with padding)
                tmp = np.zeros([mu_size, ], dtype=np.float32)
                tmp[:np.shape(policy)[0]] = policy
                policy = deepcopy(tmp)

            next_states[who], r, done, _ = env.step_play(action, playerNo=who)

            episode_dones[who, agent_step[who]] = done
            episode_next_matrix_features[who, agent_step[who], 0:len(aval_actions)] = next_aval_matrix_states
            episode_next_vector_features[who, agent_step[who], 0:len(aval_actions)] = next_aval_vector_states
            episode_num_aval_actions[who, agent_step[who]] = len(aval_actions)
            episode_rewards[who, agent_step[who]] = r
            episode_actions[who, agent_step[who]] = action
            episode_policies[who, agent_step[who]] = policy
            agent_step[who] += 1

            this_states[who] = deepcopy(next_states[who])


        elif what == "response":
            policies = [np.zeros([mu_size, ], dtype=np.float32) for _ in range(4)]
            for i in range(4):
                next_aval_matrix_states, next_aval_vector_states = env.get_aval_next_states(i)  ## for a single player
                next_aval_states = (next_aval_matrix_states, next_aval_vector_states)

                ######################## 能和则和，能立直则立直 ##############
                aval_actions = env.t.get_response_actions()

                aval_actions_lens[i] = len(aval_actions)
                episode_next_matrix_features[i, agent_step[i], 0:aval_actions_lens[i]] = next_aval_matrix_states
                episode_next_vector_features[i, agent_step[i], 0:aval_actions_lens[i]] = next_aval_vector_states

                good_actions = []

                #                 if agents[i].memory.filled_size < episode_start:  # For collecting data only
                for a in range(len(aval_actions)):
                    if aval_actions[a].action == mp.Action.Ron:
                        good_actions.append(a)

                    if aval_actions[a].action == mp.Action.ChanKan:
                        good_actions.append(a)

                    if aval_actions[a].action == mp.Action.ChanAnKan:
                        good_actions.append(a)
                ##########################################################
                if len(good_actions) > 0:
                    good_actions = np.reshape(good_actions, [-1, ])
                    a_in_good_as, policies[i] = agents[i].select([np.array(next_aval_matrix_states)[good_actions],
                                                                  np.array(next_aval_vector_states)[good_actions]])
                    actions[i] = good_actions[a_in_good_as]
                    # covert policy to vector (with padding)
                    tmp = np.zeros([mu_size, ], dtype=np.float32)
                    tmp[good_actions] = policies[i]
                    policies[i] = deepcopy(tmp)

                else:
                    actions[i], policies[i] = agents[i].select(next_aval_states)

                    # covert policy to vector (with padding)
                    tmp = np.zeros([mu_size, ], dtype=np.float32)
                    tmp[:np.shape(policies[i])[0]] = policies[i]
                    policies[i] = deepcopy(tmp)

                next_states[i], rs[i], done, _ = env.step_response(actions[i], playerNo=i)

                ## Note: next_states is agent's prediction, but not the true one

            # table change after all players making actions

            for i in range(4):
                episode_num_aval_actions[i, agent_step[i]] = aval_actions_lens[i]
                episode_dones[i, agent_step[i]] = done
                episode_rewards[i, agent_step[i]] = rs[i]
                episode_actions[i, agent_step[i]] = actions[i]
                episode_policies[i, agent_step[i]] = policies[i]
                agent_step[i] += 1

            ## next step
            for i in range(4):
                this_states[i] = deepcopy(next_states[i])

        step += 1
        #         if done or step == max_steps:
        #             print('done = {}'.format(done))
        #             print(env.get_phase_text())


        #         print("Game {}, step {}".format(n, step))


        if env.t.get_phase() == 16:  # GAME_OVER

            final_score_change = env.get_final_score_change()

            for i in range(4):

                agents[i].statistics(i, env.t.get_result(), env.get_final_score_change(), env.t.turn,
                                     env.t.players[i].riichi, env.t.players[i].menchin)

                if agent_step[i] >= 1:  # if not 1st turn end
                    episode_dones[i, agent_step[i] - 1] = 1
                    episode_rewards[i, agent_step[i] - 1] = final_score_change[i]

            if not np.max(final_score_change) == 0:  ## score change
                for i in range(4):
                    agents[i].remember_episode(episode_num_aval_actions[i],
                                               episode_next_matrix_features[i],
                                               episode_next_vector_features[i],
                                               episode_rewards[i],
                                               episode_dones[i],
                                               episode_actions[i],
                                               episode_policies[i],
                                               weight=0)
                print(' ')
                print(env.t.get_result().result_type, end='')
                print(": Totally {} steps".format(step))

                try:
                    with open("./Paipu/" + datetime_str + "game{}".format(n) + ".txt", 'w') as fp:
                        fp.write(mp.GameLogToString(env.t.game_log).decode('GBK'))
                except:
                    pass

            else:
                if np.random.rand() < 0.0025 + (n / 500000) ** 2:  ## no score change
                    for i in range(4):
                        agents[i].remember_episode(episode_num_aval_actions[i],
                                                   episode_next_matrix_features[i],
                                                   episode_next_vector_features[i],
                                                   episode_rewards[i],
                                                   episode_dones[i],
                                                   episode_actions[i],
                                                   episode_policies[i],
                                                   weight=0)
                    print(' ')
                    print(env.t.get_result().result_type, end='')
                    print(": Totally {} steps".format(step))

            for n_train in range(4):
                for i in range(4):
                    agents[i].learn(env.symmetric_matrix_features, episode_start=episode_start,
                                    care_lose=False, logging=True)
#     except:
#         pass


data = {"rons": env.final_score_changes, "p0_stat": agents[0].stat, "p1_stat": agents[1].stat,
        "p2_stat": agents[2].stat, "p3_stat": agents[3].stat, }
sio.savemat("./final_score_changes" + datetime_str + ".mat", data)

# In[ ]:





from aiFrost2 import AgentFrost2, MahjongNetFrost2
import tensorflow as tf
import numpy as np
from copy import deepcopy
from buffer import MahjongBufferFrost2
import MahjongPy as mp
from wrapper import EnvMahjong2
import scipy.io as sio
from datetime import datetime

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
episode_savebuffer = 128
mu_size = 40

max_steps = 150

# # example
# for i in range(4):
#     buffer_path =  "./buffer/Agent{}".format(i) + "-MahjongBufferFrost220190531-150059.pkl"
#     agents[i].memory.load(buffer_path)

# # example
# for i in range(4):
#     model_path = "../log/Agent{}".format(i) + "-20190531-150059-Game0/naiveAI.ckpt"
#     agents[i].nn.restore(model_path)

n_games = 1000000

print("Start!")

for n in range(n_games):

    if n % 10000 == 0:
        for i in range(4):
            agents[i].nn.save(model_dir="Agent{}-".format(i) + datetime_str + "-Game{}".format(
                n))  # save network parameters every 10000 episodes

    for i in range(4):
        if agents[i].memory.filled_size >= episode_savebuffer and agents[i].memory.tail % episode_savebuffer == 0:
            agents[i].memory.save("./buffer/Agent{}-".format(i) + "MahjongBufferFrost2" + datetime_str + ".pkl")

    print("\r Game {}".format(n), end='')

    episode_dones = np.zeros([4, max_steps], dtype=np.float16)
    episode_matrix_features = np.zeros([4, max_steps, num_tile_type, num_each_tile], dtype=np.float16)
    episode_vector_features = np.zeros([4, max_steps, num_vf], dtype=np.float16)
    episode_rewards = np.zeros([4, max_steps], dtype=np.float32)
    episode_actions = np.zeros([4, max_steps], dtype=np.int32)
    episode_policies = np.zeros([4, max_steps, mu_size], dtype=np.float32)


    done = 0
    #     policies = np.zeros([4,], dtype=np.int32)
    actions = np.zeros([4, ], dtype=np.int32)
    rs = np.zeros([4, ], dtype=np.float32)

    this_states = env.reset()  ## for all players

    next_aval_states = deepcopy(this_states)

    next_matrix_features = np.zeros([4, num_tile_type, num_each_tile], dtype=np.float16)
    next_vector_features = np.zeros([4, num_vf], dtype=np.float16)

    next_states = [[], [], [], []]

    step = 0
    agent_step = [0, 0, 0, 0]

    while not done and step < max_steps:

        who, what = env.who_do_what()

        ## make selection
        if what == "play":

            ######################## Draw a tile #####################

            next_states[who], r, done, _ = env.step_draw(playerNo=who)

            episode_dones[who, agent_step[who]] = done
            episode_matrix_features[who, agent_step[who]] = this_states[who][0]
            episode_vector_features[who, agent_step[who]] = this_states[who][1]
            episode_rewards[who, agent_step[who]] = r
            episode_actions[who, agent_step[who]] = 0
            policy = np.zeros([mu_size, ], dtype=np.float32)
            policy[0] += 1.
            episode_policies[who, agent_step[who]] = policy  # only 1 available action (draw)

            agent_step[who] += 1

            this_states[who] = deepcopy(next_states[who])

            ###################### Play a tile #######################
            ###### 能和则和，能立直则立直 ############
            aval_actions = env.t.get_self_actions()
            good_actions = []

            if agents[who].memory.filled_size < episode_start:  # For collecting data only
                for a in range(len(aval_actions)):
                    if aval_actions[a].action == mp.Action.Riichi:
                        good_actions.append(a)

                    if aval_actions[a].action == mp.Action.Tsumo:
                        good_actions.append(a)
            #######################################

            next_aval_states = env.get_aval_next_states(who)  ## for a single player

            if len(good_actions) > 0:
                good_actions = np.reshape(good_actions, [-1, ])
                a_in_good_as, policy = agents[who].select([np.array(next_aval_states[0])[good_actions],
                                                           np.array(next_aval_states[1])[good_actions]])
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

            next_states[who] = env.get_state_(who)

            episode_dones[who, agent_step[who]] = done
            episode_matrix_features[who, agent_step[who]] = this_states[who][0]
            episode_vector_features[who, agent_step[who]] = this_states[who][1]
            episode_rewards[who, agent_step[who]] = r
            episode_actions[who, agent_step[who]] = action
            episode_policies[who, agent_step[who]] = policy
            agent_step[who] += 1

            this_states[who] = deepcopy(next_states[who])

        # step += 2

        elif what == "response":
            policies = [np.zeros([mu_size, ], dtype=np.float32) for _ in range(4)]
            for i in range(4):
                next_aval_states = env.get_aval_next_states(i)

                ######################## 能和则和，能立直则立直 ##############
                aval_actions = env.t.get_response_actions()
                good_actions = []

                if agents[i].memory.filled_size < episode_start:  # For collecting data only
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
                    a_in_good_as, policies[i] = agents[i].select([np.array(next_aval_states[0])[good_actions],
                                                                  np.array(next_aval_states[1])[good_actions]])
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
                episode_dones[i, agent_step[i]] = done
                episode_matrix_features[i, agent_step[i]] = this_states[i][0]
                episode_vector_features[i, agent_step[i]] = this_states[i][1]
                episode_rewards[i, agent_step[i]] = rs[i]
                episode_actions[i, agent_step[i]] = actions[i]
                episode_policies[i, agent_step[i]] = policies[i]
                agent_step[i] += 1
            ## next step
            for i in range(4):
                this_states[i] = deepcopy(next_states[i])

        step += 1

        # print("Game {}, step {}".format(n, step))
        #         print(env.get_phase_text())

        if done:



            final_score_change = env.get_final_score_change()

            for i in range(4):

                agents[i].statistics(i, env.t.get_result(), env.get_final_score_change(), env.t.turn,
                                     env.t.players[i].riichi, env.t.players[i].menchin)

                current_state = env.get_state_(i)
                episode_matrix_features[i, agent_step[i]] = current_state[0]
                episode_vector_features[i, agent_step[i]] = current_state[1]

                if len(episode_dones[i]) >= 1:  # if not 1st turn end
                    episode_dones[i, -1] = 1


            if not np.max(final_score_change) == 0:  ## score change
                for i in range(4):
                    agents[i].remember_episode(episode_matrix_features[i, 0: agent_step[i]],
                                               episode_vector_features[i, 0: agent_step[i]],
                                               episode_rewards[i, 0: agent_step[i]],
                                               episode_dones[i, 0: agent_step[i]],
                                               episode_actions[i, 0: agent_step[i]],
                                               episode_policies[i, 0: agent_step[i]],
                                               weight=0)
                print(' ')
                print(env.t.get_result().result_type, end='')
                print(": Totally {} steps".format(np.shape(episode_dones[0])[0]))

                try:
                    with open("./Paipu/" + datetime_str + "game{}".format(n) + ".txt", 'w') as fp:
                        fp.write(mp.GameLogToString(env.t.game_log).decode('GBK'))
                except:
                    pass

            else:
                if np.random.rand() < 0.01 + n / 500000:  ## no score change
                    for i in range(4):
                        agents[i].remember_episode(episode_matrix_features[i, 0: agent_step[i]],
                                                   episode_vector_features[i, 0: agent_step[i]],
                                                   episode_rewards[i, 0: agent_step[i]],
                                                   episode_dones[i, 0: agent_step[i]],
                                                   episode_actions[i, 0: agent_step[i]],
                                                   episode_policies[i, 0: agent_step[i]],
                                                   weight=0)
                    print(' ')
                    print(env.t.get_result().result_type, end='')
                    print(": Totally {} steps".format(np.shape(episode_dones[0])[0]))


            for n_train in range(5):
                for i in range(4):
                    agents[i].learn(env.symmetric_matrix_features, episode_start=episode_start,
                                    care_lose=False, logging=True, batch_size=32)


data = {"rons": env.final_score_changes, "p0_stat": agents[0].stat, "p1_stat": agents[1].stat,
        "p2_stat": agents[2].stat, "p3_stat": agents[3].stat, }
sio.savemat("./final_score_changes" + datetime_str + ".mat", data)

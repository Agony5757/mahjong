#!/usr/bin/env python
# coding: utf-8

from naiveAI import AgentNaive, NMnaive
import tensorflow as tf
import numpy as np
from copy import deepcopy
from buffer import SimpleMahjongBuffer
from wrapper import EnvMahjong
import scipy.io as sio
from datetime import datetime

now = datetime.now()
datetime_str = now.strftime("%Y%m%d-%H%M%S")

sess = tf.InteractiveSession()

nn = NMnaive(sess)
env = EnvMahjong()
memory = SimpleMahjongBuffer(size=100000)

agents = [AgentNaive(nn, memory, greedy=10.0 ** np.random.uniform(-4, -1)) for _ in range(4)]


n_games = 3000

for n in range(n_games):
    done = 0
    #     policies = np.zeros([4,], dtype=np.int32)
    actions = np.zeros([4, ], dtype=np.int32)
    rs = np.zeros([4, ], dtype=np.float32)

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

            agents[who].remember(this_states[who], action, next_states[who], r, done, next_aval_states, policy)

            agents[who].learn()

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
                agents[i].remember(this_states[i], actions[i], next_states[i], rs[i], done, next_aval_states_all[i],
                                   policies[i])
                agents[i].learn()

            ## next step
            for i in range(4):
                this_states[i] = deepcopy(next_states[i])

        step += 1

        #         print("Game {}, step {}".format(n, step))
        #         print(env.get_phase_text())
        if done:
            print(env.t.get_result().result_type)

        data = {"ron": env.rons}
        sio.savemat("./rons" + datetime_str + ".mat", data)

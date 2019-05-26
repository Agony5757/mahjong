import tensorflow as tf
from buffer import MahjongBufferFrost2
import numpy as np
from datetime import datetime
import scipy.special as scisp
import MahjongPy as mp

class MahjongNetFrost2():
    """
    Mahjong Network Frost 2
    Using CNN + FC layers, purely feed-forward network
    """
    def __init__(self, graph, agent_no, lr=3e-4, log_dir="../log/", num_tile_type=34, num_each_tile=55, num_vf=29):
        """Model function for CNN."""

        self.session = tf.Session(graph=graph)
        self.graph = graph
        self.log_dir = log_dir + ('' if log_dir[-1]=='/' else '/')

        self.num_tile_type = num_tile_type  # number of tile types
        self.num_each_tile = num_each_tile # number of features for each tile
        self.num_vf = num_vf # number of vector features

        with self.graph.as_default():

            self.matrix_features = tf.placeholder(dtype=tf.float32, shape=[None, self.num_tile_type, self.num_each_tile], name='Features')
            self.vector_features = tf.placeholder(dtype=tf.float32, shape=[None, self.num_vf], name='Features')


            # Convolutional Layer #1
            conv1 = tf.layers.conv1d(
                inputs=self.matrix_features,
                filters=256,
                kernel_size=3,
                strides=1,
                padding="same",
                activation=tf.nn.relu)

            # Convolutional Layer #2 and Pooling Layer #2
            conv2 = tf.layers.conv1d(
                inputs=conv1,
                filters=128,
                kernel_size=3,
                strides=3,
                padding="same",
                activation=tf.nn.relu)

            # Convolutional Layer #2 and Pooling Layer #2
            conv3 = tf.layers.conv1d(
                inputs=conv2,
                filters=128,
                kernel_size=1,
                strides=3,
                padding="same",
                activation=tf.nn.relu)

            # Dense Layers
            flat = tf.concat([tf.layers.flatten(conv3), self.vector_features], axis=1)
            fc1 = tf.layers.dense(inputs=flat, units=128, activation=tf.nn.relu)
            fc2 = tf.layers.dense(inputs=fc1, units=256, activation=tf.nn.relu)
            fc3 = tf.layers.dense(inputs=fc2, units=128, activation=tf.nn.relu)

            # dropout = tf.layers.dropout(
            #     inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)

            self.value_output = tf.layers.dense(inputs=fc3, units=1, activation=None)

            self.value_target = tf.placeholder(dtype=tf.float32, shape=[None, 1], name='value_targets')

            self.loss = tf.losses.mean_squared_error(self.value_target, self.value_output)
            self.optimizer = tf.train.AdamOptimizer(lr)
            self.train_step = self.optimizer.minimize(self.loss)

            self.saver = tf.train.Saver()

            tf.summary.scalar('loss', self.loss)
            tf.summary.histogram('value_pred', self.value_output)

            now = datetime.now()
            datetime_str = now.strftime("%Y%m%d-%H%M%S")

            self.merged = tf.summary.merge_all()
            self.train_writer = tf.summary.FileWriter(log_dir + 'naiveAIlog-Agent{}-'.format(agent_no) + datetime_str, self.session.graph)

            self.session.run(tf.global_variables_initializer())

    def save(self, model_dir):
        save_path = self.saver.save(self.session, self.log_dir + model_dir + ('' if model_dir[-1]=='/' else '/') + "naiveAI.ckpt")
        print("Model saved in path: %s" % save_path)

    def restore(self, model_path):
        self.saver.restore(self.session, model_path)
        print("Model restored from" + model_path)

    def output(self, input):
        with self.graph.as_default():
            value_pred = self.session.run(self.value_output, feed_dict={self.matrix_features: input[0], self.vector_features: input[1]})

        return value_pred

    def train(self, input, target, logging, global_step):
        with self.graph.as_default():
            loss, _ , summary = self.session.run([self.loss, self.train_step, self.merged],
                feed_dict = {self.matrix_features: input[0], self.vector_features: input[1], self.value_target: target})

            if logging:
                self.train_writer.add_summary(summary, global_step=global_step)

        return loss

class AgentFrost2():
    """
    Mahjong AI agent with PER
    """
    def __init__(self, nn: MahjongNetFrost2, memory:MahjongBufferFrost2, gamma=0.9999, greedy=1.0, lambd=0.8,
                 num_tile_type=34, num_each_tile=55, num_vf=29):
        self.nn = nn
        self.gamma = gamma  # discount factor
        self.greedy = greedy
        self.memory = memory
        self.lambd = lambd
        self.global_step = 0
        self.num_tile_type = num_tile_type  # number of tile types
        self.num_each_tile = num_each_tile # number of features for each tile
        self.num_vf = num_vf # number of vector features

        # statistics
        self.stat = {}
        self.stat['num_games'] = 0.
        self.stat['hora_games'] = 0.
        self.stat['ron_games'] = 0.
        self.stat['tsumo_games'] = 0.
        self.stat['fire_games'] = 0.
        self.stat['total_scores_get'] = 0.

        self.stat['hora_rate'] = 0.
        self.stat['tsumo_rate'] = 0.
        self.stat['fire_rate'] = 0.
        self.stat['fulu_rate'] = 0.
        self.stat['riichi_rate'] = 0.
        self.stat['avg_point_get'] = 0.

        self.stat['hora'] = []
        self.stat['ron'] = []
        self.stat['tsumo'] = []
        self.stat['fire'] = []
        self.stat['score_change'] = []

    def statistics(self, playerNo, result, final_score_change, turn, riichi, menchin):

        fulu = 1 - menchin

        if result.result_type == mp.ResultType.RonAgari:
            ron_playerNo = np.argmax(final_score_change)
            if playerNo == ron_playerNo:
                self.stat['hora_games'] += 1
                self.stat['ron_games'] += 1
                self.stat['total_scores_get'] += np.max(final_score_change)
                self.stat['ron'].append(1)
                self.stat['tsumo'].append(0)
                self.stat['hora'].append(1)
                self.stat['fire'].append(0)
            elif riichi * 1000 + final_score_change[playerNo] < 0 and final_score_change[playerNo] <= - (
                    np.max(final_score_change) - riichi * 1000):
                self.stat['ron'].append(0)
                self.stat['tsumo'].append(0)
                self.stat['hora'].append(0)
                self.stat['fire'].append(1)
                self.stat['fire_games'] += 1

        if result.result_type == mp.ResultType.TsumoAgari:
            tsumo_playerNo = np.argmax(final_score_change)
            if playerNo == tsumo_playerNo:
                self.stat['hora_games'] += 1
                self.stat['tsumo_games'] += 1
                self.stat['total_scores_get'] += np.max(final_score_change)
                self.stat['ron'].append(0)
                self.stat['tsumo'].append(1)
                self.stat['hora'].append(1)
                self.stat['fire'].append(0)

        self.stat['score_change'].append(final_score_change[playerNo])
        self.stat['num_games'] += 1

        self.stat['hora_rate'] = self.stat['hora_games'] / self.stat['num_games']
        self.stat['tsumo_rate'] = self.stat['tsumo_games'] / self.stat['num_games']
        self.stat['fire_rate'] = self.stat['fire_games'] / self.stat['num_games']

        self.stat['fulu_rate'] = (self.stat['fulu_rate'] * (self.stat['hora_games'] - 1) + riichi) / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0
        self.stat['riichi_rate'] = (self.stat['riichi_rate'] * (self.stat['hora_games'] - 1) + fulu) / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0

        self.stat['hora_turn'] = (self.stat['hora_turn'] * (self.stat['hora_games'] - 1) + turn) / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0
        self.stat['avg_point_get'] = self.stat['total_scores_get'] / self.stat['hora_games'] if self.stat['hora_games'] > 0 else 0


    def select(self, aval_next_states):
        """
        select an action according to the value estimation of the next state after performing an action
        :param:
            aval_next_states: (matrix_features [N by self.num_tile_type by self.num_each_tile], vector features [N by self.num_vf]), where N is number of possible
                actions (corresponds to aval_next_states)
        :return:
            action: an int number, indicating the index of being selected action,from [0, 1, ..., N]
            policy: an N-dim vector, indicating the probabilities of selecting actions [0, 1, ..., N]
        """
        if aval_next_states is None:
            return None

        aval_next_matrix_features = np.reshape(aval_next_states[0], [-1, self.num_tile_type, self.num_each_tile])
        aval_next_vector_features = np.reshape(aval_next_states[1], [-1, self.num_vf])

        next_value_pred = np.reshape(self.nn.output((aval_next_matrix_features, aval_next_vector_features)), [-1])

        # softmax policy
        policy = scisp.softmax(self.greedy * next_value_pred / 1000)
        action = np.random.choice(np.size(policy), p=policy)

        return action, policy

    def remember_episode(self, states, rewards, dones, actions, behavior_policies, weight):
        # try:

        if len(dones) == 0:
            print("Episode Length 0! Not recorded!")
        else:
            self.memory.append_episode(states,
                                       np.reshape(rewards, [-1,]),
                                       np.reshape(dones, [-1,]),
                                       np.reshape(actions, [-1]),
                                       np.reshape(behavior_policies, [-1, 40]),
                                       weight=weight)
        # except:
        #     print("Episode Length 0! Not recorded!")
    def learn(self, symmetric_hand=None, episode_start=1, care_lose=True, logging=True):

        if self.memory.filled_size >= episode_start:
            S, Sp, s, sp, r, d, a, mu, length, e_index, e_weight = self.memory.sample_episode_batch()

            if not care_lose:
                r = np.maximum(r, 0)

            this_S = S
            next_S = Sp

            this_s = s
            next_s = sp

            target_value = np.zeros([r.shape[0], 1], dtype=np.float32)

            v = self.nn.output((this_S, this_s))
            vp = self.nn.output((next_S, next_s))

            td_prime = 0

            for i in reversed(range(r.shape[0])):  #Q(lambda)

                td_error = r[i] + (1. - d[i]) * self.gamma * vp[i, 0] - v[i, 0]

                if d[i]:
                    td_prime = 0

                target_value[i, 0] = v[i,0] + 1. * (td_error + self.lambd * td_prime)

                td_prime += 1. * self.lambd * td_error

            self.global_step += 1

            # also train symmetric hand
            if not symmetric_hand == None:
                all_S = np.concatenate([symmetric_hand(this_S) for _ in range(5)], axis=0).astype(np.float32)
                all_s = np.concatenate([this_s for _ in range(5)], axis=0).astype(np.float32)
                all_target_value = np.concatenate([target_value for _ in range(5)], axis=0).astype(np.float32)
            else:
                all_S = this_S
                all_s = this_s
                all_target_value = target_value

            self.nn.train((all_S, all_s), all_target_value, logging=logging, global_step=self.global_step)

        else:
            pass


import tensorflow as tf
from buffer import SimpleMahjongBufferPER
import numpy as np
from datetime import datetime



class NMnaive():
    """
    Mahjong Network naive version
    """
    def __init__(self, session, lr=3e-4, log_dir="../log/"):
        """Model function for CNN."""

        self.session = session
        self.log_dir = log_dir

        num_tile_type = 7 + 3 * 9
        num_each_tile = 4
        self.features = tf.placeholder(dtype=tf.float32, shape=[None, num_tile_type, num_each_tile, 1], name='Features')

        # Input Layer
        input_layer = self.features

        # Convolutional Layer #1
        conv1 = tf.layers.conv2d(
            inputs=input_layer,
            filters=64,
            kernel_size=[3, 1],
            strides=[1, 1],
            padding="same",
            activation=tf.nn.relu)

        # Pooling Layer #1
        pool1 = tf.layers.average_pooling2d(inputs=conv1, pool_size=[1, 2], strides=[1, 2])

        # Convolutional Layer #2 and Pooling Layer #2
        conv2 = tf.layers.conv2d(
            inputs=pool1,
            filters=64,
            kernel_size=[3, 1],
            strides=[1, 1],
            padding="same",
            activation=tf.nn.relu)
        pool2 = tf.layers.average_pooling2d(inputs=conv2, pool_size=[1, 2], strides=[1, 2])

        # Dense Layers
        conv2_flat = tf.layers.flatten(pool2)
        fc1 = tf.layers.dense(inputs=conv2_flat, units=128, activation=tf.nn.relu)
        fc2 = tf.layers.dense(inputs=fc1, units=128, activation=tf.nn.relu)
        # dropout = tf.layers.dropout(
        #     inputs=dense, rate=0.4, training=mode == tf.estimator.ModeKeys.TRAIN)

        self.value_output = tf.layers.dense(inputs=fc2, units=1, activation=None)

        self.value_target = tf.placeholder(dtype=tf.float32, shape=[None, 1], name='value_targets')

        self.loss = tf.losses.mean_squared_error(self.value_target, self.value_output)
        self.optimizer = tf.train.AdamOptimizer(lr)
        self.train_step = self.optimizer.minimize(self.loss)

        self.saver =tf.train.Saver()

        tf.summary.scalar('loss', self.loss)
        tf.summary.histogram('value_pred', self.value_output)

        now = datetime.now()
        datetime_str = now.strftime("%Y%m%d-%H%M%S")

        self.merged = tf.summary.merge_all()
        self.train_writer = tf.summary.FileWriter(log_dir + 'naiveAI' + datetime_str, self.session.graph)

        self.session.run(tf.global_variables_initializer())

    def save(self):
        now = datetime.now()
        datetime_str = now.strftime("%Y%m%d-%H%M%S")

        save_path = self.saver.save(self.session, self.log_dir + datetime_str + ".ckpt")
        print("Model saved in path: %s" % save_path)

    def restore(self, model_path):
        self.saver.restore(self.session, model_path)
        print("Model restored from" + model_path)

    def output(self, input):

        value_pred = self.session.run(self.value_output, feed_dict={self.features: input})

        return value_pred

    def train(self, input, target, logging, global_step):

        loss, _ , summary = self.session.run([self.loss, self.train_step, self.merged],
                                             feed_dict={self.features: input, self.value_target: target})

        if logging:
            self.train_writer.add_summary(summary, global_step=global_step)

        return loss


class AgentNaive():
    """
    Mahjong AI agent naive version
    """
    def __init__(self, nn: NMnaive, memory, gamma=0.9999, greedy=1e-3, batch_size=64, lambd=1.0):
        self.nn = nn
        self.gamma = gamma  # discount factor
        self.greedy = greedy
        self.memory = memory
        self.batch_size = batch_size
        self.lambd = lambd
        self.global_step = 0

    def select(self, aval_next_states):
        """
        select an action according to the value estimation of the next state after performing an action
        :param:
            aval_next_states: a [N by 34 by 4] matrix, where N is number of possible actions (corresponds to aval_next_states)
        :return:
            action: an int number, indicating the index of being selected action,from [0, 1, ..., N]
            policy: an N-dim vector, indicating the probabilities of selecting actions [0, 1, ..., N]
        """
        if aval_next_states is None:
            return None

        aval_next_states = np.reshape(aval_next_states, [-1, 34, 4, 1])
        next_value_pred = np.reshape(self.nn.output(aval_next_states), [-1])

        # softmax policy
        policy = np.exp(self.greedy * next_value_pred) / np.sum(np.exp(self.greedy * next_value_pred))
        action = np.random.choice(np.size(policy), p=policy)

        return action, policy

    def remember(self, this_state, action, next_state, reward, done, next_aval_states, policy):
        self.memory.append(this_state.reshape([34, 4, 1]), reward, next_state.reshape([34, 4, 1]), 1 if done else 0)

    def learn(self, symmetric_hand):

        if self.memory.filled > 2 * self.batch_size:
            state, r, d = self.memory.sample(self.batch_size)

            this_state = state[:-1]
            next_state = state[1:]

            target_value = np.zeros([self.batch_size, 1], dtype=np.float32)

            v = self.nn.output(this_state)
            vp = self.nn.output(next_state)

            td_prime = 0

            for i in reversed(range(self.batch_size)):

                td_error = r[i] + (1. - d[i]) * self.gamma * vp[i, 0] - v[i, 0]

                target_value[i, 0] = v[i,0] + td_error + self.lambd * td_prime

                td_prime += self.lambd * td_error

            self.global_step += 1

            # self.nn.train(this_state, target_value, logging=True, global_step=self.global_step)

            # also train symmetric hand

            all_state = np.concatenate([symmetric_hand(this_state) for _ in range(5)], axis=0)
            all_target_value = np.concatenate([target_value for _ in range(5)], axis=0)

            self.nn.train(all_state, all_target_value, logging=True, global_step=self.global_step)

        else:
            pass



class AgentPER():
    """
    Mahjong AI agent with PER
    """
    def __init__(self, nn: NMnaive, memory:SimpleMahjongBufferPER, gamma=0.9999, greedy=1e-3, lambd=1.0):
        self.nn = nn
        self.gamma = gamma  # discount factor
        self.greedy = greedy
        self.memory = memory
        self.lambd = lambd
        self.global_step = 0

    def select(self, aval_next_states):
        """
        select an action according to the value estimation of the next state after performing an action
        :param:
            aval_next_states: a [N by 34 by 4] matrix, where N is number of possible actions (corresponds to aval_next_states)
        :return:
            action: an int number, indicating the index of being selected action,from [0, 1, ..., N]
            policy: an N-dim vector, indicating the probabilities of selecting actions [0, 1, ..., N]
        """
        if aval_next_states is None:
            return None

        aval_next_states = np.reshape(aval_next_states, [-1, 34, 4, 1])
        next_value_pred = np.reshape(self.nn.output(aval_next_states), [-1])

        # softmax policy
        policy = np.exp(self.greedy * next_value_pred) / np.sum(np.exp(self.greedy * next_value_pred))
        action = np.random.choice(np.size(policy), p=policy)

        return action, policy

    def remember_episode(self, states, rewards, dones, weight):
        self.memory.append_episode(np.reshape(states, [-1, 34, 4, 1]),
                                   np.reshape(rewards, [-1,]),
                                   np.reshape(dones, [-1,]),
                                   weight=weight)

    def learn(self, symmetric_hand, care_others=False):

        if self.memory.filled > 32:
            state, r, d = self.memory.sample_episode()

            this_state = state[:-1]
            next_state = state[1:]

            target_value = np.zeros([r.shape[0], 1], dtype=np.float32)

            v = self.nn.output(this_state)
            vp = self.nn.output(next_state)

            td_prime = 0

            for i in reversed(r.shape[0]):

                if care_others:
                    td_error = r[i] + (1. - d[i]) * self.gamma * vp[i, 0] - v[i, 0]
                else:
                    if r[i] > 0:
                        td_error = r[i] + (1. - d[i]) * self.gamma * vp[i, 0] - v[i, 0]
                    else:
                        td_error = r[i] + self.gamma * vp[i, 0] - v[i, 0]

                target_value[i, 0] = v[i,0] + td_error + self.lambd * td_prime

                td_prime += self.lambd * td_error

            self.global_step += 1

            # self.nn.train(this_state, target_value, logging=True, global_step=self.global_step)

            # also train symmetric hand

            all_state = np.concatenate([symmetric_hand(this_state) for _ in range(5)], axis=0)
            all_target_value = np.concatenate([target_value for _ in range(5)], axis=0)

            self.nn.train(all_state, all_target_value, logging=True, global_step=self.global_step)

        else:
            pass


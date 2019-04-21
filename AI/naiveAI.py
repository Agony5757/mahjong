import tensorflow as tf
from buffer import PrioritizedReplayBuffer
import numpy as np



class NMnaive():
    """
    Mahjong Network naive version
    """
    def __init__(self, session, lr=3e-4):
        """Model function for CNN."""

        self.session = session

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

        self.value_target = tf.placeholder(dtype=tf.float32, shape=[None, 1], name='Features')

        self.loss = tf.losses.mean_squared_error(self.value_target, self.value_output)
        self.optimizer = tf.train.AdamOptimizer(lr)

        self.session.run(tf.global_variables_initializer())

    def output(self, input):

        value_pred = self.session.run(self.value_output, feed_dict={self.features: input})

        return value_pred

    def train(self, input, target):

        loss, _ = self.session.run([self.loss, self.optimizer], feed_dict={self.features: input,
                                                                           self.value_target: target})

        return loss


class AgentNaive():
    """
    Mahjong AI agent naive version
    """
    def __init__(self, nn: NMnaive, memory:PrioritizedReplayBuffer, gamma=0.99999, greedy=1.0):
        self.nn = nn
        self.gamma = gamma  # discount factor
        self.greedy = greedy
        self.memory = memory

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

    def remember(self, this_state, action, next_state, score, done, next_aval_states, policy):
        pass

    def learn(self):
        pass
import numpy as np
import random

class MahjongBufferFrost2():
    # Record Episodes
    # Prioritized Experience Replay (currently disabled)
    class SumTree:
        def __init__(self, size, scale):
            self.size = size
            self.scale = scale
            self.tree_nodes = np.zeros(2 * size, dtype=np.float32)

        def sum(self):
            return self.tree_nodes[1]

        def add(self, index, weight):
            index += self.size
            self.tree_nodes[index] = weight ** self.scale
            while index > 0:
                index = index // 2
                self.tree_nodes[index] = self.tree_nodes[index * 2] + self.tree_nodes[index * 2 + 1]

        def sample_subtree(self, root):
            if root >= self.size:
                return root - self.size, self.tree_nodes[root] / self.tree_nodes[1]
            pl = self.tree_nodes[root * 2]
            pr = self.tree_nodes[root * 2 + 1]
            s = pl + pr
            pl /= s
            pr /= s
            if random.random() < pl:
                return self.sample_subtree(root * 2)
            else:
                return self.sample_subtree(root * 2 + 1)

        def sample(self):
            if self.tree_nodes[1] == 0:
                raise Exception("Error! Sampling from empty buffer")
            return self.sample_subtree(1)
            pass

    def __init__(self, size=256, episode_length=150, priority_eps=10000, priority_scale=0.0, IS_scale=1.0, saved=None,
                 num_tile_type=34, num_each_tile=58, num_vf=29):
        # Mahjong episode length usually < 256

        self.saved = False

        self.size = size
        self.episode_length = episode_length
        self.length = np.zeros([size,], dtype=np.int)
        self.num_tile_type = num_tile_type
        self.num_each_tile = num_each_tile
        self.num_vf = num_vf
        self.max_action_num = 40

        self.S = np.zeros([size, episode_length, num_tile_type, num_each_tile], dtype=np.float16) # matrix features
        self.s = np.zeros([size, episode_length, num_vf], dtype=np.float16)  # vector features

        self.r = np.zeros([size, episode_length], dtype=np.float32) # reward
        self.d = np.zeros([size, episode_length], dtype=np.float16) # done
        self.mu = np.zeros([size, episode_length, self.max_action_num], dtype=np.float32) # bahavior policy
        self.a = np.zeros([size, episode_length], dtype=np.int)  # action

        self.IS_scale = IS_scale
        self.priority_scale = priority_scale
        self.priority_eps = priority_eps

        self.filled_size = 0  # up to this index, the buffer is filled
        self.tail = 0  # index to which an experience to be stored next

        tree_size = 2 ** int(np.ceil(np.log2(size)))
        self.sum_tree = MahjongBufferFrost2.SumTree(tree_size, priority_scale)
        self.sum_steps = 0
        self.min_length = 0
        self.max_length = 0

    def append_episode(self, state, r, d, a, mu, weight=0):
        """
        Append an episode
        :param state: features
        :param r: reward
        :param d: done
        :param a: action
        :param mu: behavior policy
        :param weight: weight of this epsiode for PER
        :return: None
        """
        length = len(r)

        for stp in range(length + 1):
            self.s[self.tail, stp] = state[stp][1]
            self.S[self.tail, stp] = state[stp][0]

        self.r[self.tail, :length] = r
        self.d[self.tail, :length] = d
        self.a[self.tail, :length] = a
        self.mu[self.tail, :length] = mu
        self.length[self.tail] = length

        self.sum_tree.add(self.tail, weight + self.priority_eps)
        self.sum_steps += length
        self.min_length = min(self.min_length, length)
        self.max_length = max(self.max_length, length)

        self.tail = (self.tail + 1) % self.size
        self.filled_size = min(self.filled_size + 1, self.size)

        self.saved = False

        return None

    def sample_episode(self):
        e_index, e_weight = self.sum_tree.sample()

        d = self.d[e_index, :self.length[e_index]]
        S = self.S[e_index, :self.length[e_index] + 1]
        s = self.s[e_index, :self.length[e_index] + 1]
        r = self.r[e_index, :self.length[e_index]]
        a = self.a[e_index, :self.length[e_index]]
        mu = self.mu[e_index, :self.length[e_index]]

        return S, s, r, d, a, mu, self.length[e_index], e_index, e_weight

    def sample_episode_batch(self, batch_size=16):

        Length = np.zeros([batch_size,], dtype=np.int)
        E_index = np.zeros([batch_size,], dtype=np.int)
        E_weight = np.zeros([batch_size,], dtype=np.float32)

        for b in range(batch_size):
            if b == 0:
                e_index, e_weight = self.sum_tree.sample()
                d = (self.d[e_index, :self.length[e_index]])
                S = (self.S[e_index, :self.length[e_index]])
                s = (self.s[e_index, :self.length[e_index]])
                Sp = (self.S[e_index, 1:self.length[e_index] + 1])
                sp = (self.s[e_index, 1:self.length[e_index] + 1])
                r = (self.r[e_index, :self.length[e_index]])
                a = (self.a[e_index, :self.length[e_index]])
                mu = (self.mu[e_index, :self.length[e_index]])
            else:
                e_index, e_weight = self.sum_tree.sample()
                S = np.vstack([S, self.S[e_index, :self.length[e_index]]])
                s = np.vstack([s, self.s[e_index, :self.length[e_index]]])
                Sp = np.vstack([Sp, self.S[e_index, 1:self.length[e_index] + 1]])
                sp = np.vstack([sp, self.s[e_index, 1:self.length[e_index] + 1]])
                r = np.hstack([r, self.r[e_index, :self.length[e_index]]])
                d = np.hstack([d, self.d[e_index, :self.length[e_index]]])
                a = np.hstack([a, self.a[e_index, :self.length[e_index]]])
                mu = np.vstack([mu, self.mu[e_index, :self.length[e_index]]])

            Length[b] = self.length[e_index]
            E_index[b] = e_index
            E_weight[b] = e_weight

        # S = np.reshape(S, [-1, self.num_tile_type, self.num_each_tile]).astype(np.float16)
        # s = np.reshape(s, [-1, self.num_vf]).astype(np.float16)
        # Sp = np.reshape(Sp, [-1, self.num_tile_type, self.num_each_tile]).astype(np.float16)
        # sp = np.reshape(sp, [-1, self.num_vf]).astype(np.float16)
        #
        # d = np.reshape(d, [-1,]).astype(np.float16)
        # r = np.reshape(r, [-1,]).astype(np.float32)
        # a = np.reshape(a, [-1,]).astype(np.int)
        # mu = np.reshape(mu, [-1, self.max_action_num]).astype(np.float32)

        return S, Sp, s, sp, r, d, a, mu, Length, E_index, E_weight

    def save(self, path='./MahjongBufferFrost2.npz'):

        if not self.saved:
            parameters = np.array([self.size, self.episode_length, self.filled_size, self.tail])
            np.savez(path, parameters=parameters, S=self.S, s=self.s, r=self.r, mu=self.mu, length=self.length, d=self.d)
            print("Buffer saved in path: %s" % path)

        self.saved = True

        return None

    def load(self, path='./MahjongBufferFrost2.npz'):
        data = np.load(path)

        self.size = data['parameters'][0]
        self.episode_length = data['parameters'][1]
        self.filled_size = data['parameters'][2]
        self.tail = data['parameters'][3]

        self.length = data['length']

        self.S = data['S']
        self.s = data['s']
        self.r = data['r']
        self.d = data['d']
        self.mu = data['mu']

        # self.infinity = 1e9

        for i in range(self.filled_size):
            self.sum_tree.add(i, 0)
            length = self.length[i]
            self.sum_steps += length
            self.min_length = min(self.min_length, length)
            self.max_length = max(self.max_length, length)

        return None


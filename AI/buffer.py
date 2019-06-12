import numpy as np
import random
import sparse as sps
import pickle

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

    def __init__(self, size=256, episode_length=180, priority_eps=10000, priority_scale=0.0, IS_scale=1.0, saved=None,
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

        self.n = np.zeros([size, episode_length], dtype=int)  # number of available actions

        self.Sp = [[] for _ in range(self.size)] # next matrix features
        self.sp = np.zeros([size, episode_length, self.max_action_num, num_vf], dtype=np.float16)  # next vector features

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

    def append_episode(self, n, Sp, sp, r, d, a, mu, weight=0):
        """
        Append an episode
        :param n: number of available actions
        :param Sp: available next matrix features
        :param sp: available next ector features
        :param r: reward
        :param d: done
        :param a: action
        :param mu: behavior policy
        :param weight: weight of this epsiode for PER
        :return: None
        """

        length = len(r)

        Sp = Sp.reshape([Sp.shape[0], Sp.shape[1], self.num_tile_type * self.num_each_tile])
        Sp_padded = np.zeros([self.episode_length, Sp.shape[1], self.num_tile_type * self.num_each_tile], dtype=np.float16)
        Sp_padded[: length] = Sp

        self.n[self.tail, :length] = n

        self.Sp[self.tail] = sps.COO.from_numpy(Sp_padded)

        self.sp[self.tail, :length] = sp

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

        n = self.n[e_index, :self.length[e_index]].astype(int)
        d = self.d[e_index, :self.length[e_index]]

        Sp = self.Sp[e_index].todense()[:self.length[e_index]]

        sp = self.sp[e_index, :self.length[e_index]]
        r = self.r[e_index, :self.length[e_index]]
        a = self.a[e_index, :self.length[e_index]]
        mu = self.mu[e_index, :self.length[e_index]]

        Sp = Sp.reshape([Sp.shape[0], Sp.shape[1], self.num_tile_type, self.num_each_tile]).astype(np.float16)

        return n, Sp, sp, r, d, a, mu, self.length[e_index], e_index, e_weight

    # def sample_episode_batch(self, batch_size=16):
    #
    #     Length = np.zeros([batch_size,], dtype=np.int)
    #     E_index = np.zeros([batch_size,], dtype=np.int)
    #     E_weight = np.zeros([batch_size,], dtype=np.float32)
    #
    #     Sp_dense = self.Sp.todense().astype(np.float16)
    #
    #     Sp_dense = Sp_dense.reshape([Sp_dense.shape[0], Sp_dense.shape[1], Sp_dense.shape[2], self.num_tile_type, self.num_each_tile])
    #
    #     for b in range(batch_size):
    #
    #         if b == 0:
    #             e_index, e_weight = self.sum_tree.sample()
    #             n = (self.n[e_index, :self.length[e_index]])
    #             d = (self.d[e_index, :self.length[e_index]])
    #             Sp = (Sp_dense[e_index, :self.length[e_index]])
    #             sp = (self.sp[e_index, :self.length[e_index]])
    #             r = (self.r[e_index, :self.length[e_index]])
    #             a = (self.a[e_index, :self.length[e_index]])
    #             mu = (self.mu[e_index, :self.length[e_index]])
    #         else:
    #             e_index, e_weight = self.sum_tree.sample()
    #             n = np.hstack([n, self.n[e_index, :self.length[e_index]]])
    #             Sp = np.vstack([Sp, Sp_dense[e_index, :self.length[e_index]]])
    #             sp = np.vstack([sp, self.sp[e_index, :self.length[e_index]]])
    #             r = np.hstack([r, self.r[e_index, :self.length[e_index]]])
    #             d = np.hstack([d, self.d[e_index, :self.length[e_index]]])
    #             a = np.hstack([a, self.a[e_index, :self.length[e_index]]])
    #             mu = np.vstack([mu, self.mu[e_index, :self.length[e_index]]])
    #
    #         Length[b] = self.length[e_index]
    #         E_index[b] = e_index
    #         E_weight[b] = e_weight
    #
    #     return n, Sp, sp, r, d, a, mu, Length, E_index, E_weight

    def save(self, path='./MahjongBufferFrost2.pkl'):

        if not self.saved:

            parameters = np.array([self.size, self.episode_length, self.filled_size, self.tail])
            data = {'parameters': parameters,
                    'n': self.n,
                    'Sp': self.Sp,
                    'sp': self.sp,
                    'r': self.r,
                    'mu': self.mu,
                    'length': self.length,
                    'd': self.d}

            f = open(path, 'wb')
            pickle.dump(data, f)
            f.close()
            print("Buffer saved in path: %s" % path)

        self.saved = True

        return None

    def load(self, path='./MahjongBufferFrost2.pkl'):

        f = open(path, 'rb')
        data = pickle.load(f)
        f.close()

        self.size = data['parameters'][0]
        self.episode_length = data['parameters'][1]
        self.filled_size = data['parameters'][2]
        self.tail = data['parameters'][3]

        self.length = data['length']

        self.n = data['n']
        self.Sp = data['Sp'] # ok to assign np array to DOK
        self.sp = data['sp']
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


import numpy as np
import random

class SimpleMahjongBuffer():

    def __init__(self, size=10000):
        self.size = size
        self.s = np.zeros([size, 34, 4, 1], dtype=np.float32)
        self.sp = np.zeros([size, 34, 4, 1], dtype=np.float32)
        self.r = np.zeros([size], dtype=np.float32)
        self.d = np.zeros([size], dtype=np.float32)

        self.filled = -1  # up to this index, the buffer is filled
        self.tail = 0  # index to which an experience to be stored next

    def __len__(self):
        return self.filled

    def append(self, s, r, s_next, done):
        self.s[self.tail] = s
        self.r[self.tail] = r
        self.sp[self.tail] = s_next
        # self.mu[self.tail] = mu
        self.d[self.tail] = done

        self.filled = max(self.filled, self.tail)
        self.tail += 1
        if self.tail == self.size:
            self.tail = 0

    def sample(self, truncated_steps):
        index = np.random.randint(low=truncated_steps, high=self.filled)

        s = np.vstack((self.s[index - truncated_steps:index], self.sp[None, index]))
        ret_tuple = (s,
                     self.r[index - truncated_steps:index],
                     self.d[index - truncated_steps:index])

        return ret_tuple




class SimpleMahjongBufferPER():
    # Record Episodes
    # Prioritized Experience Replay
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

    def __init__(self, size=1024, episode_length=256, priority_eps=10000,
                 priority_scale=0.1, IS_scale=1.0, saved=None):
        # Mahjong episode length usually <256
        self.size = size
        self.length = np.zeros([size,], dtype=np.int)
        self.s = np.zeros([size, episode_length, 34, 4, 1], dtype=np.float16)
        self.r = np.zeros([size, episode_length], dtype=np.float32)
        self.d = np.zeros([size, episode_length], dtype=np.float16)

        self.IS_scale = IS_scale
        self.priority_scale = priority_scale
        self.priority_eps = priority_eps

        self.filled_size = 0  # up to this index, the buffer is filled
        self.tail = 0  # index to which an experience to be stored next

        tree_size = 2 ** int(np.ceil(np.log2(size)))
        self.sum_tree = SimpleMahjongBufferPER.SumTree(tree_size, priority_scale)
        self.sum_steps = 0
        self.min_length = 0
        self.max_length = 0

        # self.infinity = 1e9

        # # initialize priority of saved episodes to inf
        # for i in range(self.saved_size):
        #     self.sum_tree.add(i, self.infinity)
        #     length = self.length[i]
        #     self.sum_steps += length
        #     self.min_length = min(self.min_length, length)
        #     self.max_length = max(self.max_length, length)

    def append_episode(self, s, r, d, weight=0):
        length = len(r)
        self.s[self.tail, :length+1] = s
        self.r[self.tail, :length] = r
        self.length[self.tail] = length
        self.d[self.tail, length-1] = 1

        self.sum_tree.add(self.tail, weight + self.priority_eps)

        self.tail = (self.tail + 1) % self.size
        self.filled_size = min(self.filled_size + 1, self.size)


    def sample_episode(self):
        e_index, e_weight = self.sum_tree.sample()

        d = self.d[e_index, :self.length[e_index]]
        s = self.s[e_index, :self.length[e_index]+1]
        r = self.r[e_index, :self.length[e_index]]
        # pi = self.pi[e_index]

        return s, r, d, self.length[e_index], e_index, e_weight

    # def sample_episode_batch(self, batch_size=32):
    #     states_b = []
    #     actions_b = []
    #     pi_b = []
    #     r_b = []
    #     done_b = []
    #     length_b = []
    #     mask_b = []
    #     indices = []
    #     weights = []
    #     for i in range(batch_size):
    #         states, actions, pi, r, done, length, mask, e_index, e_weight = self.sample_episode()
    #         states_b.append(states)
    #         actions_b.append(actions)
    #         pi_b.append(pi)
    #         r_b.append(r)
    #         done_b.append(done)
    #         length_b.append(length)
    #         mask_b.append(mask)
    #         indices.append(e_index)
    #         weights.append((length/e_weight/self.sum_steps) ** self.IS_scale)
    #
    #     max_l = max(length_b)
    #     states_b = np.stack(states_b, axis=0)[:, :max_l+1]
    #     actions_b = np.stack(actions_b, axis=0)[:, :max_l]
    #     pi_b = np.stack(pi_b, axis=0)[:, :max_l]
    #     r_b = np.stack(r_b, axis=0)[:, :max_l]
    #     done_b = np.stack(done_b, axis=0)
    #     mask_b = np.stack(mask_b, axis=0)
    #     weights_b = np.stack(weights, axis=0)
    #
    #     return states_b, actions_b, pi_b, r_b, done_b, length_b, mask_b, indices, weights_b
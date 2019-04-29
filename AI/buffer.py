import numpy as np


class SimpleMahjongBuffer():

    def __init__(self, size=10000):
        self.size = size
        self.s = np.zeros([size, 34, 4, 1], dtype=np.float32)
        self.sp = np.zeros([size, 34, 4, 1], dtype=np.float32)
        self.r = np.zeros([size], dtype=np.float32)
        self.d = np.zeros([size], dtype=np.float32)

        self.filled = -1  # up to this index, the buffer is filled
        self.head = 0  # index to which an experience to be stored next

    def __len__(self):
        return self.filled

    def append(self, s, r, s_next, done):
        self.s[self.head] = s
        self.r[self.head] = r
        self.sp[self.head] = s_next
        # self.mu[self.head] = mu
        self.d[self.head] = done

        self.filled = max(self.filled, self.head)
        self.head += 1
        if self.head == self.size:
            self.head = 0

    def sample(self, truncated_steps):
        index = np.random.randint(low=truncated_steps, high=self.filled)

        s = np.vstack((self.s[index - truncated_steps:index], self.sp[None, index]))
        ret_tuple = (s,
                     self.r[index - truncated_steps:index],
                     self.d[index - truncated_steps:index])

        return ret_tuple



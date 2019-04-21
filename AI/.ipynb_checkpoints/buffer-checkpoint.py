import numpy as np
import random


class AbstractReplayBuffer:
    def append(self, states, actions, pi, r, done, weight=0):
        raise NotImplementedError("Not implemented replay buffer function")

    def sample_trajectory(self, length=32):
        raise NotImplementedError("Not implemented replay buffer function")

    def sample_episode(self):
        raise NotImplementedError("Not implemented replay buffer function")

    def sample_episode_batch(self, batch_size=32):
        raise NotImplementedError("Not implemented replay buffer function")

    def update_priority(self, batch_indices, batch_priority):
        raise NotImplementedError("Not implemented replay buffer function")

    def save(self, path=''):
        pass


class PrioritizedReplayBuffer(AbstractReplayBuffer):
    infinity = 1e9

    class SumTree:
        def __init__(self, size, scale):
            self.size = size
            self.scale = scale
            self.tree_nodes = np.zeros(2*size, dtype=np.float32)

        def sum(self):
            return self.tree_nodes[1]

        def add(self, index, weight):
            index += self.size
            self.tree_nodes[index] = weight ** self.scale
            while index > 0:
                index = index//2
                self.tree_nodes[index] = self.tree_nodes[index*2] + self.tree_nodes[index*2+1]

        def sample_subtree(self, root):
            if root >= self.size:
                return root - self.size, self.tree_nodes[root] / self.tree_nodes[1]
            pl = self.tree_nodes[root*2]
            pr = self.tree_nodes[root*2+1]
            s = pl + pr
            pl /= s
            pr /= s
            if random.random() < pl:
                return self.sample_subtree(root*2)
            else:
                return self.sample_subtree(root*2+1)

        def sample(self):
            if self.tree_nodes[1] == 0:
                raise Exception("Error! Sampling from empty buffer")
            return self.sample_subtree(1)
            pass

    def __init__(self, state_dim, action_dim, max_episodes=1024, episode_length=200, priority_eps=0.01, priority_scale=0.3, IS_scale=1.0, saved=None):
        super(PrioritizedReplayBuffer, self).__init__()
        # parameters = np.array([self.size, self.max_episodes, self.episode_length])
        # np.savez(path, parameters=parameters, states=self.states, actions=self.actions, rewards=self.r, probs=self.pi, length=self.length, mask=self.mask, done=self.done)
        self.priority_eps = priority_eps
        self.IS_scale = IS_scale
        if saved is not None:
            saved_replay = np.load(saved)
            parameters = saved_replay['parameters']
            self.size, self.max_episodes, self.episode_length = parameters
            self.states = saved_replay['states']
            self.actions = saved_replay['actions']
            self.r = saved_replay['rewards']
            self.pi = saved_replay['probs']
            self.length = saved_replay['length']
            self.mask = saved_replay['mask']
            self.done = saved_replay['done']
            self.tail = 0
        else:
            self.length = np.zeros((max_episodes,), dtype=np.int)
            self.mask = np.zeros((max_episodes, episode_length,), dtype=np.bool)
            self.actions = np.zeros((max_episodes, episode_length, action_dim), dtype=np.float32)
            self.states = np.zeros((max_episodes, episode_length + 1, state_dim), dtype=np.float32)
            self.pi = np.zeros((max_episodes, episode_length,), dtype=np.float32)
            self.r = np.zeros((max_episodes, episode_length,), dtype=np.float32)
            self.done = np.zeros((max_episodes,), dtype=np.bool)

            self.tail = self.size = 0
            self.max_episodes = max_episodes
        tree_size = 2 ** int(np.ceil(np.log2(max_episodes)))
        self.sum_tree = PrioritizedReplayBuffer.SumTree(tree_size, priority_scale)
        self.sum_steps = 0
        self.min_length = 0
        self.max_length = 0
        # initialize priority of saved episodes to inf
        for i in range(self.size):
            self.sum_tree.add(i, self.infinity)
            length = self.length[i]
            self.sum_steps += length
            self.min_length = min(self.min_length, length)
            self.max_length = max(self.max_length, length)

    def append(self, states, actions, pi, r, done, weight=0):
        length = len(actions)
        if self.length[self.tail] != 0:
            self.sum_steps -= self.length[self.tail]
        self.length[self.tail] = length
        self.sum_steps += length
        self.min_length = min(self.min_length, length)
        self.max_length = max(self.max_length, length)

        self.length[self.tail] = length
        self.mask[self.tail][:length] = True
        self.mask[self.tail][length:] = False
        self.done[self.tail] = done
        self.states[self.tail][:length + 1] = states
        self.actions[self.tail][:length] = actions
        self.pi[self.tail][:length] = pi
        self.r[self.tail][:length] = r

        self.sum_tree.add(self.tail, weight + self.priority_eps)

        self.tail = (self.tail + 1) % self.max_episodes
        self.size = min(self.size + 1, self.max_episodes)

    def update_priority(self, batch_indices, batch_priority):
        for index, priority in zip(batch_indices, batch_priority):
            self.sum_tree.add(index, priority + self.priority_eps)

    def sample_episode(self):
        e_index, e_weight = self.sum_tree.sample()
        if self.done[e_index]:
            done = True
        else:
            done = False

        states = self.states[e_index, :]
        actions = self.actions[e_index, :]
        r = self.r[e_index, :]
        pi = self.pi[e_index, :]
        mask = self.mask[e_index, :]

        return states, actions, pi, r, done, self.length[e_index], mask, e_index, e_weight

    def sample_episode_batch(self, batch_size=32):
        states_b = []
        actions_b = []
        pi_b = []
        r_b = []
        done_b = []
        length_b = []
        mask_b = []
        indices = []
        weights = []
        for i in range(batch_size):
            states, actions, pi, r, done, length, mask, e_index, e_weight = self.sample_episode()
            states_b.append(states)
            actions_b.append(actions)
            pi_b.append(pi)
            r_b.append(r)
            done_b.append(done)
            length_b.append(length)
            mask_b.append(mask)
            indices.append(e_index)
            weights.append((length/e_weight/self.sum_steps) ** self.IS_scale)

        max_l = max(length_b)
        states_b = np.stack(states_b, axis=0)[:, :max_l+1]
        actions_b = np.stack(actions_b, axis=0)[:, :max_l]
        pi_b = np.stack(pi_b, axis=0)[:, :max_l]
        r_b = np.stack(r_b, axis=0)[:, :max_l]
        done_b = np.stack(done_b, axis=0)
        mask_b = np.stack(mask_b, axis=0)
        weights_b = np.stack(weights, axis=0)

        return states_b, actions_b, pi_b, r_b, done_b, length_b, mask_b, indices, weights_b

    def sample_trajectory(self, length=32):
        raise NotImplementedError("Not Implemented: Sample trajectory from episodic replay buffer")


class PrioritizedReplayBufferWithDemonstration(AbstractReplayBuffer):
    def __init__(self, state_dim, action_dim, demo, max_episodes=1024, episode_length=200, priority_eps=0.01, demo_eps=0.0, priority_scale=0.3, IS_scale=1.0):
        self.demo = PrioritizedReplayBuffer(state_dim, action_dim, max_episodes=max_episodes, episode_length=episode_length, priority_eps=priority_eps + demo_eps, priority_scale=priority_scale, IS_scale=IS_scale, saved=demo)
        self.experience = PrioritizedReplayBuffer(state_dim, action_dim, max_episodes=max_episodes, episode_length=episode_length, priority_eps=priority_eps, priority_scale=priority_scale, IS_scale=IS_scale)
        self.IS_scale = IS_scale

    def sum_steps(self):
        return self.demo.sum_steps + self.experience.sum_steps

    def append(self, states, actions, pi, r, done, weight=0):
        self.experience.append(states, actions, pi, r, done, weight=weight)

    def update_priority(self, batch_indices, batch_priority):
        demo_indices = []
        demo_priority = []
        exp_indices = []
        exp_priority = []
        for index, priority in zip(batch_indices, batch_priority):
            buffer_index, episode_index = index
            if buffer_index == 0:
                demo_indices.append(episode_index)
                demo_priority.append(priority)
            else:
                exp_indices.append(episode_index)
                exp_priority.append(priority)
        self.demo.update_priority(demo_indices, demo_priority)
        self.experience.update_priority(exp_indices, exp_priority)

    def sample_episode(self):
        sum_demo = self.demo.sum_tree.sum()
        sum_exp = self.experience.sum_tree.sum()
        s = sum_demo + sum_exp
        p_demo = sum_demo / s
        p_exp = sum_exp / s
        if random.random() < p_demo:
            buffer_index = 0
            e_index, e_weight = self.demo.sum_tree.sample()
            states = self.demo.states[e_index, :]
            actions = self.demo.actions[e_index, :]
            r = self.demo.r[e_index, :]
            pi = np.ones_like(self.demo.pi[e_index, :]) # don't use pi for demonstration
            mask = self.demo.mask[e_index, :]
            if self.demo.done[e_index]:
                done = True
            else:
                done = False
            # adjust IS weight
            e_weight = e_weight * p_demo
            return states, actions, pi, r, done, self.demo.length[e_index], mask, (buffer_index, e_index), e_weight
        else:
            buffer_index = 1
            e_index, e_weight = self.experience.sum_tree.sample()
            states = self.experience.states[e_index, :]
            actions = self.experience.actions[e_index, :]
            r = self.experience.r[e_index, :]
            pi = self.experience.pi[e_index, :]
            mask = self.experience.mask[e_index, :]
            if self.experience.done[e_index]:
                done = True
            else:
                done = False
            # adjust IS weight
            e_weight = e_weight * p_exp
            return states, actions, pi, r, done, self.experience.length[e_index], mask, (buffer_index, e_index), e_weight

    def sample_episode_batch(self, batch_size=32):
        # print(self.demo.sum_tree.sum(), self.experience.sum_tree.sum())
        states_b = []
        actions_b = []
        pi_b = []
        r_b = []
        done_b = []
        length_b = []
        mask_b = []
        indices = []
        weights = []
        for i in range(batch_size):
            states, actions, pi, r, done, length, mask, e_index, e_weight = self.sample_episode()
            states_b.append(states)
            actions_b.append(actions)
            pi_b.append(pi)
            r_b.append(r)
            done_b.append(done)
            length_b.append(length)
            mask_b.append(mask)
            indices.append(e_index)
            weights.append((length/e_weight/(self.sum_steps())) ** self.IS_scale)

        max_l = max(length_b)
        states_b = np.stack(states_b, axis=0)[:, :max_l+1]
        actions_b = np.stack(actions_b, axis=0)[:, :max_l]
        pi_b = np.stack(pi_b, axis=0)[:, :max_l]
        r_b = np.stack(r_b, axis=0)[:, :max_l]
        done_b = np.stack(done_b, axis=0)
        mask_b = np.stack(mask_b, axis=0)
        weights_b = np.stack(weights, axis=0)

        return states_b, actions_b, pi_b, r_b, done_b, length_b, mask_b, indices, weights_b


class ReplayBuffer(AbstractReplayBuffer):
    def __init__(self, state_dim, action_dim, max_episodes=2000, episode_length=200):
        super(ReplayBuffer, self).__init__()
        self.length = np.zeros((max_episodes,), dtype=np.int)
        self.mask = np.zeros((max_episodes, episode_length,), dtype=np.bool)
        self.actions = np.zeros((max_episodes, episode_length, action_dim), dtype=np.float32)
        self.states = np.zeros((max_episodes, episode_length + 1, state_dim), dtype=np.float32)
        self.pi = np.zeros((max_episodes, episode_length,), dtype=np.float32)
        self.r = np.zeros((max_episodes, episode_length,), dtype=np.float32)
        self.done = np.zeros((max_episodes,), dtype=np.bool)

        self.size = self.tail = 0
        self.max_episodes = max_episodes
        self.episode_length = episode_length

        self.sum_steps = 0
        self.min_length = episode_length
        self.max_length = 0
        pass

    def append(self, states, actions, pi, r, done, weight=0):
        length = len(actions)
        if self.length[self.tail] != 0:
            self.sum_steps -= self.length[self.tail]
        self.length[self.tail] = length
        self.sum_steps += length
        self.min_length = min(self.min_length, length)
        self.max_length = max(self.max_length, length)

        self.mask[self.tail][:length] = True
        self.mask[self.tail][length:] = False
        self.done[self.tail] = done
        self.states[self.tail][:length + 1] = states
        self.actions[self.tail][:length] = actions
        self.pi[self.tail][:length] = pi
        self.r[self.tail][:length] = r
        self.tail = (self.tail + 1) % self.max_episodes
        self.size = min(self.size + 1, self.max_episodes)

    def update_priority(self, batch_indices, batch_priority):
        # Do nothing
        pass

    def sample_trajectory(self, length=32):
        e_length = 0
        while e_length <= 1:
            e_index = np.random.randint(low=0, high=self.size)
            e_length = self.length[e_index]
        l = np.random.randint(low=0, high=e_length)
        if l + length > e_length:
            length = e_length - l

        if l + length == e_length and self.done[e_index]:
            done = True
        else:
            done = False

        states = self.states[e_index, l:l + length + 1]
        actions = self.actions[e_index, l:l + length]
        r = self.r[e_index, l:l + length]
        pi = self.pi[e_index, l:l + length]
        return states, actions, pi, r, done

    def sample_episode(self):
        e_length = 0
        while e_length <= 1:
            e_index = np.random.randint(low=0, high=self.size)
            e_length = self.length[e_index]
        if self.done[e_index]:
            done = True
        else:
            done = False

        states = self.states[e_index, :]
        actions = self.actions[e_index, :]
        r = self.r[e_index, :]
        pi = self.pi[e_index, :]
        mask = self.mask[e_index, :]

        return states, actions, pi, r, done, self.length[e_index], mask

    def sample_episode_batch(self, batch_size=32):
        states_b = []
        actions_b = []
        pi_b = []
        r_b = []
        done_b = []
        length_b = []
        mask_b = []
        for i in range(batch_size):
            states, actions, pi, r, done, length, mask = self.sample_episode()
            states_b.append(states)
            actions_b.append(actions)
            pi_b.append(pi)
            r_b.append(r)
            done_b.append(done)
            length_b.append(length)
            mask_b.append(mask)

        max_l = max(length_b)
        states_b = np.stack(states_b, axis=0)[:, :max_l+1]
        actions_b = np.stack(actions_b, axis=0)[:, :max_l]
        pi_b = np.stack(pi_b, axis=0)[:, :max_l]
        r_b = np.stack(r_b, axis=0)[:, :max_l]
        done_b = np.stack(done_b, axis=0)
        mask_b = np.stack(mask_b, axis=0)
        # weights = np.ones(batch_size, dtype=np.float32)
        weights = np.array(length_b, dtype=np.float32) * self.size / self.sum_steps

        return states_b, actions_b, pi_b, r_b, done_b, length_b, mask_b, None, weights

    def save(self, path=''):
        parameters = np.array([self.size, self.max_episodes, self.episode_length])
        np.savez(path, parameters=parameters, states=self.states, actions=self.actions, rewards=self.r, probs=self.pi, length=self.length, mask=self.mask, done=self.done)
        pass


class ReplayBufferWithVision:
    def __init__(self, img_w, img_h, img_channel, state_dim, action_dim, max_episodes=1000, episode_length=50):
        self.length = np.zeros((max_episodes,), dtype=np.int)
        self.actions = np.zeros((max_episodes, episode_length, action_dim), dtype=np.float32)
        self.images = np.zeros((max_episodes, episode_length + 1, img_channel, img_w, img_h), dtype=np.float32)
        self.states = np.zeros((max_episodes, episode_length + 1, state_dim), dtype=np.float32)
        self.pi = np.zeros((max_episodes, episode_length,), dtype=np.float32)
        self.r = np.zeros((max_episodes, episode_length,), dtype=np.float32)
        self.done = np.zeros((max_episodes,), dtype=np.bool)

        self.size = self.tail = 0
        self.max_episodes = max_episodes
        pass

    def append(self, images, states, actions, pi, r, done):
        length = len(actions)
        self.length[self.tail] = length
        self.done[self.tail] = done
        self.images[self.tail][:length + 1] = images
        self.states[self.tail][:length + 1] = states
        self.actions[self.tail][:length] = actions
        self.pi[self.tail][:length] = pi
        self.r[self.tail][:length] = r
        self.tail = (self.tail + 1) % self.max_episodes
        self.size = min(self.size + 1, self.max_episodes)

    def sample_trajectory(self, length=32):
        e_length = 0
        while e_length <= 1:
            e_index = np.random.randint(low=0, high=self.size)
            e_length = self.length[e_index]
        l = np.random.randint(low=0, high=e_length)
        if l + length > e_length:
            length = e_length - l

        if l + length == e_length and self.done[e_index]:
            done = True
        else:
            done = False

        states = self.states[e_index, l:l + length + 1]
        images = self.images[e_index, l:l + length + 1]
        actions = self.actions[e_index, l:l + length]
        r = self.r[e_index, l:l + length]
        pi = self.pi[e_index, l:l + length]
        return images, states, actions, pi, r, done

    def sample_episode(self):
        e_length = 0
        while e_length <= 1:
            e_index = np.random.randint(low=0, high=self.size)
            e_length = self.length[e_index]
        if self.done[e_index]:
            done = True
        else:
            done = False

        images = self.images[e_index, :]
        states = self.states[e_index, :]
        actions = self.actions[e_index, :]
        r = self.r[e_index, :]
        pi = self.pi[e_index, :]

        return images, states, actions, pi, r, done

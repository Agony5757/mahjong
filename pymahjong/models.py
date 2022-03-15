import warnings

import gym
import torch
import torch.nn as nn
import numpy as np
import time

import torch.nn.functional as F
import torch.distributions as dis
from gym.spaces import Box, Discrete

torch.set_default_dtype(torch.float32)

INFINITY = 1e9


class VLOG(nn.Module):

    def __init__(self, observation_space, oracle_observation_space, action_space, is_main_network=True, **kwargs):

        ## For the source code of training, please see

        super(VLOG, self).__init__()


    def select(self, x, action_mask=None, greedy=True):

        with torch.no_grad():

            if action_mask is not None:
                action_mask = torch.from_numpy(
                    action_mask.astype(np.float32).reshape([1, self.action_size]))

            x = torch.from_numpy(x.astype(np.float32).reshape([1, *list(x.shape)])).to(device=self.device)

            x = self.encoder(x)
            e = self.forward_fnn(x)
            muz = self.f_h2muzp(e)
            logsigz = self.f_h2logsigzp(e)
            dist = dis.normal.Normal(muz, torch.exp(logsigz))
            z = dist.sample()

            self.h_t = z
            self.zp_tm1 = z

            if self.algorithm == 'bc':

                a = self.f_s2pi0.sample_action(self.h_t, action_mask=action_mask, greedy=greedy).item()

            elif self.algorithm == 'ddqn':
                q = self.f_s2q(self.h_t).detach().cpu()
                if action_mask is not None:
                    q = q.clamp(-INFINITY, INFINITY) * action_mask - 2 * INFINITY * (1 - action_mask)

                if greedy:
                    a = torch.argmax(q, dim=-1)
                    if np.prod(a.shape) == 1:
                        a = a.item()  # discrete action
                else:
                    if np.random.rand() < self.epsilon:
                        if action_mask is None:
                            a = np.random.randint(self.action_size)
                        else:
                            valid_action_ind = np.nonzero(action_mask.cpu().numpy().reshape([-1]))
                            valid_actions = np.arange(self.action_size)[valid_action_ind]
                            a = int(valid_actions[np.random.randint(len(valid_actions))])
                    else:
                        a = torch.argmax(q, dim=-1)
                        if np.prod(a.shape) == 1:
                            a = int(a.item())  # discrete action

        return a

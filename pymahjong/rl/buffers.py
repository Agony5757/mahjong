"""Rollout buffer with action masks (PPO + GAE).

Encoding-agnostic: observations are stored as raw dicts and collated
into tensors at minibatch iteration time via a caller-supplied
``collate_obs`` function.  This lets the same buffer work with V3
(token-based) and V4 (event-stream) observation formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

import numpy as np
import torch

from .action_space import ACTION_DIM


@dataclass
class RolloutBuffer:
    """Fixed-size rollout buffer for masked PPO.

    Observations are stored as raw dicts (the format returned by the
    environment).  Scalar arrays (actions, rewards, etc.) are
    pre-allocated for fast random access.

    Args:
        capacity: maximum number of transitions.
        gamma: discount factor for GAE.
        lam: lambda for GAE.
        device: torch device string for minibatch tensors.
    """

    capacity: int
    gamma: float = 0.99
    lam: float = 0.95
    device: str = "cpu"

    _obs: List[Dict] = field(default_factory=list, init=False, repr=False)
    actions: np.ndarray = field(init=False, repr=False)
    log_probs: np.ndarray = field(init=False, repr=False)
    values: np.ndarray = field(init=False, repr=False)
    rewards: np.ndarray = field(init=False, repr=False)
    dones: np.ndarray = field(init=False, repr=False)
    advantages: np.ndarray = field(init=False, repr=False)
    returns: np.ndarray = field(init=False, repr=False)
    size: int = field(default=0, init=False, repr=False)

    def __post_init__(self):
        c = self.capacity
        self._obs = []
        self.actions = np.zeros((c,), dtype=np.int64)
        self.log_probs = np.zeros((c,), dtype=np.float32)
        self.values = np.zeros((c,), dtype=np.float32)
        self.rewards = np.zeros((c,), dtype=np.float32)
        self.dones = np.zeros((c,), dtype=bool)
        self.advantages = np.zeros((c,), dtype=np.float32)
        self.returns = np.zeros((c,), dtype=np.float32)

    def add(
        self,
        obs: Dict,
        action: int,
        log_prob: float,
        value: float,
        reward: float,
        done: bool,
    ):
        i = self.size
        self._obs.append(obs)
        self.actions[i] = action
        self.log_probs[i] = log_prob
        self.values[i] = value
        self.rewards[i] = reward
        self.dones[i] = done
        self.size += 1

    def reset(self):
        self._obs.clear()
        self.size = 0

    def compute_gae(self, last_value: float = 0.0):
        """Compute GAE advantages and discounted returns in-place."""
        adv = 0.0
        for t in reversed(range(self.size)):
            next_value = last_value if t == self.size - 1 else self.values[t + 1]
            next_non_terminal = 0.0 if self.dones[t] else 1.0
            delta = self.rewards[t] + self.gamma * next_value * next_non_terminal - self.values[t]
            adv = delta + self.gamma * self.lam * next_non_terminal * adv
            self.advantages[t] = adv
        self.returns[: self.size] = self.advantages[: self.size] + self.values[: self.size]

    def iterate_minibatches(self, batch_size: int, collate_obs: Callable):
        """Yield minibatches as torch tensor dicts.

        Args:
            batch_size: number of transitions per minibatch.
            collate_obs: ``fn(list[obs_dict]) -> dict[str, Tensor]``
                that converts a list of raw observation dicts into a
                batched tensor dict (e.g. :func:`ppo_obs_collate` for V3
                or ``cached_event_collate`` for V4).
        """
        idxs = np.random.permutation(self.size)
        for start in range(0, self.size, batch_size):
            mb = idxs[start : start + batch_size]
            obs_batch = [self._obs[i] for i in mb]
            obs_tensors = collate_obs(obs_batch)
            d = self.device
            obs_tensors = {k: v.to(d) for k, v in obs_tensors.items()}
            obs_tensors["actions"] = torch.as_tensor(self.actions[mb], device=d, dtype=torch.long)
            obs_tensors["old_log_probs"] = torch.as_tensor(self.log_probs[mb], device=d, dtype=torch.float32)
            obs_tensors["old_values"] = torch.as_tensor(self.values[mb], device=d, dtype=torch.float32)
            obs_tensors["advantages"] = torch.as_tensor(self.advantages[mb], device=d, dtype=torch.float32)
            obs_tensors["returns"] = torch.as_tensor(self.returns[mb], device=d, dtype=torch.float32)
            yield obs_tensors


# Backward compatibility re-export.
from .v3.collate import ppo_obs_collate  # noqa: E402,F401

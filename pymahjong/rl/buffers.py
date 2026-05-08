"""Rollout buffer with action masks (PPO + GAE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import torch

from .tokenization import ACTION_DIM, MAX_SEQ_LEN, TOKEN_FEATURES


@dataclass
class RolloutBuffer:
    """Fixed-size rollout buffer for masked PPO.

    All arrays are pre-allocated. Use :meth:`add` to append a transition
    and :meth:`compute_gae` once the rollout is collected.
    """

    capacity: int
    max_seq_len: int = MAX_SEQ_LEN
    gamma: float = 0.99
    lam: float = 0.95
    device: str = "cpu"

    def __post_init__(self):
        c = self.capacity
        L = self.max_seq_len
        self.tokens = np.zeros((c, L, TOKEN_FEATURES), dtype=np.int32)
        self.attn_mask = np.zeros((c, L), dtype=bool)
        self.action_mask = np.zeros((c, ACTION_DIM), dtype=bool)
        self.actions = np.zeros((c,), dtype=np.int64)
        self.log_probs = np.zeros((c,), dtype=np.float32)
        self.values = np.zeros((c,), dtype=np.float32)
        self.rewards = np.zeros((c,), dtype=np.float32)
        self.dones = np.zeros((c,), dtype=bool)
        self.advantages = np.zeros((c,), dtype=np.float32)
        self.returns = np.zeros((c,), dtype=np.float32)
        self.size = 0

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
        self.tokens[i] = obs["tokens"]
        self.attn_mask[i] = obs["attention_mask"]
        self.action_mask[i] = obs["action_mask"]
        self.actions[i] = action
        self.log_probs[i] = log_prob
        self.values[i] = value
        self.rewards[i] = reward
        self.dones[i] = done
        self.size += 1

    def reset(self):
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

    def iterate_minibatches(self, batch_size: int):
        idxs = np.random.permutation(self.size)
        for start in range(0, self.size, batch_size):
            mb = idxs[start : start + batch_size]
            yield self._to_torch(mb)

    def _to_torch(self, mb):
        d = self.device
        return {
            "tokens": torch.as_tensor(self.tokens[mb], device=d, dtype=torch.long),
            "attention_mask": torch.as_tensor(self.attn_mask[mb], device=d, dtype=torch.bool),
            "action_mask": torch.as_tensor(self.action_mask[mb], device=d, dtype=torch.bool),
            "actions": torch.as_tensor(self.actions[mb], device=d, dtype=torch.long),
            "old_log_probs": torch.as_tensor(self.log_probs[mb], device=d, dtype=torch.float32),
            "old_values": torch.as_tensor(self.values[mb], device=d, dtype=torch.float32),
            "advantages": torch.as_tensor(self.advantages[mb], device=d, dtype=torch.float32),
            "returns": torch.as_tensor(self.returns[mb], device=d, dtype=torch.float32),
        }

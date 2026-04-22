# Custom Agents

This guide explains how to implement custom agents for pymahjong.

## Agent Interface

A custom agent should implement the following interface:

```python
class CustomAgent:
    def select(self, observation, action_mask):
        """
        Select an action given observation and valid action mask.

        Args:
            observation: numpy array of shape (93, 34) or (111, 34)
            action_mask: numpy array of shape (54,), 1 for valid actions

        Returns:
            int: action index
        """
        raise NotImplementedError
```

## Example: Random Agent

```python
import numpy as np

class RandomAgent:
    def select(self, observation, action_mask):
        valid_actions = np.where(action_mask)[0]
        return np.random.choice(valid_actions)
```

## Example: Neural Network Agent

```python
import numpy as np
import torch
import torch.nn as nn

class NeuralNetworkAgent(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(93, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(64, 64, kernel_size=3, padding=1)
        self.fc = nn.Linear(64 * 34, 54)

    def forward(self, x):
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        x = x.view(x.size(0), -1)
        return self.fc(x)

    def select(self, observation, action_mask):
        self.eval()
        with torch.no_grad():
            x = torch.FloatTensor(observation).unsqueeze(0)
            logits = self.forward(x).squeeze(0)

            # Mask invalid actions
            logits[~torch.BoolTensor(action_mask)] = float('-inf')

            action = torch.argmax(logits).item()
        return action
```

## Using Custom Agents

### In Multi-agent Environment

```python
import pymahjong

env = pymahjong.MahjongEnv()
agents = [CustomAgent() for _ in range(4)]

env.reset()
while not env.is_over():
    player_id = env.get_curr_player_id()
    obs = env.get_obs(player_id)
    mask = env.get_valid_actions(nhot=True)

    action = agents[player_id].select(obs, mask)
    env.step(player_id, action)
```

### As Opponents in Single-agent

Modify `SingleAgentMahjongEnv` or create your own wrapper:

```python
import pymahjong

class CustomOpponentEnv:
    def __init__(self, opponent_agent):
        self.env = pymahjong.MahjongEnv()
        self.opponent = opponent_agent
        self.player_id = 0  # Your agent is player 0

    def reset(self):
        self.env.reset()
        self._proceed_to_agent()
        return self.env.get_obs(self.player_id)

    def step(self, action):
        self.env.step(self.player_id, action)
        self._proceed_to_agent()

        if self.env.is_over():
            reward = self.env.get_payoffs()[self.player_id]
            return self.env.get_obs(self.player_id), reward, True, {}
        return self.env.get_obs(self.player_id), 0, False, {}

    def _proceed_to_agent(self):
        while not self.env.is_over() and self.env.get_curr_player_id() != self.player_id:
            pid = self.env.get_curr_player_id()
            obs = self.env.get_obs(pid)
            mask = self.env.get_valid_actions(nhot=True)
            action = self.opponent.select(obs, mask)
            self.env.step(pid, action)

    def get_valid_actions(self):
        return self.env.get_valid_actions()
```

## Training with RL

### Using Stable-Baselines3

```python
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import pymahjong
import gymnasium as gym

# Create a gym-compatible wrapper
class MahjongGymWrapper(gym.Env):
    def __init__(self):
        super().__init__()
        self.env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")
        self.observation_space = self.env.observation_space
        self.action_space = self.env.action_space

    def reset(self, **kwargs):
        return self.env.reset(), {}

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        return obs, reward, done, False, info

# Train
env = DummyVecEnv([lambda: MahjongGymWrapper()])
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=100000)
```

## Tips for Training

1. **Use action masking**: Always mask invalid actions during training
2. **Normalize observations**: Observations are already in [0, 1] range
3. **Sparse rewards**: Rewards are only non-zero at game end
4. **Episode length**: Mahjong games can be long (50-100 steps per player)
5. **Curriculum learning**: Start with simpler opponents, gradually increase difficulty

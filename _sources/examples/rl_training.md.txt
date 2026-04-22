# RL Training Example

This example shows how to train a reinforcement learning agent with pymahjong.

## Setup

```bash
pip install pymahjong torch stable-baselines3
```

## PPO with Stable-Baselines3

```python
import gymnasium as gym
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import EvalCallback
import pymahjong


class MahjongGymWrapper(gym.Env):
    """Gymnasium wrapper for SingleAgentMahjongEnv."""

    def __init__(self, opponent_agent="random"):
        super().__init__()
        self.env = pymahjong.SingleAgentMahjongEnv(opponent_agent=opponent_agent)
        self.observation_space = self.env.observation_space
        self.action_space = self.env.action_space

    def reset(self, **kwargs):
        obs, info = self.env.reset()
        return obs, info

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        return obs, reward, done, False, info

    def get_valid_actions(self, nhot=False):
        return self.env.get_valid_actions(nhot=nhot)


class ActionMaskWrapper(gym.ActionWrapper):
    """Mask invalid actions by sampling from valid ones."""

    def __init__(self, env):
        super().__init__(env)

    def action(self, action):
        # The action is already validated by our custom policy
        return action

    def valid_actions(self):
        return self.env.get_valid_actions()


def make_env():
    return ActionMaskWrapper(MahjongGymWrapper(opponent_agent="random"))


# Create vectorized environment
env = DummyVecEnv([make_env for _ in range(4)])

# Create PPO model
model = PPO(
    "MlpPolicy",
    env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    verbose=1,
)

# Train
model.learn(total_timesteps=1_000_000)

# Save
model.save("ppo_mahjong")
```

## Custom Policy with Action Masking

```python
import torch
import torch.nn as nn
from stable_baselines3.common.policies import ActorCriticPolicy


class MaskedActorCriticPolicy(ActorCriticPolicy):
    """Policy that properly handles action masking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def forward(self, obs, deterministic=False):
        # Get base outputs
        latent_pi, latent_vf, latent_sde = self._get_latent(obs)

        # Evaluate actions
        actions, values, log_prob = self._evaluate_actions(
            latent_pi, latent_vf, latent_sde, obs, deterministic=deterministic
        )

        # Get valid actions from environment (if available)
        # This requires passing action mask through observation or separate channel
        return actions, values, log_prob

    def _get_action_distribution(self, obs):
        # Override to add action masking
        latent_pi = self.extract_features(obs)
        latent_pi = self.mlp_extractor.forward_actor(latent_pi)
        logits = self.action_net(latent_pi)

        # Apply mask (requires mask in obs or separate handling)
        # This is a simplified example
        return self._get_distribution(logits)


# Use custom policy
model = PPO(
    MaskedActorCriticPolicy,
    env,
    verbose=1,
)
```

## PyTorch DQN Implementation

```python
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import random
import pymahjong


class DQNNetwork(nn.Module):
    def __init__(self, obs_dim, action_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(obs_dim, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, action_dim),
        )

    def forward(self, x):
        return self.net(x)


class DQNAgent:
    def __init__(self, obs_shape=(93, 34), action_dim=54):
        self.obs_dim = np.prod(obs_shape)
        self.action_dim = action_dim

        self.q_network = DQNNetwork(self.obs_dim, action_dim)
        self.target_network = DQNNetwork(self.obs_dim, action_dim)
        self.target_network.load_state_dict(self.q_network.state_dict())

        self.optimizer = optim.Adam(self.q_network.parameters(), lr=1e-4)
        self.memory = deque(maxlen=100000)

        self.batch_size = 64
        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.1
        self.epsilon_decay = 0.9995

    def select_action(self, obs, valid_actions):
        if random.random() < self.epsilon:
            return random.choice(valid_actions)

        with torch.no_grad():
            x = torch.FloatTensor(obs).flatten().unsqueeze(0)
            q_values = self.q_network(x).squeeze()

            # Mask invalid actions
            mask = torch.full((self.action_dim,), float('-inf'))
            mask[valid_actions] = 0
            q_values = q_values + mask

            return q_values.argmax().item()

    def store(self, obs, action, reward, next_obs, done):
        self.memory.append((obs, action, reward, next_obs, done))

    def train(self):
        if len(self.memory) < self.batch_size:
            return

        batch = random.sample(self.memory, self.batch_size)
        obs, actions, rewards, next_obs, dones = zip(*batch)

        obs = torch.FloatTensor(np.array([o.flatten() for o in obs]))
        actions = torch.LongTensor(actions)
        rewards = torch.FloatTensor(rewards)
        next_obs = torch.FloatTensor(np.array([o.flatten() for o in next_obs]))
        dones = torch.FloatTensor(dones)

        current_q = self.q_network(obs).gather(1, actions.unsqueeze(1))
        with torch.no_grad():
            next_q = self.target_network(next_obs).max(1)[0]
            target_q = rewards + self.gamma * next_q * (1 - dones)

        loss = nn.MSELoss()(current_q.squeeze(), target_q)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def update_target(self):
        self.target_network.load_state_dict(self.q_network.state_dict())


def train_dqn():
    env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")
    agent = DQNAgent()

    num_episodes = 10000
    target_update_freq = 100

    for episode in range(num_episodes):
        obs, _ = env.reset()
        total_reward = 0

        while True:
            valid_actions = env.get_valid_actions()
            action = agent.select_action(obs, valid_actions)

            next_obs, reward, done, info = env.step(action)
            agent.store(obs, action, reward, next_obs, done)

            obs = next_obs
            total_reward += reward

            agent.train()

            if done:
                break

        if episode % target_update_freq == 0:
            agent.update_target()

        if episode % 100 == 0:
            print(f"Episode {episode}, Reward: {total_reward:.2f}, Epsilon: {agent.epsilon:.3f}")

    return agent


if __name__ == "__main__":
    agent = train_dqn()
    torch.save(agent.q_network.state_dict(), "dqn_mahjong.pth")
```

## Evaluation

```python
def evaluate_agent(agent, num_games=100):
    """Evaluate agent performance."""
    env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")

    rewards = []
    wins = 0

    for _ in range(num_games):
        obs, _ = env.reset()
        total_reward = 0

        while True:
            valid_actions = env.get_valid_actions()

            # Use trained agent
            action = agent.select_action(obs, valid_actions)

            obs, reward, done, info = env.step(action)
            total_reward += reward

            if done:
                rewards.append(total_reward)
                if total_reward > 0:
                    wins += 1
                break

    print(f"Average reward: {np.mean(rewards):.2f} ± {np.std(rewards):.2f}")
    print(f"Win rate: {wins / num_games * 100:.1f}%")

    return rewards
```

## Tips for Training

1. **Sparse Rewards**: Mahjong has sparse rewards (only at game end). Consider:
   - Using high gamma (0.99+)
   - Adding intermediate rewards for tenpai, riichi, etc.

2. **Long Episodes**: Games can be 50-150 steps. Consider:
   - Using n-step returns
   - Adding episode length normalization

3. **Action Masking**: Always use action masking to prevent invalid actions

4. **Opponent Strength**: Start with random opponents, gradually increase difficulty

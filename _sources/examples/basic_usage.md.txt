# Basic Usage

This example demonstrates the basic usage of pymahjong.

## Single-agent Environment

```python
import pymahjong
import numpy as np

# Create environment with random opponents
env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")

# Reset and get initial observation
obs, info = env.reset()

total_reward = 0
step = 0

while True:
    # Get valid actions
    valid_actions = env.get_valid_actions()

    # Random action selection
    action = np.random.choice(valid_actions)

    # Step the environment
    obs, reward, done, truncated, info = env.step(action)
    total_reward += reward
    step += 1

    if done:
        print(f"Game finished in {step} steps")
        print(f"Final payoff: {total_reward}")
        break

print(f"Average reward per step: {total_reward / step:.4f}")
```

## Multi-agent Environment

```python
import pymahjong
import numpy as np

env = pymahjong.MahjongEnv()

num_games = 10
results = []

for game in range(num_games):
    env.reset()
    steps = 0

    while not env.is_over():
        # Get current player
        player_id = env.get_curr_player_id()

        # Get observation and valid actions
        obs = env.get_obs(player_id)
        valid_actions = env.get_valid_actions()

        # Random decision
        action = np.random.choice(valid_actions)

        # Execute action
        env.step(player_id, action)
        steps += 1

    # Record results
    payoffs = env.get_payoffs()
    results.append(payoffs)
    print(f"Game {game + 1}: steps={steps}, payoffs={payoffs}")

# Statistics
results = np.array(results)
print(f"\nAverage payoffs over {num_games} games:")
for i in range(4):
    print(f"  Player {i}: {results[:, i].mean():.2f} ± {results[:, i].std():.2f}")
```

## Using Oracle Observation

```python
import pymahjong
import numpy as np

env = pymahjong.MahjongEnv()
env.reset()

# Get different observation types
player_id = env.get_curr_player_id()

# Executor observation (visible game state)
executor_obs = env.get_obs(player_id)
print(f"Executor observation shape: {executor_obs.shape}")  # (93, 34)

# Oracle observation (hidden information)
oracle_obs = env.get_oracle_obs(player_id)
print(f"Oracle observation shape: {oracle_obs.shape}")  # (18, 34)

# Full observation
full_obs = env.get_full_obs(player_id)
print(f"Full observation shape: {full_obs.shape}")  # (111, 34)

# Verify concatenation
assert np.array_equal(full_obs, np.concatenate([executor_obs, oracle_obs], axis=0))
```

## Action Masking

```python
import pymahjong
import numpy as np

env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")
obs, info = env.reset()

# Get valid actions as indices
valid_indices = env.get_valid_actions()
print(f"Valid action indices: {valid_indices}")

# Get valid actions as one-hot mask
valid_mask = env.get_valid_actions(nhot=True)
print(f"Valid action mask shape: {valid_mask.shape}")  # (54,)
print(f"Number of valid actions: {valid_mask.sum()}")

# Example: softmax with masking
def masked_softmax(logits, mask):
    """Apply softmax only to valid actions."""
    logits = logits.copy()
    logits[~mask] = -np.inf  # Set invalid actions to -inf
    exp_logits = np.exp(logits - logits.max())  # Numerical stability
    return exp_logits / exp_logits.sum()

# Simulate policy network output
logits = np.random.randn(54)
probs = masked_softmax(logits, valid_mask)
print(f"Action probabilities sum: {probs.sum():.4f}")  # Should be 1.0

# Sample from distribution
action = np.random.choice(54, p=probs)
print(f"Sampled action: {action}")
```

## Game State Inspection

```python
import pymahjong as pm

env = pm.MahjongEnv()
env.reset()

# Access the underlying C++ Table
table = env.t

print(f"Current turn: {table.turn}")
print(f"Game wind: {table.game_wind}")
print(f"Parent (oya): {table.oya}")
print(f"Honba: {table.honba}")
print(f"Kyoutaku (riichi sticks): {table.kyoutaku}")

# Player information
for i, player in enumerate(table.players):
    print(f"\nPlayer {i}:")
    print(f"  Score: {player.score}")
    print(f"  Riichi: {player.riichi}")
    print(f"  Tenpai: {player.is_tenpai()}")

# Dora information
dora = table.get_dora()
print(f"\nDora indicators: {[str(d) for d in dora]}")

# Remaining tiles
print(f"Remaining tiles: {table.get_remain_tile()}")
```

## Custom Game Initialization

```python
import pymahjong as pm

env = pm.MahjongEnv()

# Custom initialization
env.reset(
    oya=2,              # Player 2 is parent
    game_wind="south", # South round
    seed=42            # Fixed random seed
)

print(f"Parent: {env.t.oya}")
print(f"Game wind: {env.t.game_wind}")

# With specific initial scores
env.reset(
    scores=[30000, 25000, 20000, 25000]
)
for i, player in enumerate(env.t.players):
    print(f"Player {i} score: {player.score}")
```

## Rendering

```python
import pymahjong as pm

env = pm.MahjongEnv()
env.reset()

# Text-based rendering
env.render()

# Output example:
# ----------- current player: 0 -----------------
# [Player 0]
# Hand: 1m 2m 3m 4m 5m 6m 7m 8m 9m 1p 2p 3p 4p
# River: 5p(1) 6p(2)
# ...
```

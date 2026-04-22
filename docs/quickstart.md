# Quick Start

This guide will help you get started with pymahjong quickly.

## Single-agent Environment

The single-agent environment is similar to standard OpenAI Gym environments. Your agent plays against 3 opponents.

### Basic Usage

```python
import pymahjong
import numpy as np

# Create environment with random opponents
env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")

# Reset and get initial observation
obs = env.reset()

while True:
    # Get valid actions at current step
    valid_actions = env.get_valid_actions()

    # Select a random valid action
    action = np.random.choice(valid_actions)

    # Step the environment
    obs, reward, done, info = env.step(action)

    if done:
        print(f"Game over! Payoff: {reward}")
        break
```

### Using Pretrained Opponents

```python
import pymahjong

# Load environment with pretrained VLOG opponents
env = pymahjong.SingleAgentMahjongEnv(
    opponent_agent="path/to/mahjong_VLOG_CQL.pth"
)

obs = env.reset()
# ... same as above
```

## Multi-agent Environment

In the multi-agent environment, 4 agents play against each other.

### Basic Usage

```python
import pymahjong
import numpy as np

env = pymahjong.MahjongEnv()

for game in range(10):
    env.reset()

    while not env.is_over():
        # Get current player ID
        curr_player_id = env.get_curr_player_id()

        # Get observation and valid actions
        obs = env.get_obs(curr_player_id)
        valid_actions = env.get_valid_actions()

        # Make a random decision
        action = np.random.choice(valid_actions)
        env.step(curr_player_id, action)

    # Get final payoffs
    payoffs = env.get_payoffs()
    print(f"Game {game}, payoffs: {payoffs}")
```

## Observation Space

The observation is a boolean matrix:

- **Executor observation**: Shape `(93, 34)` - visible game state
- **Oracle observation**: Shape `(18, 34)` - hidden information (opponents' hands)
- **Full observation**: Shape `(111, 34)` - concatenated

```python
# Get different observations
obs = env.get_obs(player_id)           # Executor observation (93, 34)
oracle = env.get_oracle_obs(player_id) # Oracle observation (18, 34)
full = env.get_full_obs(player_id)     # Full observation (111, 34)
```

The 34 columns represent:
- Characters (Man): 1-9
- Dots (Pin): 1-9
- Bamboo (Sou): 1-9
- Winds: East, South, West, North
- Dragons: White, Green, Red

## Action Space

There are 54 discrete actions. Not all actions are valid at each step.

```python
# Get valid action indices
valid_actions = env.get_valid_actions()  # e.g., [0, 3, 4, 20, 21]

# Get one-hot mask of valid actions
mask = env.get_valid_actions(nhot=True)  # Shape (54,)
```

### Action Types

| Index Range | Action Type |
|-------------|-------------|
| 0-33 | Discard tile (0-33) |
| 34-36 | Discard red dora 5m/5p/5s |
| 37-42 | Chi (left/middle/right, with/without red) |
| 43-44 | Pon (with/without red) |
| 45 | AnKan (concealed kan) |
| 46 | MinKan (open kan) |
| 47 | KaKan (added kan) |
| 48 | Riichi |
| 49 | Ron |
| 50 | Tsumo |
| 51 | Push (kyushukyuhai) |
| 52 | Pass (during riichi decision) |
| 53 | Pass (response) |

## Game Initialization

```python
# Default initialization
env.reset()

# Custom initialization
env.reset(
    oya=0,              # Parent player (0-3)
    game_wind="east",   # Game wind
    seed=42             # Random seed
)
```

## Rendering

For debugging, you can print the game state:

```python
env.render()
```

This displays each player's hand and river in text format.

## Next Steps

- [API Reference](api/index.md) - Detailed API documentation
- [Examples](examples/index.md) - More usage examples
- [Advanced Topics](advanced/index.md) - Custom agents and C++ engine

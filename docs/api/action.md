# Action Space

## Overview

The action space consists of 54 discrete actions. Not all actions are valid at each step - use `get_valid_actions()` to check.

## Action Indices

### Discard Actions (0-36)

| Index | Action | Description |
|-------|--------|-------------|
| 0-33 | Discard | Discard tile type 0-33 |
| 34 | Discard Red 5m | Discard red 5 Man |
| 35 | Discard Red 5p | Discard red 5 Pin |
| 36 | Discard Red 5s | Discard red 5 Sou |

### Chi Actions (37-42)

| Index | Action | Description |
|-------|--------|-------------|
| 37 | Chi Left | Chi with tiles tile+1, tile+2 |
| 38 | Chi Middle | Chi with tiles tile-1, tile+1 |
| 39 | Chi Right | Chi with tiles tile-2, tile-1 |
| 40 | Chi Left (Red) | Chi Left using red dora |
| 41 | Chi Middle (Red) | Chi Middle using red dora |
| 42 | Chi Right (Red) | Chi Right using red dora |

### Pon Actions (43-44)

| Index | Action | Description |
|-------|--------|-------------|
| 43 | Pon | Pon without using red dora |
| 44 | Pon (Red) | Pon using red dora |

### Kan Actions (45-47)

| Index | Action | Description |
|-------|--------|-------------|
| 45 | AnKan | Concealed kan |
| 46 | MinKan | Open kan (daiminkan) |
| 47 | KaKan | Added kan (kakan) |

### Special Actions (48-53)

| Index | Action | Description |
|-------|--------|-------------|
| 48 | Riichi | Declare riichi |
| 49 | Ron | Win by ron |
| 50 | Tsumo | Win by tsumo |
| 51 | Push | Kyushukyuhai (nine terminals) |
| 52 | Pass Riichi | Pass on riichi decision |
| 53 | Pass Response | Pass on response |

## Riichi Mechanism

Riichi is a two-step action:

1. **First step**: Discard a tile that can be riichi-declared
2. **Second step**: Choose between Riichi (48) or Pass Riichi (52)

```python
# Example riichi flow
if 48 in valid_actions:
    # Player can declare riichi
    # First, discard a riichi tile
    riichi_tiles = pm.encv1_get_riichi_tiles(env.t)
    action = riichi_tiles[0]  # Discard first available riichi tile
    env.step(player_id, action)

    # Second step: declare riichi or pass
    valid_actions = env.get_valid_actions()
    # valid_actions will be [48, 52]
    env.step(player_id, 48)  # Declare riichi
```

## Getting Valid Actions

```python
# Get list of valid action indices
valid_actions = env.get_valid_actions()
# Example: [0, 1, 2, 5, 6, 7, 48]

# Get one-hot mask
mask = env.get_valid_actions(nhot=True)
# Shape: (54,), 1 for valid actions, 0 for invalid
```

## Action Constants

The environment provides action constants for convenience:

```python
from pymahjong.env_pymahjong import MahjongEnv

env = MahjongEnv()

# Action indices
env.CHILEFT      # 37
env.CHIMIDDLE    # 38
env.CHIRIGHT     # 39
env.PON          # 43
env.ANKAN        # 45
env.MINKAN       # 46
env.KAKAN        # 47
env.RIICHI       # 48
env.RON          # 49
env.TSUMO        # 50
env.PUSH         # 51
env.PASS_RIICHI  # 52
env.PASS_RESPONSE # 53
```

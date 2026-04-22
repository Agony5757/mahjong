# Paipu Replay

Paipu (牌譜) is the Japanese term for game records. pymahjong supports replaying games from Tenhou.net paipu files for validation and analysis.

## Overview

The paipu replay system allows you to:

1. Validate the game engine against real game records
2. Analyze professional player decisions
3. Generate training data from human games

## Using Paipu Replay

### Basic Usage

```python
import pymahjong as pm

# Replay paipu files in the current directory
pm.paipu_replay(mode='debug')
```

### Replay Modes

| Mode | Description |
|------|-------------|
| `'debug'` | Print detailed information for debugging |
| `'normal'` | Standard replay without verbose output |

### Paipu Format

pymahjong supports Tenhou.net XML format paipu files. The expected structure:

```
paipuxmls/
├── mjlog_2020010101gm-xxxx-xxxx-xxxx.xml
├── mjlog_2020010102gm-xxxx-xxxx-xxxx.xml
└── ...
```

## C++ PaipuReplayer

The `PaipuReplayer` class provides low-level control:

```python
import MahjongPyWrapper as pm

# Create replayer
replayer = pm.PaipuReplayer()

# Initialize with game state
replayer.init(
    yama=[...],           # 136 tile IDs
    init_scores=[25000]*4,
    kyoutaku=0,
    honba=0,
    game_wind=0,          # 0=East, 1=South, etc.
    oya=0                 # Parent player
)

# Get available actions
phase = replayer.get_phase()
if phase < 4:
    actions = replayer.get_self_actions()
else:
    actions = replayer.get_response_actions()

# Make selection
replayer.make_selection(selection_index)

# Get result
result = replayer.get_result()
```

## Debug Mode

When debug mode is enabled, the game generates replayable code:

```python
import pymahjong as pm

env = pm.MahjongEnv()
env.reset(debug_mode=1)  # Enable debug mode

# ... play the game ...

# Get replay code
replay_code = env.t.get_debug_replay()
print(replay_code)
```

This outputs code that can be used to reproduce the exact game:

```python
Table table;
table.game_init_for_replay([...], [25000, 25000, 25000, 25000], 0, 0, 0, 0);
table.make_selection(0);
table.make_selection(1);
# ... etc
```

## Validation

The CI pipeline runs paipu replay validation:

1. Downloads paipu files from releases
2. Replays each game
3. Verifies that actions and outcomes match

This ensures the game engine correctly implements Mahjong rules.

## Downloading Paipu Data

Paipu files are available from:

- [Tenhou.net MJLog](https://tenhou.net/mjlog/)
- [Project Releases](https://github.com/Agony5757/mahjong/releases)

### Offline Dataset

Pre-processed datasets are available for machine learning:

```python
import scipy.io

data = scipy.io.loadmat("mahjong_data.mat")

# data["X"] - Executor observation
# data["O"] - Oracle observation
# data["A"] - Actions taken
# data["M"] - Valid action masks
# data["R"] - Rewards
# data["D"] - Done signals
```

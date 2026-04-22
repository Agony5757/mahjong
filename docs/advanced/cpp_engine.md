# C++ Engine

pymahjong uses a C++ backend for high-performance game simulation. This section documents the C++ architecture.

## Architecture Overview

```
┌─────────────────────────────────────────┐
│              Python Layer               │
│  (pymahjong/env_pymahjong.py)          │
└─────────────────┬───────────────────────┘
                  │ pybind11
┌─────────────────▼───────────────────────┐
│            Pybinder Layer               │
│  (Pybinder/MahjongPy.cpp)               │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Mahjong Core               │
│  (Mahjong/Table.cpp, Player.cpp, etc.)  │
└─────────────────────────────────────────┘
```

## Core Classes

### Table

The central game state manager.

**File**: `Mahjong/Table.h`, `Mahjong/Table.cpp`

**Key Methods**:
- `game_init()` - Initialize a new game
- `get_phase()` - Get current game phase
- `get_self_actions()` - Get available self-actions
- `get_response_actions()` - Get available response actions
- `make_selection(int)` - Execute an action

**Phases**:
| Phase | Description |
|-------|-------------|
| `P1_ACTION` - `P4_ACTION` | Self-action phases |
| `P1_RESPONSE` - `P4_RESPONSE` | Response phases |
| `GAME_OVER` | Terminal state |

### Player

Manages individual player state.

**File**: `Mahjong/Player.h`, `Mahjong/Player.cpp`

**Key Attributes**:
- `hand` - Tiles in hand
- `river` - Discarded tiles
- `call_groups` - Melded tile groups
- `atari_tiles` - Winning tiles (if tenpai)
- `riichi` - Riichi status
- `score` - Player score

**Key Methods**:
- `get_discard()` - Generate discard actions
- `get_chi()` - Generate chi actions
- `get_pon()` - Generate pon actions
- `get_ron()` - Generate ron actions
- `update_atari_tiles()` - Update tenpai status

### Rule

Implements tile splitting and hand evaluation.

**File**: `Mahjong/Rule.h`, `Mahjong/Rule.cpp`

**Key Functions**:
- `get_completed_tiles()` - Find valid hand decompositions
- `get_atari_hai()` - Calculate waiting tiles
- `is_tenpai()` - Check tenpai status
- `is_riichi_able()` - Check if riichi is possible

### ScoreCounter

Evaluates yaku and calculates scores.

**File**: `Mahjong/ScoreCounter.h`, `Mahjong/ScoreCounter.cpp`

**Key Functions**:
- `count_yaku()` - Evaluate yaku for a winning hand
- `calculate_score()` - Calculate final score

### Action

Defines action types and selection.

**File**: `Mahjong/Action.h`, `Mahjong/Action.cpp`

**BaseAction Enum**:
```cpp
enum class BaseAction : uint8_t {
    Pass, Chi, Pon, Kan, Ron,      // Response
    ChanAnKan, ChanKan,            // Special response
    AnKan, KaKan, Discard, Riichi, // Self action
    Tsumo, Kyushukyuhai            // Special self
};
```

## Observation Encoding

**File**: `Mahjong/Encoding/TrainingDataEncodingV1.cpp`

The V1 encoding produces a 93x34 boolean matrix:

```cpp
void encode_table(const Table& table, int player_id, bool oracle, dtype* output);
void encode_actions_vector(const Table& table, int player_id, dtype* output);
```

V2 encoding provides more detailed features:
```cpp
// Mahjong/Encoding/TrainingDataEncodingV2.h
class TableEncoder {
    void init();
    void update();
    // ...
};
```

## Game Flow

```
game_init()
    │
    ▼
from_beginning() ─────► _generate_self_actions()
    │                              │
    │                              ▼
    │                      self_actions (list)
    │                              │
    ▼                              │
make_selection() ◄─────────────────┘
    │
    ▼
_handle_self_action()
    │
    ▼
_generate_response_actions()
    │
    ▼
response_actions (for each player)
    │
    ▼
make_selection() (x4)
    │
    ▼
_handle_response_final_execution()
    │
    ▼
from_beginning() (loop)
    │
    ▼
GAME_OVER
```

## Building from Source

### Requirements

- CMake 3.15+
- C++14 compiler
- Python 3.10+ with development headers

### Build Steps

```bash
mkdir build && cd build
cmake .. -DCMAKE_CXX_COMPILER=clang++
make -j$(nproc)
./bin/test  # Run C++ tests
```

### CMake Structure

```
CMakeLists.txt (root)
├── ThirdParty/CMakeLists.txt
│   ├── fmt/CMakeLists.txt
│   └── tenhou/CMakeLists.txt
├── Mahjong/CMakeLists.txt
├── Pybinder/CMakeLists.txt
└── test/CMakeLists.txt
```

## Performance

- **Memory**: ~800KB per game instance
- **Speed**: ~10ms per complete game (random play)
- **Optimization**: Uses lookup tables for shanten calculation

## Debugging

Enable debug mode to generate replay code:

```cpp
table.set_debug_mode(1);  // Buffer mode
table.set_debug_mode(2);  // Stdout mode

// ... play game ...

table.print_debug_replay();  // Print replay code
```

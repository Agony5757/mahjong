# C++ Engine API Reference

本节提供 Mahjong C++ 引擎的完整 API 参考文档，基于 `Mahjong/` 目录下的头文件和源文件生成。

```{toctree}
:maxdepth: 2

table
player
score_counter
tile_action
```

## 命名空间

所有 C++ 代码位于 `mahjong` 命名空间：

```cpp
namespace_mahjong      // #define NAMESPACE_BEGIN
namespace_mahjong_end  // #define NAMESPACE_END
```

包含方式：`#include "Tile.h"` 等，均已在 `macro.h` 中处理命名空间。

## 头文件依赖关系

```
macro.h          (工具宏)
  └── Tile.h    (BaseTile, Tile, CallGroup, 工具函数)
  └── Action.h  (BaseAction, Action, SelfAction, ResponseAction)
  └── Player.h  (Player, River, RiverTile)
  └── Yaku.h    (Yaku 枚举)
  └── GameLog.h (GameLog, BaseGameLog, LogAction)
  └── GameResult.h (Result, ResultType)
  └── ScoreCounter.h (ScoreCounter, CounterResult)
  └── Table.h   (Table, PhaseEnum) — 核心状态机
```

## 核心类概览

| 类 | 文件 | 职责 |
|---|------|------|
| `Table` | `Table.h` | 核心游戏状态、状态机、动作执行 |
| `Player` | `Player.h` | 玩家状态（手牌/河/鸣牌/得分） |
| `ScoreCounter` | `ScoreCounter.h` | 役种检测、符数计算、计分 |
| `Tile` | `Tile.h` | 牌表示、牌操作工具函数 |
| `Action` | `Action.h` | 动作类型和编码 |
| `GameLog` | `GameLog.h` | 游戏事件记录 |
| `GameResult` | `GameResult.h` | 结算结果 |
| `PaipuReplayer` | `GamePlay.h` | 牌谱重放 |

## 编译方式

```bash
mkdir build && cd build
cmake .. -DCMAKE_CXX_COMPILER=clang++
make -j$(nproc)
./bin/test
```

所有类均通过 `Pybinder/MahjongPy.cpp` 暴露给 Python。

# Table 类参考

`Table` 是引擎的核心类，管理整个游戏状态和状态机。

## 头文件

```cpp
#include "Table.h"
```

## 构造函数

```cpp
Table() = default;
```

默认构造函数，初始化所有成员为默认值。

## 公开成员

### 游戏状态

| 成员 | 类型 | 说明 |
|------|------|------|
| `tiles[136]` | `Tile[N_TILES]` | 牌堆（初始化后分配具体牌） |
| `yama` | `vector<Tile*>` | 牌山（剩余摸牌堆） |
| `dora_indicator` | `vector<Tile*>` | 宝牌指示牌 |
| `uradora_indicator` | `vector<Tile*>` | 里宝牌指示牌 |
| `n_active_dora` | `int` | 已翻开的宝牌数量 |
| `players[4]` | `array<Player, 4>` | 4名玩家 |
| `turn` | `int` | 当前行动玩家 ID (0-3) |
| `oya` | `int` | 庄家玩家 ID |
| `game_wind` | `Wind` | 场风（East/South/West/North） |
| `honba` | `int` | 本场数 |
| `kyoutaku` | `int` | 立直棒累计（1000点/棒） |
| `phase` | `PhaseEnum` | 当前阶段 |
| `result` | `Result` | 游戏结果 |
| `gamelog` | `GameLog` | 游戏日志 |

### 摸牌相关

| 成员 | 类型 | 说明 |
|------|------|------|
| `river_counter` | `int` | 巡目计数器 |

## 初始化方法

### `game_init()`

```cpp
void game_init();
```

初始化新游戏（随机洗牌），所有玩家 25000 点，东风场，庄家为玩家0。

### `game_init_with_config()`

```cpp
void game_init_with_config(
    const std::vector<int>& yama,      // 空=随机，否则用指定牌山(136 tile IDs)
    const std::vector<int>& init_scores, // 空=25000×4，否则用指定初始分数
    int kyoutaku,                      // -1=默认0，或指定初始立直棒
    int honba,                         // -1=默认0，或指定初始本场
    int game_wind,                     // 0~3=东南西北，或默认East
    int oya                            // 0~3=指定庄家，或默认Player0
);
```

灵活初始化，支持固定牌山、初始分数等配置。

### `game_init_for_replay()`

```cpp
void game_init_for_replay(
    const std::vector<int>& yama,
    const std::vector<int>& init_scores,
    int kyoutaku,
    int honba,
    int game_wind,
    int oya
);
```

专门用于牌谱重放的初始化（与 `game_init_with_config()` 内部实现相同）。

### `import_yama()`

```cpp
void import_yama(const std::vector<int>& yama);
```

导入牌山（由 `export_yama()` 导出后重新导入，用于重放）。

### `export_yama()`

```cpp
string export_yama();
```

导出当前牌山为字符串（用于 debug 重放）。

## 摸牌方法

### `draw_tenhou_style()`

```cpp
void draw_tenhou_style();
```

按天凤风格发牌：每人轮流摸4张×3次+1张，生成13张初始手牌。

### `draw_normal(i_player)`

```cpp
void draw_normal(int i_player);
```

从牌山头部正常摸牌（正常游戏流程中使用）。

### `draw_rinshan(i_player)`

```cpp
void draw_rinshan(int i_player);
```

从岭上摸牌（杠之后使用，岭上牌是牌山中 `dora_indicator[0]` 之前的牌）。

## 游戏推进方法

### `make_selection(selection)`

```cpp
void make_selection(int selection);
```

核心推进函数：根据 `selection` 索引（由 `get_selection_from_action_tile()` 或 `get_selection_from_action_basetile()` 获取）执行动作并推进状态机。

**执行流程：**
1. `_check_selection()` — 验证 selection 合法性
2. `_handle_self_action()` — 处理自摸动作（舍牌/杠/和牌等）
3. `_generate_response_actions()` — 为响应阶段生成可用动作
4. 进入下一个 phase

### `get_selection_from_action_tile()`

```cpp
int get_selection_from_action_tile(
    BaseAction action_type,
    const std::vector<Tile*>& tiles
) const;
```

通过动作类型和具体 Tile 指针获取 selection 索引。

### `get_selection_from_action_basetile()`

```cpp
int get_selection_from_action_basetile(
    BaseAction action_type,
    const std::vector<BaseTile>& tiles,
    bool use_red_dora
) const;
```

通过动作类型和 BaseTile 列表获取 selection 索引。`use_red_dora=true` 时考虑赤宝牌。

### `make_selection_from_action_tile()`

```cpp
void make_selection_from_action_tile(
    BaseAction action,
    const std::vector<Tile*>& tiles
);
```

一步到位：`get_selection_from_action_tile()` + `make_selection()`。

### `make_selection_from_action_basetile()`

```cpp
void make_selection_from_action_basetile(
    BaseAction action,
    const std::vector<BaseTile>& tiles,
    bool use_red_dora
);
```

一步到位：`get_selection_from_action_basetile()` + `make_selection()`。

## 查询方法

### `from_beginning()`

```cpp
void from_beginning();
```

每轮开始时调用：
1. 检测流局条件（4风/4立/4杠/无牌）
2. 根据 `last_action` 决定摸牌方式
3. 生成自摸阶段可用动作
4. 设置当前 phase

### `_generate_self_actions()`

```cpp
std::vector<SelfAction> _generate_self_actions();
```

生成当前玩家的自摸动作列表（Discard/Riichi/Tsumo/AnKan/KaKan/Kyushukyuhai）。

### `_generate_response_actions()`

```cpp
std::vector<ResponseAction> _generate_response_actions(
    int player,
    Tile* tile,
    bool
);
```

生成某玩家对某舍牌的响应动作列表（Ron/Pon/Kan/Chi/Pass）。

### `get_self_actions()`

```cpp
inline std::vector<SelfAction> get_self_actions() const;
```

返回当前自摸阶段可用动作（便捷包装）。

### `get_response_actions()`

```cpp
inline std::vector<ResponseAction> get_response_actions() const;
```

返回当前响应阶段可用动作（便捷包装）。

## 辅助查询

### `get_phase()`

```cpp
inline int get_phase() const;
```

返回当前阶段编号（0-16）。

### `who_make_selection()`

```cpp
inline int who_make_selection() const;
// 等价于: (get_phase() - P1_ACTION) % 4
```

返回需要行动的玩家 ID。

### `is_self_acting()`

```cpp
inline bool is_self_acting() const;
// 等价于: get_phase() <= P4_ACTION
```

当前是否为自摸阶段。

### `is_over()`

```cpp
inline bool is_over() const;
// 等价于: get_phase() == GAME_OVER
```

游戏是否已结束。

### `get_result()`

```cpp
inline Result get_result() const;
```

返回游戏结果（含得分/和牌者/流局类型等）。

### `get_dora()`

```cpp
std::vector<BaseTile> get_dora() const;
```

返回所有已翻开的宝牌（BaseTile 列表）。

### `get_ura_dora()`

```cpp
std::vector<BaseTile> get_ura_dora() const;
```

返回所有里宝牌（仅在立直后有效）。

### `get_scores()`

```cpp
std::array<int, 4> get_scores();
```

返回4名玩家的当前分数。

### `get_selected_action()`

```cpp
inline SelfAction get_selected_action() const;
```

返回自摸阶段选中的动作（用于 Ron 检测）。

### `get_selected_action_tile()`

```cpp
inline Tile* get_selected_action_tile();
```

返回自摸动作对应的牌（用于 Ron 检测）。

## Debug 模式

### `set_debug_mode(mode)`

```cpp
inline void set_debug_mode(int debug_mode)
// debug_close = 0: 无debug
// debug_buffer = 1: 输出到buffer
// debug_stdout = 2: 输出到stdout
```

### `set_seed(seed)`

```cpp
inline void set_seed(int new_seed);
```

设置随机种子（须在 `game_init()` 之前调用）。

### `get_debug_replay()`

```cpp
inline std::string get_debug_replay();
```

返回 debug 重放代码（包含 `game_init_for_replay()` 和所有 `make_selection()` 调用）。

### `print_debug_replay()`

```cpp
inline void print_debug_replay();
```

打印 debug 重放代码到 stdout。

## 参考

- `Mahjong/Table.h` - 完整声明
- `Mahjong/Table.cpp` - 完整实现
- `docs/advanced/state_machine.md` - 状态机完整描述

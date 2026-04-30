# Player 类参考

`Player` 类管理单个玩家的所有状态：手牌、河、鸣牌、得分和游戏状态标志。

## 头文件

```cpp
#include "Player.h"
```

## 成员变量

### 手牌与鸣牌

| 成员 | 类型 | 说明 |
|------|------|------|
| `hand` | `vector<Tile*>` | 当前手牌（14张或17张） |
| `call_groups` | `vector<CallGroup>` | 已鸣牌组（吃/碰/大明杠） |
| `river` | `River` | 舍牌河 |

### 得分与风向

| 成员 | 类型 | 说明 |
|------|------|------|
| `score` | `int` | 当前点数（初始25000） |
| `wind` | `Wind` | 自风（East/South/West/North） |
| `oya` | `bool` | 是否为庄家 |

### 状态标志

| 成员 | 类型 | 说明 |
|------|------|------|
| `riichi` | `bool` | 是否已宣言立直 |
| `double_riichi` | `bool` | 是否双立直 |
| `menzen` | `bool` | 是否门清（无鸣牌） |
| `ippatsu` | `bool` | 是否一发自摸 |
| `first_round` | `bool` | 是否第一巡 |
| `furiten_round` | `bool` | 振听（舍牌振听）：某家和牌后自己打出的牌 |
| `furiten_river` | `bool` | 振听（河底振听）：自己舍牌后对手打出的牌 |
| `furiten_riichi` | `bool` | 振听（立直振听）：立直后舍出的牌 |

### 听牌

| 成员 | 类型 | 说明 |
|------|------|------|
| `atari_tiles` | `vector<BaseTile>` | 听牌列表 |

## 自摸动作（Self-Actions）

以下方法由 `Table._generate_self_actions()` 调用，返回可在 Pn_ACTION 阶段执行的动作。

### `get_discard(after_chipon)`

```cpp
std::vector<SelfAction> get_discard(bool after_chipon) const;
```

生成所有合法舍牌动作。`after_chipon=true` 时排除违反食断（Kuikae）的牌。

**违反食断的牌**：
- 吃上家 `Chi` 后，不能打出刚吃的顺子中的第2张（吃隔壁筋牌）
- 例如：上家打 3m，吃了 123m，不能打 2m（否则下次上家吃 23m 可和 1m）

### `get_riichi()`

```cpp
std::vector<SelfAction> get_riichi() const;
```

生成所有可宣言立直的舍牌（仅门清时可宣言）。

**立直条件**：
1. 门清（`menzen == true`）
2. 未宣言立直（`riichi == false`）
3. 处于听牌状态（`is_tenpai() == true`）
4. 有1000点以上点数

### `get_tsumo(table)`

```cpp
std::vector<SelfAction> get_tsumo(const Table* table) const;
```

检测自摸和牌。返回和牌动作（若有）。

### `get_kyushukyuhai()`

```cpp
std::vector<SelfAction> get_kyushukyuhai() const;
```

检测九种九牌（手牌有≥9种幺九牌时可用，宣告流局）。

**幺九牌**：1/9万、1/9筒、1/9索、东/南/西/北、白、发、中（共19种）

### `get_ankan()`

```cpp
std::vector<SelfAction> get_ankan() const;
```

生成所有可暗杠的组合（手牌中有4张相同的牌）。

### `get_kakan()`

```cpp
std::vector<SelfAction> get_kakan() const;
```

生成所有可加杠的组合（碰牌后，手牌中有第4张相同的牌）。

## 响应动作（Response-Actions）

以下方法由 `Table._generate_response_actions()` 调用。

### `get_ron(table, tile)`

```cpp
std::vector<ResponseAction> get_ron(Table* table, Tile* tile);
```

检测荣和。若手牌+此牌可和牌，返回 Ron 动作。

**振听检测**：若 `furiten_* == true`，不能和。

### `get_chi(tile)`

```cpp
std::vector<ResponseAction> get_chi(Tile* tile);
```

生成所有可吃的顺子（仅限上家打出的牌）。

**约束**：
- 必须门清才能吃（食断 rule）
- 赤宝牌5不能被吃

### `get_pon(tile)`

```cpp
std::vector<ResponseAction> get_pon(Tile* tile);
```

生成所有可碰的刻子（手中有该牌2张以上）。

### `get_kan(tile)`

```cpp
std::vector<ResponseAction> get_kan(Tile* tile);
```

生成所有可大明杠的刻子（手中有该牌3张以上）。

### `get_chankan(tile)`

```cpp
std::vector<ResponseAction> get_chankan(Tile* tile);
```

检测抢加杠（他人加杠时可抢）。

### `get_chanankan(tile)`

```cpp
std::vector<ResponseAction> get_chanankan(Tile* tile);
```

检测抢暗杠（他人暗杠时可抢）。

## 状态查询

### `is_riichi()`

```cpp
bool is_riichi() const;
```

是否已立直。

### `is_furiten()`

```cpp
bool is_furiten() const;
// 等价于: furiten_round || furiten_river || furiten_riichi
```

是否处于任何振听状态。

### `is_menzen()`

```cpp
bool is_menzen();
```

是否门清（遍历 `call_groups.empty()`）。

### `is_tenpai()`

```cpp
bool is_tenpai();
```

是否听牌（`atari_tiles` 非空）。

## 动作执行

### `execute_naki(tiles, tile, relative_position)`

```cpp
void execute_naki(
    std::vector<Tile*> tiles,
    Tile* tile,
    int relative_position
);
```

执行鸣牌（Chi/Pon/Kan）：
- `tiles`：用于鸣牌的牌（3或4张）
- `tile`：被鸣的牌（对手舍牌）
- `relative_position`：鸣牌中各张牌的位置（0/1/2），用于显示

### `execute_ankan(tile)`

```cpp
void execute_ankan(BaseTile tile);
```

执行暗杠：从手牌移除4张，添加为 AnKan 鸣牌组。

### `execute_kakan(tile)`

```cpp
void execute_kakan(Tile* tile);
```

执行加杠：将已有的 Pon 转为 DaiMinKan。

### `execute_discard(tile, number, on_riichi, fromhand)`

```cpp
void execute_discard(
    Tile* tile,
    int& number,
    bool on_riichi,
    bool fromhand
);
```

执行舍牌：
- `number`：河中第几枚
- `on_riichi`：是否为立直后的舍牌
- `fromhand`：是否为手切（从手牌打出，而非摸切）

### `remove_from_hand(tile)`

```cpp
void remove_from_hand(Tile* tile);
```

从手牌移除一张牌。

### `sort_hand()`

```cpp
void sort_hand();
```

将手牌按 BaseTile 排序（万→筒→索→字，数字升序）。

## 听牌计算

### `update_atari_tiles()`

```cpp
void update_atari_tiles();
```

重新计算听牌列表（调用 `Rule.get_atari_hai()`）。

### `update_furiten_river()`

```cpp
void update_furiten_river();
```

更新河底振听（对手河中有可和牌时设置）。

### `get_false_atari_hai()`

```cpp
std::vector<BaseTile> get_false_atari_hai() const;
```

获取虚假听牌（手牌有4张以上的牌，不能作为有效和牌张）。

## River 类（舍牌河）

```cpp
class River {
    std::vector<RiverTile> river;
    int size;
};
```

### RiverTile

```cpp
struct RiverTile {
    Tile* tile;       // 舍出的牌
    int number;       // 第几枚
    bool riichi;      // 是否为立直后舍牌
    bool remain;      // 是否仍可荣和（非振听时为true）
    bool fromhand;    // 是否为手切
};
```

## 参考

- `Mahjong/Player.h` - 完整声明
- `Mahjong/Player.cpp` - 完整实现

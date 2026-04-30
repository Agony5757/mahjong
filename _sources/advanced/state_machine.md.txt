# C++ 游戏引擎状态机

本文档详细描述了 Mahjong C++ 引擎的完整状态机实现。理解状态机是正确使用引擎、与前端对接、以及扩展功能的基础。

## 概述

引擎使用**阶段制（Phase-based）状态机**，每次 `make_selection()` 调用推进一个阶段。所有游戏状态集中在 `Table` 类中，通过 `PhaseEnum` 追踪当前所处的阶段。

## PhaseEnum 完整列表

```cpp
enum PhaseEnum {
    P1_ACTION = 0,   // 玩家0自摸阶段
    P2_ACTION = 1,   // 玩家1自摸阶段
    P3_ACTION = 2,   // 玩家2自摸阶段
    P4_ACTION = 3,   // 玩家3自摸阶段
    P1_RESPONSE = 4,  // 玩家0响应阶段
    P2_RESPONSE = 5,  // 玩家1响应阶段
    P3_RESPONSE = 6,  // 玩家3响应阶段
    P4_RESPONSE = 7,  // 玩家3响应阶段
    P1_CHANKAN_RESPONSE = 8,   // 玩家0抢杠响应阶段
    P2_CHANKAN_RESPONSE = 9,   // 玩家1抢杠响应阶段
    P3_CHANKAN_RESPONSE = 10,  // 玩家2抢杠响应阶段
    P4_CHANKAN_RESPONSE = 11,  // 玩家3抢杠响应阶段
    P1_CHANANKAN_RESPONSE = 12, // 玩家0抢暗杠响应阶段
    P2_CHANANKAN_RESPONSE = 13, // 玩家1抢暗杠响应阶段
    P3_CHANANKAN_RESPONSE = 14, // 玩家2抢暗杠响应阶段
    P4_CHANANKAN_RESPONSE = 15, // 玩家3抢暗杠响应阶段
    GAME_OVER = 16,     // 游戏结束
    UNINITIALIZED = 17 // 未初始化
};
```

**关键辅助函数**（均定义于 `Table.h`）：

| 函数 | 说明 |
|------|------|
| `who_make_selection()` | 返回当前需要行动的玩家 ID：`phase % 4` |
| `is_self_acting()` | `phase <= P4_ACTION` 时为自摸阶段 |
| `is_over()` | `phase == GAME_OVER` 时游戏结束 |

## 完整状态转移图

```
┌────────────────┐
│ UNINITIALIZED  │
└───────┬────────┘
        │ game_init() / game_init_with_config()
        ▼
┌─────────────────────────────────────┐
│ from_beginning()                    │
│  ├─ 流局检测（4风/4立/4杠/无牌）     │
│  ├─ 摸牌 (draw_normal / draw_rinshan)│
│  └─ _generate_self_actions()         │
└───────┬─────────────────────────────┘
        │ set phase = Pn_ACTION
        ▼
┌─────────────────────────────────┐
│  Pn_ACTION (自摸阶段)           │◄──────────────┐
│  turn = n                       │               │
│                                 │               │
│  get_kyushukyuhai()  ──────────────────────────►流局(9种9牌) → GAME_OVER
│  get_tsumo()        ──────────────────────────►和牌(tsumo) → GAME_OVER
│  get_discard()      ──► P1_RESPONSE            │
│  get_riichi()       ──► 摸牌 → get_riichi() ──► P1_RESPONSE
│  get_ankan()        ──► P1_CHANANKAN_RESPONSE  │
│  get_kakan()        ──► P1_CHANKAN_RESPONSE    │
└──────┬──────────────────────────┘               │
       │ make_selection()                         │
       ▼                                          │
┌─────────────────────────────────────────────────────┐
│ P1_RESPONSE ─► P2_RESPONSE ─► P3_RESPONSE ─► P4_RESPONSE │
│ 玩家1      玩家2       玩家3       玩家4                 │
│                                                        │
│  优先级: Ron > Pon/Kan > Chi > Pass                   │
│                                                        │
│  Ron    ──► generate_result_ron() ──────────────► GAME_OVER
│  Pon/Kan/Chi ──► execute_naki() ──► from_beginning()
│  Pass(所有人) ──► _handle_response_final_pass_impl()      │
│                  ──► next_turn() ──► from_beginning()─────┘
└─────────────────────────────────────────────────────┘

P1_CHANKAN_RESPONSE ─► P2_CHANKAN ─► P3_CHANKAN ─► P4_CHANKAN
  (抢加杠)
  ChanKan ──► generate_result_chankan() ──► GAME_OVER
  Pass(所有人) ──► _handle_response_final_chankan_execution()
                      ──► from_beginning()

P1_CHANANKAN_RESPONSE ─► P2 ─► P3 ─► P4
  (抢暗杠)
  ChanAnKan ──► generate_result_chanankan() ──► GAME_OVER
  Pass(所有人) ──► _handle_response_final_chanankan_execution()
                       ──► from_beginning()
```

## 阶段详解

### Pn_ACTION（自摸阶段）

玩家 `n`（`n = turn`）可执行的动作为 `_generate_self_actions()` 返回的列表：

| 动作类型 | 方法 | 结果 |
|---------|------|------|
| **Kyushukyuhai** | `get_kyushukyuhai()` | 流局，9种9牌，`generate_result_9hai()` |
| **Tsumo** | `get_tsumo()` | 自摸和牌，`generate_result_tsumo()` |
| **Discard** | `get_discard()` | 舍牌，进入 P1_RESPONSE |
| **Riichi** | `get_riichi()` | 宣言立直，后续须再次舍牌，进入 P1_RESPONSE |
| **AnKan** | `get_ankan()` | 暗杠，进入 P1_CHANANKAN_RESPONSE |
| **KaKan** | `get_kakan()` | 加杠，进入 P1_CHANKAN_RESPONSE |

#### 立直的两步流程

立直是一个两阶段操作：

1. **第一步**：玩家选牌 → `make_selection(Riichi_discard_index)`（action_type=Discard, 但 `selected_action.action = BaseAction::Riichi`）。引擎进入下一个 Pn_ACTION，**尚未实际舍牌**。
2. **第二步**：前端显示"确认立直"弹窗，玩家再次选同一张牌 → `make_selection(discard_index)` 正式舍牌并宣告立直。

前端必须正确处理此两步流程（详见 `pymahjong/env_pymahjong.py` 中的 `step()` 函数对立直的特殊处理）。

### Pn_RESPONSE（响应阶段）

针对当前 `turn` 玩家舍出的牌，其他玩家按顺序响应。`actions[4]` 数组记录各玩家的选择，优先级如下：

```
Ron > Pon > Kan > Chi > Pass
```

具体规则：
- **Chi**：仅当 `player == (turn + 1) % 4` 时可用（只能吃上家）
- **Pon**：手中有该牌2张以上时可执行
- **Kan**：手中有该牌3张以上时可执行（大手替打）
- **Ron**：任何玩家在和牌型时可执行

#### `_handle_response_final_execution()` 逻辑

所有4个玩家响应完成后，按以下优先级确认最终动作：

1. **存在 Ron**：`generate_result_ron()` → `GAME_OVER`
2. **存在 Pon/Kan/Chi**：执行鸣牌（调用 `execute_naki()`），`from_beginning()` 重新开始
3. **全部 Pass**：`next_turn()` → `from_beginning()` 继续下一巡

### Chankan / ChanAnKan（抢杠）

**加杠（KaKan）**后，触发 `P1_CHANKAN_RESPONSE`：
- 其他玩家可以**抢杠**（`ChanKan`）
- 被抢则 `generate_result_chankan()` → `GAME_OVER`

**暗杠（AnKan）**后，触发 `P1_CHANANKAN_RESPONSE`：
- 其他玩家可以**抢暗杠**（`ChanAnKan`）
- 被抢则 `generate_result_chanankan()` → `GAME_OVER`

## 流局（Ryukyoku）检测

在每局开始时（`from_beginning()`），引擎检查以下流局条件：

| 条件 | 检测方式 | 结果类型 |
|------|---------|---------|
| **四风连打** | 第1巡，4家首张舍牌均为同一风牌，无鸣牌 | `Ryukyouku_Interval_4Wind` |
| **四立直** | `player.riichi == true` 且4家全部宣布立直 | `Ryukyouku_Interval_4Riichi` |
| **四杠子** | `get_remain_kan_tile() == 0` 且2+家有杠 | `Ryukyouku_Interval_4Kan` |
| **九种九牌** | 玩家手牌有9种以上幺九牌（kyushukyuhai） | `Ryukyouku_9Hai` |
| **无牌** | `get_remain_tile() == 0`（yama剩余≤14张） | `generate_result_notile()` |

### `get_remain_kan_tile()` 实现

```cpp
inline int get_remain_kan_tile() const {
    // 找到 dora_indicator[0] 在 yama 中的位置
    // 该位置之前的所有牌（不含 dora_indicator 本身）= 岭上牌
    return int(std::find(yama.begin(), yama.end(), dora_indicator[0]) - yama.begin() - 1);
}
```

### `get_remain_tile()` 实现

```cpp
inline int get_remain_tile() const {
    // yama.size() - 14 = 剩余可摸牌数
    // 当剩余≤14时游戏结束（最后14张为王牌）
    return int(yama.size() - 14);
}
```

## 关键状态变量

| 变量 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `turn` | `int` | Table | 当前行动玩家 ID (0-3) |
| `oya` | `int` | Table | 庄家玩家 ID（每局固定，连庄时不变） |
| `honba` | `int` | Table | 本场数，每非庄和牌/流局+1 |
| `kyoutaku` | `int` | Table | 立直棒累计金额（1000点/棒） |
| `last_action` | `BaseAction` | Table | 上一个动作（决定是否摸牌） |
| `selected_action` | `SelfAction` | Table | 自摸阶段选中的动作（Ron检测用） |
| `phase` | `PhaseEnum` | Table | 当前阶段 |
| `self_actions` | `vector<SelfAction>` | Table | 当前自摸阶段可用动作列表 |
| `response_actions` | `vector<ResponseAction>` | Table | 当前响应阶段可用动作列表 |
| `actions` | `vector<ResponseAction>` | Table | 4名玩家的响应选择 |
| `hand` | `vector<Tile*>` | Player | 玩家手牌 |
| `call_groups` | `vector<CallGroup>` | Player | 鸣牌组（吃/碰/杠） |
| `riichi` | `bool` | Player | 是否已宣言立直 |
| `double_riichi` | `bool` | Player | 是否双立直 |
| `menzen` | `bool` | Player | 是否门清（无鸣牌） |
| `furiten_*` | `bool` | Player | 三种振听状态 |
| `atari_tiles` | `vector<BaseTile>` | Player | 当前听牌列表 |
| `score` | `int` | Player | 当前得分（点） |

## BaseAction 枚举

```cpp
enum class BaseAction : uint8_t {
    Pass,        // 跳过
    Chi,         // 吃（仅上家）
    Pon,         // 碰
    Kan,         // 大明杠
    Ron,         // 荣和
    ChanAnKan,   // 抢暗杠
    ChanKan,     // 抢加杠
    AnKan,       // 暗杠
    KaKan,       // 加杠
    Discard,     // 舍牌
    Riichi,      // 立直宣言
    Tsumo,       // 自摸
    Kyushukyuhai // 九种九牌
};
```

## 动作索引（Python API）

在 Python 绑定中，所有动作被编码为 0-53 的整数索引：

| 索引范围 | 动作 |
|---------|------|
| 0-33 | 34种标准牌的舍牌 |
| 34-36 | 赤5万/筒/索的舍牌 |
| 37-39 | 吃左/中/右（标准） |
| 40-42 | 吃左/中/右（赤宝牌） |
| 43 | 碰（标准） |
| 44 | 碰（赤宝牌） |
| 45 | 暗杠 |
| 46 | 大明杠 |
| 47 | 加杠 |
| 48 | 立直 |
| 49 | 荣和 |
| 50 | 自摸 |
| 51 | 自动通过（推进对手回合） |
| 52 | 确认立直（第二步） |
| 53 | 跳过响应 |

## 摸牌规则（`last_action` 决定）

```cpp
inline bool after_chipon()     { return last_action == BaseAction::Chi || last_action == BaseAction::Pon; }
inline bool after_daiminkan()  { return last_action == BaseAction::Kan; }
inline bool after_ankan()      { return last_action == BaseAction::AnKan; }
inline bool after_kakan()      { return last_action == BaseAction::KaKan; }
inline bool after_kan()        { return after_daiminkan() || after_ankan(); }
```

| 上一个动作 | 本巡是否摸牌 | 说明 |
|-----------|------------|------|
| Discard / Riichi | **是**（`draw_normal()`） | 正常摸牌 |
| Chi / Pon | **否**（不摸牌） | 吃碰后不补牌，直接由鸣牌者继续 |
| Kan / AnKan / KaKan | **是**（`draw_rinshan()`） | 杠后从岭上补牌 |

## `from_beginning()` 完整流程

```cpp
void Table::from_beginning() {
    // 1. 检查流局条件
    if (is_4wind_ryukyoku()) { result = generate_result_4wind(); phase = GAME_OVER; return; }
    if (is_4riichi())         { result = generate_result_4riichi(); phase = GAME_OVER; return; }
    if (is_4kan())            { result = generate_result_4kan(); phase = GAME_OVER; return; }
    if (get_remain_tile() == 0) { result = generate_result_notile(); phase = GAME_OVER; return; }

    // 2. 补牌
    if (after_chipon()) {
        // 吃碰后不补牌，轮转到鸣牌者
    } else if (after_kan()) {
        draw_rinshan(turn);   // 岭上摸牌
    } else {
        draw_normal(turn);    // 正常从牌山摸牌
    }

    // 3. 生成自摸动作
    self_actions = _generate_self_actions();
    phase = PhaseEnum(turn); // P1_ACTION ~ P4_ACTION
}
```

## 鸣牌后轮转规则

当 Pon/Kan/Chi 发生时，轮到鸣牌者（而非被鸣牌者）继续：

```cpp
void Table::_handle_response_final_chiponkan_impl(int response_player) {
    // 鸣牌后轮到鸣牌者（response_player）继续
    // turn 更新为 response_player
    last_action = ...; // Chi/Pon/Kan
    from_beginning();
}
```

## 与前端对接注意事项

1. **阶段轮询**：前端通过 `GET /api/game/{id}/state` 轮询，`phase` 字段指示当前状态
2. **立直两步**：前端必须在 `selected_action.action == Riichi` 时显示确认弹窗
3. **响应阶段**：前端通过 `response_actions` 列表渲染按钮（Chi/Pon/Ron/Pass）
4. **SSE 推送**：AI 动作完成后通过 SSE 推送，前端无需高频轮询
5. **牌谱记录**：每个 `make_selection()` 调用的索引都应记录，用于重放

## 参考文件

- `Mahjong/Table.h` - `PhaseEnum` 定义及核心状态
- `Mahjong/Table.cpp` - 状态转移实现（`_handle_self_action()`、`_handle_response_final_execution()` 等）
- `Mahjong/Player.h/cpp` - `get_*()` 系列方法实现
- `Mahjong/GameResult.h/cpp` - 流局和结算结果生成

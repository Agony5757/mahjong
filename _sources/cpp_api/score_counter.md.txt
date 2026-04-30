# ScoreCounter 类参考

`ScoreCounter` 负责役种检测、符数计算和最终得分。

## 头文件

```cpp
#include "ScoreCounter.h"
```

## 构造函数

```cpp
ScoreCounter(
    const Table* t,        // 游戏桌指针
    const Player* p,      // 和牌玩家指针
    Tile* win,             // 和牌张（荣和时为荣和牌，自摸时为nullptr）
    bool chankan,          // 是否抢杠和
    bool chanankan         // 是否抢暗杠和
);
```

## 成员变量

### 基础数据

| 成员 | 类型 | 说明 |
|------|------|------|
| `tiles` | `vector<Tile*>` | 所有和牌相关牌 |
| `win_tile` | `Tile*` | 和牌张 |
| `basetiles` | `vector<BaseTile>` | 牌种列表 |
| `completedtiles_list` | `vector<vector<CompletedTiles>>` | 所有可能的手牌拆分 |
| `table` | `const Table*` | 游戏桌指针 |
| `player` | `const Player*` | 和牌玩家指针 |

### 检测结果

| 成员 | 类型 | 说明 |
|------|------|------|
| `tenhou_chihou_yakus` | `vector<Yaku>` | 天地和役 |
| `state_yakus` | `vector<Yaku>` | 状态役（立直/一发等） |
| `dora_yakus` | `vector<Yaku>` | 宝牌役 |
| `max_hand_yakus_fan_fu` | `pair<vector<Yaku>, int>` | 最大番数/符数组合 |
| `have_yaku` | `bool` | 是否有役 |
| `yakuman` | `bool` | 是否役满 |
| `yakuman_fold` | `int` | 几倍役满 |
| `mpsz_pure_type` | `int` | 清一色/字一色类型 (0-3=suit, 4=honor) |
| `menzen` | `bool` | 是否门清 |
| `tsumo` | `bool` | 是否自摸 |
| `kokushi` / `kokushi_13` | `bool` | 国士/国士13面 |
| `churen` / `churen_pure` | `bool` | 九莲/纯正九莲 |

## 役种检测方法

### `yaku_counter()`

```cpp
CounterResult yaku_counter();
```

**主入口函数**，执行完整役种检测：

1. 手牌拆分 → `completedtiles_list`
2. 特殊手型检测（天地和→国士→九莲）
3. 对每种拆分，检测役满 → 检测普通役
4. 状态役检测（立直/一发/海底等）
5. 宝牌役检测
6. 选择最大番/符组合
7. 返回 `CounterResult`

### `get_tenhou_chihou()`

```cpp
bool get_tenhou_chihou();
```

检测天和（Tenhou）和地和（Chihou）。

**天和**：第一巡，庄家自摸，无鸣牌 → 役满
**地和**：第一巡，非庄家自摸，无鸣牌 → 半庄满

**条件**：
- `player->first_round == true`（第一巡）
- `player->call_groups.empty()`（无鸣牌）
- `player->oya == true`（天和）或 `false`（地和）

### `get_kokushi()`

```cpp
bool get_kokushi();
```

检测国士无双（Kokushi Musou）。

**形式**：
- 普通国士：13种幺九牌 + 任意一张幺九牌对子
- 十三面国士（`kokushi_13 = true`）：13种幺九牌各1张 + 听第14种，役满/双倍役满

### `get_churen()`

```cpp
bool get_churen();
```

检测九莲宝灯（Churen Poutou）。

**形式**：
- 普通九莲：1,1,1,2,3,4,5,6,7,8,9,9,9 + 任意一张同花色
- 九莲宝灯9面（`churen_pure = true`）：听第9张时，役满/双倍役满

### `get_pure_type()`

```cpp
void get_pure_type();
```

分析手牌，确定 `mpsz_pure_type`：
- 0, 1, 2, 3 = 万/筒/索/字
- 纯字一色：全为字牌（z）

### `get_hand_yakuman()`

```cpp
std::vector<Yaku> get_hand_yakuman(
    const std::vector<string>& tile_group_string,
    Wind self_wind,
    Wind game_wind,
    bool& yakuman
);
```

检测役满（非特殊手型）。支持的役满：

| Yaku | 名称 | 条件 |
|------|------|------|
| `Daisangen` | 大三元 | 白/发/中三个刻子 |
| `Siiankou` | 四暗刻 | 4个刻子（单骑=双倍役满） |
| `Siiankou_1` | 四暗刻单骑 | 四暗刻+单面听（双倍役满） |
| `Tsuiisou` | 字一色 | 全为字牌 |
| `Ryuiisou` | 绿一色 | 仅含绿牌(2,3,4,6,8s + 发) |
| `Chinroutou` | 清老头 | 仅含1/9数牌 |
| `Siikantsu` | 四杠子 | 4个杠子 |
| `Shousuushi` | 小四喜 | 3种风牌刻子 + 1种风牌对子 |
| `Daisuushi` | 大四喜 | 4种风牌全部刻子（双倍役满） |

### `get_hand_yakus()`

```cpp
std::pair<vector<Yaku>, int> get_hand_yakus(
    const vector<string>& tile_group_string,
    Wind self_wind,
    Wind game_wind,
    bool menzen
);
```

检测普通役（非役满）。返回 `{yaku列表, fu数}`。

**主要役种**：

| 番数 | 役种 | 检测条件 |
|------|------|---------|
| 1 | Tanyao 断幺九 | 无幺九牌 |
| 1 | Riichi 立直 | 已宣言立直 |
| 1 | Menzentsumo 门清自摸 | 门清+自摸 |
| 1 | Pinfu 平和 | 门清+顺子+非役牌对+边张/坎张 |
| 1 | Ippatsu 一发 | 立直后1巡内和牌 |
| 1 | Haiteiraoyue 海底摸月 | 最后一张自摸 |
| 1 | Houteiraoyu 河底捞鱼 | 最后一张荣和 |
| 1 | Rinshankaihou 岭上开花 | 杠后自摸 |
| 1 | Chankan 抢杠 | 抢他人加杠 |
| 1+ | Dora 宝牌 | 每张宝牌+1番 |
| 1+ | Akadora 赤宝牌 | 每张赤5+1番 |
| 1 | Uradora 里宝牌 | 立直后每张里宝牌+1番 |
| 2 | Dabururiichi 两立直 | 第1巡立直 |
| 2 | Sanshokudoukou 三色同刻 | 同数字m/p/s刻子 |
| 2 | Toitoiho 对对和 | 全刻子 |
| 2 | Sanankou 三暗刻 | 3个暗刻 |
| 2 | Shousangen 小三元 | 2个三元牌刻子+1对 |
| 2 | Honroutou 混老头 | 全1/9数牌+字牌 |
| 2 | Chiitoitsu 七对子 | 7个对子（固定25符） |
| 2 | Sankantsu 三杠子 | 3个杠子 |
| 3 | Sanshokudoujun 三色同顺 | 同形状m/p/s顺子 |
| 3 | Ikkitsuukan 一气通贯 | 1-4-7同花色顺子 |
| 3 | Ryanpeikou 二杯口 | 两个相同顺子（门清） |
| 3 | Junchantaiyaochu 纯全带幺九 | 全带幺九+门清 |
| 3 | Honchantaiyaochu 混全带幺九 | 全带幺九 |
| 3 | Honitsu 混一色 | 同花色+字牌（2番） |
| 5 | Chinitsu 清一色 | 全同花色（5番） |

### `get_riichi()` / `get_ippatsu()` / `get_haitei_hotei()` 等

```cpp
void get_riichi();
void get_ippatsu();
void get_haitei_hotei();
void get_chankan();
void get_rinshan();
void get_menzentsumo();
void get_aka_dora();
void get_dora();
void get_ura_dora();
```

分别检测对应的状态役和宝牌役。

## tile_group 字符串编码

手牌用字符串编码表示，用于役种检测：

```
格式: [数字][花色][类型][位置后缀]
```

| 类型字符 | 含义 |
|---------|------|
| `K` | 刻子（3张相同） |
| `S` | 顺子（3连续） |
| `:` | 对子 |
| `\|` | 杠子（4张相同） |

| 后缀字符 | 含义 |
|---------|------|
| `-` | 副露（鸣牌） |
| `+` | 暗杠 |
| `!` | 自摸第1张 |
| `@` | 自摸第2张 |
| `#` | 自摸第3张 |
| `$` | 荣和第1张 |
| `%` | 荣和第2张 |
| `^` | 荣和第3张 |

**示例**：
- `1mK-`：1万刻子（副露）
- `1mS!`：自摸123万顺子（和1万）
- `1z:+`：1字对子（暗杠）
- `5p|`：5筒杠子

## CounterResult 结构

```cpp
struct CounterResult {
    vector<Yaku> yakus;  // 役种列表
    int score1 = 0;       // 亲家支付（或荣和总支付）
    int score2 = 0;       // 子家支付（自摸时）
    int fan = 0;          // 总番数
    int fu = 0;           // 总符数
    void calculate_score(bool oya, bool tsumo);
};
```

### `calculate_score()`

```cpp
void calculate_score(bool oya, bool tsumo);
```

根据番/符数计算实际得分（查标准计分表）。

**得分表摘要**：

| 番数 | 符数 | 亲家自摸 | 子家自摸 | 荣和（亲） | 荣和（子） |
|------|------|---------|---------|-----------|-----------|
| 1 | 20 | 1500 | 500 | 2000 | 2000 |
| 1 | 30 | 2000 | 700 | 2900 | 2900 |
| 2 | 20 | 3900 | 1300 | 5200 | 3900 |
| 3 | 40 | 7700 | 2600 | 10600 | 7100 |
| 4 | 40 | 11600 | 3900 | 15400 | 11600 |
| 5 | — | **满贯 12000** | **8000** | **12000** | **8000** |
| 6-7 | — | **跳满 18000** | **12000** | **18000** | **12000** |
| 8-10 | — | **倍满 24000** | **16000** | **24000** | **16000** |
| 11-12 | — | **三倍满 36000** | **24000** | **36000** | **24000** |
| 13+ | — | **役满 48000** | **32000** | **48000** | **32000** |

**特殊**：
- 7对子固定25符
- 平和自摸固定20符（不计自摸符）
- 符数不满10的倍数时向上取整

## 计分器辅助函数

### `calculate_fan()`

```cpp
int calculate_fan(const vector<Yaku>& yakus);
```

计算役种列表的总番数（考虑倍役满/三倍役满/数倍役满）。

### `compare_yaku_fu()`

```cpp
bool compare_yaku_fu(
    const pair<vector<Yaku>, int>& lhs,
    const pair<vector<Yaku>, int>& rhs
);
```

比较两个 `{役列表, 符}` 对：先比番数，再比符数（用于选择最大手役）。

## 参考

- `Mahjong/ScoreCounter.h` - 完整声明
- `Mahjong/ScoreCounter.cpp` - 完整实现
- `docs/advanced/state_machine.md` - `generate_result_*` 系列函数的调用关系

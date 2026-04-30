# Tile、Action 与相关工具参考

## Tile.h - 牌表示

### BaseTile 枚举

34种基础牌型：

| 范围 | 花色 | BaseTile 值 |
|------|------|------------|
| 0-8 | 万子（Manzu, m） | 0=1m, 1=2m, ..., 8=9m |
| 9-17 | 筒子（Pinzu, p） | 9=1p, 10=2p, ..., 17=9p |
| 18-26 | 索子（Souzu, s） | 18=1s, 19=2s, ..., 26=9s |
| 27-33 | 字牌（Jihai, z） | 27=1z(东), 28=2z(南), 29=3z(西), 30=4z(北), 31=5z(白), 32=6z(发), 33=7z(中) |

### Tile 结构体

```cpp
struct Tile {
    BaseTile tile;   // 基础牌种
    bool red_dora;   // 是否为赤宝牌（仅5万/5筒/5索）
    int id;          // 唯一标识 0-135（Tenhou 编码）
};
```

**Tenhou ID 编码规则**：
```
id = basetile × 4 + (copy_index: 0-3)
```

例如：4个1万的 id 分别是 0, 1, 2, 3。

**赤宝牌 ID**：
- 5m 红：id = 4（第5×4=20号位置）
- 5p 红：id = 13
- 5s 红：id = 22

### 工具函数

#### `basetile_to_string(bt)`

```cpp
string basetile_to_string(BaseTile bt);
```

将 BaseTile 转为字符串：0→"1m", 27→"1z" 等。

#### `char2_to_basetile(s)`

```cpp
BaseTile char2_to_basetile(const string& s);
```

反向解析："5mr" → 赤5万。

#### `is_1hai(bt)` / `is_9hai(bt)` / `is_19hai(bt)`

```cpp
bool is_1hai(BaseTile bt);   // 是否1牌
bool is_9hai(BaseTile bt);   // 是否9牌
bool is_19hai(BaseTile bt);  // 是否1/9牌
```

#### `is_yaochuhai(bt)`

```cpp
bool is_yaochuhai(BaseTile bt);
// 等价于: is_19hai(bt) || is_tsuhai(bt)
```

是否幺九牌（1/9数牌 + 字牌）。

#### `is_tsuhai(bt)`

```cpp
bool is_tsuhai(BaseTile bt);
// 27 <= bt <= 33
```

是否为字牌。

#### `is_shuntsu(bt)`

```cpp
bool is_shuntsu(BaseTile bt);
// bt % 9 <= 6 (可组成顺子的起始牌)
```

是否可作为顺子起始牌（顺123需要1-7，数牌）。

#### `is_koutsu(bt)`

```cpp
bool is_koutsu(BaseTile bt);
// basetile_to_group(bt) == 3
```

是否可作为刻子（任意牌均可）。

#### `is_kantsu(bt)`

```cpp
bool is_kantsu(BaseTile bt);
// 同 is_koutsu
```

是否可作为杠子（同刻子，但实际需要4张）。

#### `is_yakuhai(bt, self_wind, game_wind)`

```cpp
bool is_yakuhai(BaseTile bt, Wind self_wind, Wind game_wind);
```

是否为目标役牌：
- 字牌（5z=白，6z=发，7z=中）永远为役牌
- 风牌当与自风或场风相同时为役牌

#### `get_dora_next(bt)`

```cpp
BaseTile get_dora_next(BaseTile bt);
```

获取下一个宝牌：`9m→1m`, `8p→9p`, `7z→1z`（循环）。

### CallGroup 结构体

表示鸣牌组：

```cpp
struct CallGroup {
    vector<Tile*> tiles;  // 鸣牌涉及的牌（3张）
    int take;             // 被鸣牌在组中的位置: 0/1/2
    Type type;            // Chi/Pon/DaiMinKan/KaKan/AnKan
};
```

**Type 枚举**：
- `Chi`：吃（上家舍牌 + 手牌2张）
- `Pon`：碰（对手舍牌 + 手牌2张）
- `DaiMinKan`：大明杠（对手舍牌 + 手牌3张）
- `KaKan`：加杠（碰牌 + 手牌1张）
- `AnKan`：暗杠（手牌4张）

**`take` 字段说明**：
- Chi 123（吃2）：`take=1`（被吃的是第2张）
- Pon 111（碰1）：`take=0,1,2` 均可（碰不区分位置）
- DaiMinKan 1111：`take=0,1,2,3`

## Action.h - 动作表示

### BaseAction 枚举

```cpp
enum class BaseAction : uint8_t {
    Pass,        // 0: 跳过
    Chi,         // 1: 吃
    Pon,         // 2: 碰
    Kan,         // 3: 大明杠
    Ron,         // 4: 荣和
    ChanAnKan,   // 5: 抢暗杠
    ChanKan,     // 6: 抢加杠
    AnKan,       // 7: 暗杠
    KaKan,       // 8: 加杠
    Discard,     // 9: 舍牌
    Riichi,      // 10: 立直宣言
    Tsumo,       // 11: 自摸
    Kyushukyuhai // 12: 九种九牌
};
```

### Action 结构体模板

```cpp
template<typename T>
struct Action {
    T action;                        // BaseAction
    std::vector<BaseTile> correspond_tiles;  // 相关牌列表
};
```

`SelfAction = Action<SelfAction>`，类似 `ResponseAction`。

### `get_action_index()`

```cpp
template<typename T>
int get_action_index(
    const std::vector<T>& actions,
    BaseAction action_type,
    const std::vector<BaseTile>& tiles
);
```

在动作列表中查找匹配 `action_type + tiles` 的动作索引。

## GameLog.h - 游戏日志

### LogAction 枚举

```cpp
enum class LogAction {
    AnKan,                     // 暗杠
    Pon,                       // 碰
    Chi,                       // 吃
    Kan,                       // 大明杠
    KaKan,                     // 加杠
    DiscardFromHand,           // 手切（从手牌舍出）
    DiscardFromTsumo,          // 摸切（摸牌后立即舍出）
    RiichiDiscardFromHand,     // 立直手切
    RiichiDiscardFromTsumo,    // 立直摸切
    RiichiSuccess,             // 立直成功（1巡后确认）
    DrawNormal,                // 正常摸牌
    DrawRinshan,              // 岭上摸牌
    DoraReveal,               // 翻开宝牌
    Kyushukyuhai,             // 九种九牌
    Ron,                      // 荣和
    Tsumo,                    // 自摸
    InvalidLogAction
};
```

### BaseGameLog 结构体

```cpp
struct BaseGameLog {
    int player, player2;       // 玩家ID（Ron时：player=赢家，player2=输家）
    LogAction action;
    Tile* tile;               // 相关牌
    std::vector<Tile*> call_tiles; // 鸣牌用牌
    int score[4];             // 本步后的各玩家分数
};
```

### GameLog 类

```cpp
class GameLog {
    int winner, loser;
    int start_scores[4], init_yama[136];
    Tile* init_hands[4][14];  // 4玩家×14初始手牌
    int start_honba, end_honba;
    int start_kyoutaku, end_kyoutaku;
    int oya, game_wind;
    Result result;
    std::vector<BaseGameLog> logs;
};
```

**关键方法**：
- `log_game_start()` - 初始化日志，记录初始状态
- `log_draw()` - 记录摸牌（`DrawNormal`/`DrawRinshan`）
- `log_discard()` - 记录舍牌（`DiscardFromHand`/`DiscardFromTsumo`）
- `log_riichi_discard()` - 记录立直舍牌
- `log_call()` - 记录鸣牌（Chi/Pon/Kan）
- `log_ankan()` / `log_kakan()` - 记录杠
- `log_ron()` / `log_tsumo()` - 记录和牌
- `log_gameover()` - 记录终局结果
- `to_string()` - 生成可读日志

## GameResult.h - 结算结果

### ResultType 枚举

```cpp
enum class ResultType {
    RonAgari,           // 荣和
    TsumoAgari,         // 自摸
    Ryukyouku_9Hai,     // 九种九牌
    Ryukyouku_4Wind,    // 四风连打
    Ryukyouku_4Riichi,  // 四立直
    Ryukyouku_4Kan,     // 四杠子
    Ryukyouku_Notile    // 无牌流局
};
```

### Result 结构体

```cpp
struct Result {
    ResultType result_type;
    int score[4];              // 各玩家最终得分
    std::vector<int> winner;    // 赢家列表（可多人荣和）
    int loser;                 // 输家（荣和时）
    int n_honba;               // 本场数（终局）
    bool renchan;              // 是否连庄
    CounterResult counter_result; // 和牌时的役种/得分详情
};
```

### 生成函数

| 函数 | 说明 |
|------|------|
| `generate_result_ron(table, tile, players)` | 荣和结算 |
| `generate_result_tsumo(table, tile, player)` | 自摸结算 |
| `generate_result_9hai(table)` | 九种九牌 |
| `generate_result_4wind(table)` | 四风连打 |
| `generate_result_4riichi(table)` | 四立直 |
| `generate_result_4kan(table)` | 四杠子 |
| `generate_result_notile(table)` | 无牌流局（十有害/南入/西入/北入处理） |
| `generate_result_3ron(table)` | 三家和（ triple ron） |
| `generate_result_chankan(table, tile, player)` | 抢杠和 |
| `generate_result_chanankan(table, tile, player)` | 抢暗杠和 |

## Yaku.h - 役种枚举

完整的 Yaku 枚举包含100+种值，分为：

**固定番数**：
- 1番：Riichi, Tanyao, Menzentsumo, Pinfu, Ippatsu, Haiteiraoyue, Houteiraoyu, Rinshankaihou, Chankan, Dora, Uradora, Akadora, Peidora, Jikaze, Bakaze, Yakuhai, Ippeikou
- 2番：Dabururiichi, Sanshokudoukou, Toitoiho, Sanankou, Shousangen, Honroutou, Chiitoitsu, Ikkitsuukan, Sankantsu, Sanshokudoujun
- 3番：Ryanpeikou, Junchantaiyaochu, Honitsu
- 5+番：Chinitsu

**役满**：
- Tenhou, Chihou, Daisangen, Siiankou, Siiankou_1, Tsuiisou, Ryuiisou, Chinroutou, Kokushimusou, Kokushimusou_13, Shousuushi, Siikantsu, Chuurenpoutou, Chuurenpoutou_9, Daisuushi

**特殊**：Yakuman_Double（双倍役满）

详见 `Mahjong/Yaku.h` 完整定义。

## 参考

- `Mahjong/Tile.h` - Tile 和 CallGroup 定义
- `Mahjong/Action.h` - BaseAction 和 Action 结构
- `Mahjong/Yaku.h` - Yaku 枚举完整列表
- `Mahjong/GameLog.h` - 日志系统
- `Mahjong/GameResult.h` - 结算系统

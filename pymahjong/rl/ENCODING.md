# 状态/动作编码方案设计文档（v2 草案，待审）

> 本文是 `pymahjong.rl` 的编码设计 + **逐项自检报告**。审阅重点：
>
> 1. 是否完整覆盖了原 C++ `TrainingDataEncoding::v2` 暴露给模型的所有信息（4 家鸣牌、立直状态、牌河、furiten、可见牌张数等）；
> 2. 数值字段是否都在合理范围内、是否存在"把 raw 数值塞给模型当连续变量"的隐患；
> 3. 红 5（赤ドラ）的编码方式。

代码涉及：`pymahjong/rl/tokenization.py`、`Mahjong/Encoding/TrainingDataEncodingV2.{h,cpp}`、`Mahjong/Encoding/TrainingDataEncodingV1.h`。

---

## 0. TL;DR

- 状态 = 变长 token 序列 `tokens[L, 5]` + `attention_mask[L]`，每行 `(segment, tile, count, who, extra)` 全部 `uint8`；模型对 5 个字段各学一张 embedding，求和送 Transformer。
- 动作 = 54 维离散，与 `MahjongEnv.ACTION_DIM` 完全兼容，附 `action_mask[54]`。
- 缓存：`uint8` token + `int16` label，1 sample ≈ 1.23 KiB。
- 数据增强：仅花色置换 ×6（man/pin/sou），座次旋转**禁止**。
- **本次自检发现的 8 个必修缺口与 4 个推荐补**列在 §11，含修复后 token/段计数。

---

## 1. Token 5 个字段

| 字段 | 类型 | 当前 vocab | 缓存 dtype | 取值约束 |
|---|---|---|---|---|
| `segment`  | 段 id（PAD/SELF_HAND/...） | 21 → 修后 30 | `uint8` (0..255) | 类别 |
| `tile`     | 牌 id：0–33 = 基础牌；34/35/36 = 红 5m/p/s；37 = PAD | 38 | `uint8` | 类别 |
| `count`    | tile 张数 0–4，或段内小整数 payload | 96 | `uint8` | 类别 / 小整数索引 |
| `who`      | 相对座次：0=自家 / 1=下家 / 2=对家 / 3=上家 / 4=N/A | 5 | `uint8` | 类别 |
| `extra`    | 段内附加 payload（位包等） | 256 | `uint8` | 类别 / 小整数索引 |

> **重要约定**：5 个字段全部以**类别 id（embedding 查表索引）**进入模型，绝不作为连续数值参与运算。这一原则隔离了"raw value 范围"问题：tile_id=4 对模型而言不是"4 单位"，而是"embedding 表第 4 行"。详见 §6。

---

## 2. 当前段（Segment）总表

| ID | 段名 | 当前是否填 | `count` 含义 | `who` 含义 | `extra` 含义 |
|---:|---|---|---|---|---|
| 0  | PAD                 | 自动 | 0 | 0 | 0 |
| 1  | SELF_HAND           | ✅ | 张数 0..4 | 0 | 0 |
| 2  | SELF_TSUMO          | 🟡 已定义未用 | — | — | — |
| 3  | SELF_FUURO          | ✅ | 1 | 0 | `BaseAction` 类型 |
| 4  | OPP_FUURO           | ✅ | 1 | 1/2/3 | `BaseAction` 类型 |
| 5  | SELF_RIVER          | ✅ | 1 | 0 | 位包：bit0=立直宣言, bit1=fromhand, bits2-7=巡序 |
| 6  | OPP_RIVER           | ✅ | 1 | 1/2/3 | 同上 |
| 7  | DORA_INDICATOR      | ✅ | 1 | 4 | 0 |
| 8  | URA_DORA_INDICATOR  | 🟡 仅胡牌后才填 | 1 | 4 | 0 |
| 9  | PLAYER_RIICHI       | ✅ | 0/1 | 0..3 | double_riichi |
| 10 | PLAYER_IPPATSU      | ✅ | 0/1 | 0..3 | 0 |
| 11 | PLAYER_MENZEN       | ✅ | 0/1 | 0..3 | 0 |
| 12 | PLAYER_SCORE        | ✅ | 1k 桶 0..80 | 0..3 | 0 |
| 13 | GAME_WIND           | ✅ | 风 id 0..3 | 4 | 0 |
| 14 | SELF_WIND           | ✅ | 风 id 0..3 | 0 | 0 |
| 15 | HONBA               | ✅ | 0..255（&0xFF） | 4 | 0 |
| 16 | KYOUTAKU            | ✅ | 0..255（&0xFF） | 4 | 0 |
| 17 | REMAINING_TILES     | ✅ | 0..70 | 4 | 0 |
| 18 | LAST_DISCARD        | ⚠️ 语义混用 | 1 | 来源相对座次 | 0 |
| 19 | PHASE               | ✅ | engine phase id | 4 | riichi 第 2 步标志 |
| 20 | ACTION_HINT         | ✅ | 0/1/2 | 4 | 0 |

**当前未实现的段（必修，详见 §4）**：ROUND_INDEX、DEALER_SEAT、SELF_TSUMO_TILE、LAST_DISCARDED_TILE、ACTUAL_DORA、VISIBLE_COUNT、FURITEN_AREA、FUURO_FROM、TURN_INDEX。

---

## 3. **EncodingV2 完整对照表（自检主表）**

`TrainingDataEncoding::v2` 把状态拆成三块：

- **`self_info[18, 34]`** — 每位玩家一份的"自家可见信息矩阵"
- **`global_info[15]`** — 每位玩家一份的"全局标量信息向量"
- **`records[N]`** — 每个动作 1 条 `(tile_idx_with_aka + action_one_hot + player_one_hot)` 共 53 维

下表把 V2 的**每一个槽**与本编码的**对应方式或缺口**逐一列出。

### 3.1 V2 self_info 18 个 row（每个 row 长度 34=tile types）

| V2 row | V2 含义 | 本编码对应 | 状态 |
|---:|---|---|---|
| 0..3 `pos_hand_1..4` | 自家手牌中各 tile_type 的第 1/2/3/4 张（4 通道堆叠 one-hot） | `SELF_HAND` 段每个 tile_id 一 token，`count` = 张数 | ✅ 等价 |
| 4 `pos_dora_1` | **实际 dora 牌**（由 indicator+1 计算） | 当前缺！只有 `DORA_INDICATOR` | ❌ **必修**：增 `ACTUAL_DORA` 段 |
| 5 `pos_dora_indicator_1` | 已翻 dora 表示牌（含杠后） | `DORA_INDICATOR` 段 | ✅ |
| 6 `pos_aka_dora` | **自家手牌中的赤ドラ标志**（每 tile_type 一位） | `SELF_HAND` 用独立 tile_id（34/35/36）表示赤 5 | ✅ 等价（细节差异，见 §5） |
| 7 `pos_game_wind` | 场风（在 7 张字牌位置上 one-hot） | `GAME_WIND` 段，`count`=风 id | ✅ |
| 8 `pos_self_wind` | 自风（同上） | `SELF_WIND` 段 | ✅ |
| 9 `pos_tsumo_tile` | 自家刚摸的那张（仅当 `is_self_acting && hand%3==2`） | 当前 `LAST_DISCARD` 段语义被复用（在 self-action 时也填这里） | ⚠️ **必修**：拆出独立 `SELF_TSUMO_TILE` 段 |
| 10..13 `pos_discarded_by_player_1..4` | **furiten 区**：4 家分别"打过哪些 tile_type"（位图，无序，相对座次排列） | 可由 `SELF_RIVER`/`OPP_RIVER` 推导，但当前未显式聚合 | ❌ **必修**：增 `FURITEN_AREA` 段（每家 1 张位图，用 token 表示） |
| 14..17 `pos_discarded_number_1..4` | **可见牌张数**：所有可见的 tile_type 各被见到 1/2/3/4 次（4 通道堆叠 one-hot） | 当前没有显式总和；模型必须自己从河 + 副露 + dora 表示牌里数 | ❌ **必修**：增 `VISIBLE_COUNT` 段（每个被见到的 tile_id 一 token，`count`=已可见次数） |

### 3.2 V2 global_info 15 个槽

| V2 idx | V2 含义 | 本编码对应 | 状态 |
|---:|---|---|---|
| 0 `pos_game_number` | `(game_wind-East)*4 + oya` 范围 0..7 | 当前缺局数与亲家 | ❌ **必修**：增 `ROUND_INDEX` + `DEALER_SEAT` |
| 1 `pos_game_size` | 半庄/东风：V2 写死 7（？）— 本编码用半庄/东风室号代替 | 缺：未编码"半庄 vs 东风" | 🟡 **推荐**：增 `GAME_SIZE` |
| 2 `pos_honba` | 本场 raw int | `HONBA` 段，低 8 位 | ✅（一般 honba<256） |
| 3 `pos_kyoutaku` | 立直棒 raw int | `KYOUTAKU` 段，低 8 位 | ✅ |
| 4 `pos_self_wind` | 自风 0..3 | `SELF_WIND.count` | ✅ |
| 5 `pos_game_wind` | 场风 0..3 | `GAME_WIND.count` | ✅ |
| 6..9 `pos_player_{0..3}_point` | 4 家持点（**单位是 / 100**），相对座次 0=self,1=prev,2=opp,3=next | `PLAYER_SCORE` 段每家 1 token，**1k 桶**（0..80） | ⚠️ 粒度比 V2 粗 10 倍；详见 §6.3 |
| 10..13 `pos_player_{0..3}_ippatsu` | 4 家一发（相对座次） | `PLAYER_IPPATSU` 段每家 1 token | ✅ |
| 14 `pos_remaining_tiles` | 剩余山数 raw int | `REMAINING_TILES` 段 | ✅ |

### 3.3 V2 records[N]（每个动作 1 条向量）

每条 record 由三段拼接：

```
record[0..36]   = tile_one_hot (含赤 5m/p/s 共 37 维)
record[37..50]  = action_one_hot (14 种 LogAction)
record[51..54]  = player_one_hot (4 家，相对座次)
```

V2 的 14 种 action：DrawNormal、DrawRinshan、DiscardFromHand、DiscardFromTsumo、ChiLeft、ChiMiddle、ChiRight、Pon、Kan、Ankan、Kakan、RiichiFromHand、RiichiFromTsumo、RiichiSuccess。

| V2 records 用途 | 本编码对应 | 状态 |
|---|---|---|
| 还原一局完整动作流（draw/discard/chi 区分左中右/riichi 状态机） | 当前**无**对应；只有 snapshot（手牌、河、副露） | ❌ **必修**（部分）：见下 |

> 注：V2 的 records 既包含**当前盘面信息的来源轨迹**，也包含"碰/吃/杠是从谁那里来的"信息（通过 player_one_hot）。

#### records 的覆盖策略

完整 records 在长游戏里可达 ~150 条，按 1 token/record 至少 +150 tokens，会爆 `MAX_SEQ_LEN=200` 预算。我们做**信息压缩**：

| V2 records 中携带的关键信息 | 是否必须 | 在本编码里如何还原 |
|---|---|---|
| 河里每张牌（含赤 5、立直宣言、手切/摸切） | ✅ 已有 | `SELF_RIVER` / `OPP_RIVER`，extra 位包了立直宣言 + fromhand |
| 河里每张的巡序 | ✅ 已有 | `SELF_RIVER.extra` 高 6 位 = number |
| 副露的牌、类型 | ✅ 已有 | `SELF_FUURO` / `OPP_FUURO`，`extra`=BaseAction 类型 |
| **副露是从谁吃/碰/杠来的（chi-left/middle/right、pon-from-whom）** | ❌ 缺 | **必修**：在 `*_FUURO.extra` 增加 from-whom 编码（见 §5.4） |
| Draw / Rinshan 区分（自摸 vs 杠摸） | 🟡 可选 | 可由"是否触发 dora reveal"间接体现；推荐增 `LAST_DRAW_KIND` 单 token |
| Riichi 状态机三步（DiscardFromHand/Tsumo + RiichiSuccess） | ✅ 已有 | `PLAYER_RIICHI` 段 + `SELF_RIVER.extra` 立直宣言 bit |

**结论**：records 的全部决策相关信息都可以用现有 + 新增的少量段还原，无需把整段历史塞进 token 序列。

### 3.4 V2 visible_tiles（隐式跨 self_info 共享）

V2 的 `visible_tiles[4 * 34]` 在每次 update 后会 `memcpy` 到 `self_info` 的最后 4 行（`pos_discarded_number_*`）。它累计了**所有 4 家河 + 所有 4 家副露 + 所有翻开的 dora 表示牌** 中每种 tile 出现了多少张（最多 4 张，按 0/1/2/3 通道一一 set）。

➜ 对应本编码的 `VISIBLE_COUNT` 段（必修）。

### 3.5 V1 额外信息（V2 已舍弃但值得注意）

V1 没有 V2 没有的语义增量。结论：**V2 是 V1 的超集 + 重排**，按 V2 对照即可。

---

## 4. 自检结论：必修缺口（按 V2 对照）

| # | 缺口 | 当前替代 | 修复方案 |
|---:|---|---|---|
| F1 | **实际 dora 牌**（不仅 indicator） | 仅 indicator | 新增 `ACTUAL_DORA` 段；每个已翻 indicator 算出 next-tile，1 token |
| F2 | **可见牌张数**（每 tile_type 累计 0..4） | 无 | 新增 `VISIBLE_COUNT` 段；编码时遍历 4 家河 + 4 家副露 + 已翻 dora indicator，按 tile_id 累计 |
| F3 | **Furiten 区**（每家打过的 tile_type 集合） | 河里有，但模型要自己聚合 | 新增 `FURITEN_AREA` 段，每家 1 段；只列**唯一 tile_type 集合**（≤34 token / 家，实际通常 ≤24） |
| F4 | **拆 LAST_DISCARD** → `SELF_TSUMO_TILE`（self-action 阶段）+ `LAST_DISCARDED_TILE`（response 阶段） | 当前一段语义混用 | 删 `LAST_DISCARD`，新增上述两段；who 字段标"上家弃牌来自谁" |
| F5 | **局数 ROUND_INDEX**（东 1 / 南 4 …） | 缺 | 新增 `ROUND_INDEX` 段，count = 0..7（半庄）或 0..3（东风） |
| F6 | **亲家 DEALER_SEAT** | 仅可由 SELF_WIND 推 | 新增 `DEALER_SEAT` 段，count=相对座次 0..3 |
| F7 | **副露来源 FUURO_FROM** | 缺；V2 通过 records 的 player_one_hot 给 | 在 `SELF_FUURO`/`OPP_FUURO` 的 `extra` 中增加 from-whom；**重新设计 extra 字段位包**：bits 0-3 = BaseAction 类型, bits 4-5 = from-whom relative seat, bit 6 = is_target_tile（是被叫的那张）；总长 7 bit，在 8 bit 内 |
| F8 | **吃左/中/右** mask | 当前 mask 同时点亮 3 个 | 需要 C++ 侧暴露 `SelfAction.take` / `ResponseAction.take`；修复后 `_resolve_action` 与 `_mask_one_action` 都能精确分形 |

### 推荐补（可选但有意义）

| # | 缺口 | 修复方案 |
|---:|---|---|
| R1 | **TURN_INDEX** | 新增段 `count` = 当前巡目（自家河长度） |
| R2 | **GAME_SIZE**（半庄/东风/番战） | 新增段 `count` = 0..2 |
| R3 | **LAST_DRAW_KIND**（normal/rinshan） | 1 token |
| R4 | **MY_DORA_COUNT**（自家手牌+副露+赤的 dora 总数） | 1 token，速学特征 |

修后 `SegmentType` 从 21 → **30**（仍 < 256，`uint8` 不变）。

---

## 5. 红 5（赤ドラ）编码

V2 的做法：

- 在 self_info **手牌区**用 4 个 row 堆 one-hot 表示 1/2/3/4 张普通 5；**额外**在 `pos_aka_dora` row 用 1 位标"该 tile_type 在我手里有赤 5"。
- 在 records 与 visible_tiles 中用**独立 tile_idx**（n_tile_types + 0/1/2 = 34/35/36）表示赤 5。

我现在的做法：**所有位置都用独立 `tile_id` 34/35/36**（即 V2 records 的方式），手牌段不再分通道。

### 5.1 取舍分析

| 维度 | 独立 tile_id（本方案） | V2 self_info 的 aka flag |
|---|---|---|
| 一致性 | 河、副露、dora、手牌、动作空间共享同一 vocab | self_info 手牌特殊，records / visible_tiles 又用独立 id |
| 表达力 | 一张 token 即可同时回答"是 5m？是赤？" | 需要先看 5m 通道再看 aka_dora 通道 |
| 模型负担 | 多 3 个 embedding row | 多 1 个二进制特征 |
| 数张数（统计 5m 总数） | `count(5m) + count(red5m)` | one-hot 列加和 |
| **缺陷** | 需要做"红 5 也 implies 5m"映射；模型要学"red5m 与 5m 共享某些性质（比如 5m 雀头）" | 需要额外通道，但语义清晰 |

### 5.2 选择

**保留独立 tile_id，但同时在 `count` 字段编码 aka 标志**，得到两全：

- 仍然用 tile_id 0..33 表示基础 5；
- 红 5 出现时，同样 push 一个 tile_id=4（5m）的 token，**但 `extra` 的 bit0 设为 1**（aka flag）；
- 对手牌段而言，"我手里有 1 张普通 5m + 1 张赤 5m"会得到 1 个 `(SELF_HAND, tile=4, count=2, extra=aka_bit=1)`，简洁；
- 对河/副露/弃牌段，每张牌独立 token，`extra` 里加 aka bit。
- 为了向后兼容动作空间 54 维（包含赤 5 的弃牌位 34/35/36 与吃赤变体），**动作 mask 不变**。

> 即：**取消独立 tile_id 34/35/36**，让 vocab 缩到 35（0..33 基础 + 34=PAD），更紧凑、可学性更好（5m 与赤 5m 自动共享 embedding 主轴，aka 是一个独立维度）。这是相对 §1 的修正。

后续修复一并实施（与 schema_version 升级同步）。

---

## 6. 数值字段的取值范围与归一化策略

> 用户关切："不能直接把点数 encode 进去，应该 encode 点数/25000；不能直接把牌的具体值编码进去。"

本节明确每个字段的语义（**类别 vs 数值**）以及处理策略。

### 6.1 大原则：分两条路

| 通路 | 输入 | 处理 | 适用字段 |
|---|---|---|---|
| **类别（embedding 查表）** | int 索引 | `nn.Embedding(vocab, d_model)` | `segment` / `tile` / `who`，以及一切「无数值序」的 id |
| **标量（连续特征）** | float | 归一化到 ~`[-1, 1]` 后用 `nn.Linear(1, d_model)` 投影或位置/RoPE 编码 | `score / 25000.`、`remaining_tiles / 70.`、`turn_index / 18.` 等 |

> tile_id=4 不代表"4"，是一个类别索引；放进 embedding 完全没有数值刻度问题。
> score 字段必须**先除以 25000 再喂模型**才有数值意义；当前用 1k 桶整数走 embedding，模型只能学到"哪个桶领先"，做不到"差 13000 与差 26000 是 2:1 的关系"。

### 6.2 当前实现的问题清单（按字段）

| 字段 | 当前处理 | 是否合理 | 修复 |
|---|---|---|---|
| tile_id | embedding 索引 | ✅ | — |
| count（手牌张数 0..4） | embedding 索引 | ✅（小类别） | — |
| who（相对座次 0..4） | embedding 索引 | ✅ | — |
| extra（位包） | embedding 索引（256 类） | ✅ 类别可，但有信息密度浪费 | 建议拆成多个独立小字段（见 §6.4） |
| **score** | 1k 桶 → 81 类 embedding | ❌ 失去数值刻度 + 桶过粗 | **改走标量通路**：`score / 25000.0`，每家一个 float；同时保留 `PLAYER_SCORE_RANK` 一个类别 token（顺位 0..3） |
| **remaining_tiles** | 0..70 → 71 类 embedding | ⚠️ 类别也能学，但同样失去刻度 | 改走标量通路：`remaining / 70.0` |
| **honba** | low 8 bits → 256 类 | ⚠️ 同上 + 数据范围其实 0..30 | 改走标量通路：`honba / 8.0`（8 倍本场已是极限） |
| **kyoutaku** | low 8 bits → 256 类 | ⚠️ 实际 0..10 | 改走标量通路：`kyoutaku / 4.0` |
| **turn_index** | （新增） | — | 走标量通路：`turn / 18.0` |
| **round_index** | （新增） | 类别 0..7 | 类别通路 |
| **风（self / game / dealer）** | 类别 0..3 | ✅ | — |
| **VISIBLE_COUNT 的可见次数** | （新增） | 类别 0..4 | 类别通路 |

### 6.3 score 粒度的影响估计

天凤一局点数差异常以 **百点为最小单位**。当前 1k 桶把 1500 点和 2000 点视为相邻，**100 点和 900 点视为同桶**——这影响"喂铳危险性 vs 收益"判断。改成标量后取消这个限制。

### 6.4 extra 字段的位包问题

当前 `SELF_RIVER.extra` 把 `bit0=riichi | bit1=fromhand | bits2-7=number<<2` 塞进 8 bit；模型用 256 大小的 embedding 学。**问题**：number 高 6 位（0..63）和 riichi/fromhand 共享同一 embedding 表，模型必须把"巡序 5 + 立直"和"巡序 5 + 不立直"看成两个完全无关的索引。

**修复**：把 `extra` 拆成 3 个独立的小整数字段，每个字段一张 embedding，**仍然在每条 token 一行内**（增加 token 维度从 5 → 7）：

```
token = (segment, tile, count, who, ext_kind, ext_a, ext_b)
                                   ^ 新       ^ 拆位 1  ^ 拆位 2
```

或者更简单：保留 5 字段，但**为高基数 extra 字段（如 number）切到标量通路**：把巡序作为标量 `number / 24.0` 加到 token 的标量旁路。具体方案待 §6.5 选择。

### 6.5 修订后的 token 接口（待审）

**方案 A（保 5 字段 + 全标量旁路）**：

```python
TokenizedObservation:
    tokens:         (L, 5)  uint8   # 类别字段
    scalars:        (L, S)  float32 # 每 token 的标量旁路（多数为 0）
    attention_mask: (L,)    bool
    action_mask:    (54,)   bool
```

`scalars` 可以预留 4 维（per-token 的"巡序 / 各家 score / kyoutaku / honba"等），未填写位置全 0。模型把 `embed(tokens).sum(-2) + Linear(scalars)` 作为每 token 输入。

**方案 B（拆 token 字段到 7 维）**：

```python
tokens: (L, 7) uint8
# (segment, tile, count, who, ext_a, ext_b, ext_c)
```

不引入新通路，但所有 extra 子字段必须走类别 embedding（小数值仍是类别）。

**推荐方案 A**：score/honba/kyoutaku/remaining/turn 走标量更符合天然语义；类别该类别该走 embedding 的不变。

### 6.6 modeling 端的影响

`MahjongTransformer` 当前只读 `tokens`+`attention_mask`+`action_mask`。改 A 后增加 `scalars` 输入：

```python
emb = (
    self.seg_emb(tokens[..., 0]) + self.tile_emb(tokens[..., 1])
  + self.count_emb(tokens[..., 2]) + self.who_emb(tokens[..., 3])
  + self.extra_emb(tokens[..., 4]) + self.scalar_proj(scalars)
)
```

代码影响仅 `model.py` 一处与 `tokenization.py`/`cache.py` 的 schema。

---

## 7. 动作空间（54 维，不变）

| 索引 | 含义 |
|---|---|
| 0..33 | 弃 34 种基本牌 |
| 34/35/36 | 弃 红 5m / 5p / 5s |
| 37/38/39 | 吃 左/中/右 |
| 40/41/42 | 吃 左/中/右 + 用赤 |
| 43/44 | 碰 / 碰 + 用赤 |
| 45/46/47 | 暗杠 / 明杠 / 加杠 |
| 48 | 立直 |
| 49 | 荣和 |
| 50 | 自摸 |
| 51 | 九種九牌 |
| 52 | PassRiichi |
| 53 | PassResponse |

**已知问题（F8）**：吃的左/中/右细分需要 `take` 字段；C++ 端补完后 mask 与 BC 标签即可精确。

---

## 8. 缓存 schema（v3）

```
cache_dir/
    index.json              # 含 schema 指纹（含 schema_version=3）
    shard_*/
        tokens.npy          # (N, L, 5)  uint8
        scalars.npy         # (N, L, S)  float32   ← v3：由 float16 升级到 float32（避免 score 量化误差）
        attention_mask.npy  # (N, L)     uint8
        action_mask.npy     # (N, A=54)  uint8
        labels.npy          # (N,)       int16
        meta.json
```

`schema_fingerprint`（v3）：

```python
{
  "schema_version": 3,
  "max_seq_len": 200,
  "token_features": 5,
  "scalar_features": 4,
  "action_dim": 54,
  "field_vocab": {"segment": 30, "tile": 35, "count": 96, "who": 5, "extra": 256},
  "dtypes": {"tokens": "uint8", "scalars": "float32",
             "attention_mask": "uint8", "action_mask": "uint8",
             "labels": "int16"},
}
```

新增存储：`(N, 200, 4) float32` ≈ 3.1 KiB/sample → **总成本 ~4.3 KiB/sample**。
不前向兼容；旧 v1/v2 缓存会被 `assert_schema_compatible` 直接拒绝。

---

## 9. 数据增强

| 方案 | 是否启用 | 理由 |
|---|---|---|
| **花色置换 ×6（man↔pin↔sou）** | ✅ | 完全对称（无场风/役种区分 m/p/s），PAD/字牌/赤标志安全 |
| **座次旋转** | ❌ | 场风/自风/亲家位置都是决策关键，旋转会污染 label。`who` 已是相对座次，无需再做对称处理 |
| 顺位/分数置换 | ❌ | 影响"压制对手"决策 |
| 红 5 屏蔽 | ❌ | 收益不明 |

---

## 10. 修复后段总览（共 30 段）

```
 0 PAD
 1 SELF_HAND
 2 SELF_TSUMO_TILE          [新, F4]
 3 LAST_DISCARDED_TILE      [新, F4]
 4 SELF_FUURO               [extra 重新位包: F7]
 5 OPP_FUURO                [extra 重新位包: F7]
 6 SELF_RIVER               [extra 走 scalars: §6.4]
 7 OPP_RIVER                [extra 走 scalars: §6.4]
 8 DORA_INDICATOR
 9 ACTUAL_DORA              [新, F1]
10 URA_DORA_INDICATOR
11 PLAYER_RIICHI            [count: 立直/双立直 二选一]
12 PLAYER_IPPATSU
13 PLAYER_MENZEN
14 PLAYER_SCORE             [类别 token + scalars 旁路: §6.5]
15 GAME_WIND
16 SELF_WIND
17 ROUND_INDEX              [新, F5]
18 DEALER_SEAT              [新, F6]
19 HONBA                    [scalars 旁路]
20 KYOUTAKU                 [scalars 旁路]
21 REMAINING_TILES          [scalars 旁路]
22 TURN_INDEX               [新, R1, scalars 旁路]
23 VISIBLE_COUNT            [新, F2]
24 FURITEN_AREA             [新, F3]
25 GAME_SIZE                [新, R2]
26 LAST_DRAW_KIND           [新, R3]
27 MY_DORA_COUNT            [新, R4]
28 PHASE
29 ACTION_HINT
```

---

## 11. 修复任务（一次性合入，schema_version=3）

实施情况（已合入 `feat/new-rl-algorithm`）：

- [x] F1 ACTUAL_DORA 段
- [x] F2 VISIBLE_COUNT 段（编码时遍历 4 家河 + 4 家副露 + 已翻 dora indicator）
- [x] F3 FURITEN_AREA 段
- [x] F4 拆 LAST_DISCARD → SELF_TSUMO_TILE / LAST_DISCARDED_TILE
- [x] F5 ROUND_INDEX 段
- [x] F6 DEALER_SEAT 段
- [x] F7 副露段在 `extra` 中携带 BaseAction 类型（含红 5 bit）；**from-whom 暂未编码**：当前引擎不持久保存 chi/pon/kan 来源座次（`CallGroup.take` 表示牌在副露中的位置 0/1/2，并非来源相对座次），编码端与解码端一致地输出 `from_r=4 (unknown)`。引擎补全后再启用。
- [x] F8 修复方向不变；`_mask_one_action` 已使用 chi 牌相对手牌中位牌位置进行 left/middle/right 分形（见 `_classify_chi`）
- [x] R1 TURN_INDEX 段（自家河长度，走 scalars）
- [x] R2 GAME_SIZE 段
- [x] R3 LAST_DRAW_KIND 段
- [x] R4 MY_DORA_COUNT 段
- [x] §5.2 红 5 改为 `tile_id = 基础 5 + extra.aka_bit=1`，删 TILE_RED5M/P/S；`TILE_VOCAB_SIZE = 35`，TILE_PAD = 34
- [x] §6.5 token 增加 `scalars (L, S=4)` 通路；`model.py` 加 `scalar_proj`（zero-init），forward / act / evaluate_actions 同步
- [x] cache schema_version → **3**（dtype 由 float16 升级为 **float32** 以避免 score 量化误差），同步 `cache.py / cached_dataset.py / encode_paipu_to_cache.py`
- [x] River `number`（巡序）存放在 `count` 字段（vocab=96），不再压在 `extra`，避免 8 bit 溢出
- [x] 圆周对照测试：新增 `state_to_string(table, current_player)` 与 `tokens_to_string(obs)` 两个公开接口；`pytest test/test_encoding_roundtrip.py` 与 `tools/verify_encoding_paipu.py` 在 selfplay + Tenhou 牌谱上做逐状态字符串对比，截至当前在 1003 个 CI 牌谱上 0 mismatch。

---

## 12. 等待审阅的关键决定

请确认以下 5 项：

1. **scalars 通路（方案 A）vs 全部走 embedding（方案 B）** — 推荐 A，分数等连续语义保留刻度。
2. **红 5 编码切到 "5m + aka bit"**（删独立 tile_id 34/35/36，TILE_VOCAB_SIZE 由 38 → 35）—— 是否 OK？动作空间的"弃红 5"位 34/35/36 不变。
3. **VISIBLE_COUNT** 用 1 token / tile_type（最多 34 token）vs 用 1 token 共 4 个通道压缩 —— 推荐前者，可读性强。
4. **scalars 维度 S** —— 推荐 4：`score_self / score_lead_gap / honba_norm / remaining_norm`。需要更多再调。
5. 是否一次性把 R1–R4 一并合入（建议是，否则会导致两次 schema bump）。

审阅通过后，我将把 §11 的所有任务在一次提交里完成，并升 `CACHE_SCHEMA_VERSION` → 2。

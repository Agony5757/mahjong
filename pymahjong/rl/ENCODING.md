# 编码方案设计文档（待审）

> 本文档描述 `pymahjong.rl` 子包的状态/动作编码方案，并标注**当前实现已覆盖 ✅、计划补齐 🟡、显式不做 ❌**。请按"是否覆盖了所有决策必需信息"来审。
>
> 目标：纯 Python 即可生成 token 序列，避免对 C++ 编码器的依赖；同时让 Transformer 友好（变长、稀疏、可掩码）。

## 0. TL;DR

- 状态 = 变长 token 序列 `[L, 5]`，每行 `(segment, tile, count, who, extra)`。
- 动作 = 54 维离散，与 `MahjongEnv.ACTION_DIM` 完全兼容。
- 缓存 dtypes 全部 `uint8` / `int16`，1 sample ≈ 1.1 KB。
- 数据增强：**仅花色置换 ×6**（man/pin/sou），座次旋转**禁止**（场风/自风/亲是决策关键）。

---

## 1. Token 字段总览

| 字段 | 含义 | 当前 vocab | 缓存 dtype |
|---|---|---|---|
| `segment` | 段落类型（PAD/SELF_HAND/SELF_FUURO/...） | 见 §2，目前 21（PAD=0 起） | `uint8` |
| `tile`    | 牌 id：0–33 = 34 基础牌；34/35/36 = 红 5m/p/s；37 = PAD | 38 | `uint8` |
| `count`   | 该 tile 的张数 0–4；非牌 token 时复用为 small-int payload | 96 | `uint8` |
| `who`     | 相对座次：0=自家，1=下家，2=对家，3=上家，4=N/A（场面） | 5 | `uint8` |
| `extra`   | 段内附加 payload（见各段说明） | 256 | `uint8` |

**牌 id 编码细节（重要）**：

- 0..8   = 1m..9m
- 9..17  = 1p..9p
- 18..26 = 1s..9s
- 27..30 = 东南西北
- 31..33 = 白发中
- 34/35/36 = 赤 5m / 5p / 5s（独立 id，可与普通 5 在 `count` 上分开统计）
- 37    = PAD

> 这样 dora 表示牌 / 弃牌 / 副露牌都可以共用同一个 vocab，而花色置换 LUT 也只需要在 0..26 + 34..36 上动手。

---

## 2. 段落（Segment）一览

| ID | 段名 | 是否实现 | 含义 / `count` / `who` / `extra` 用法 |
|---:|---|---|---|
| 0  | PAD | ✅ | 占位，不入 attention |
| 1  | SELF_HAND | ✅ | 自家暗手；按 tile 聚合，`count`=张数，`who=0`，`extra=0` |
| 2  | SELF_TSUMO | 🟡 已定义未使用 | 自家刚摸的牌单独 1 token（区分"暗手 + 摸牌"） |
| 3  | SELF_FUURO | ✅ | 自家副露每张 1 token；`extra` = `BaseAction` 类型（吃/碰/明杠/暗杠/加杠） |
| 4  | OPP_FUURO | ✅ | 他家副露；`who` 标对手；`extra` 同上 |
| 5  | SELF_RIVER | ✅ | 自家河每张 1 token；`extra` 位包：bit0=立直宣言牌，bit1=fromhand，bits2-7=巡序 |
| 6  | OPP_RIVER | ✅ | 他家河；`who` 标对手 |
| 7  | DORA_INDICATOR | ✅ | 当前已翻 dora 表示牌（含杠后翻牌）；`who=4` |
| 8  | URA_DORA_INDICATOR | 🟡 已定义未使用 | 立直胡牌后才公开；当前未填 |
| 9  | PLAYER_RIICHI | ✅ | 每家 1 token；`count`=立直与否，`extra`=double_riichi |
| 10 | PLAYER_IPPATSU | ✅ | 每家 1 token；`count`=一发与否 |
| 11 | PLAYER_MENZEN | ✅ | 每家 1 token；`count`=门前清与否 |
| 12 | PLAYER_SCORE | ✅ | 每家 1 token；`count` = 1k 桶分数（-5000..75000 → 0..80） |
| 13 | GAME_WIND | ✅ | 场风（东=0/南=1/...）；`count`=风 id，`who=4` |
| 14 | SELF_WIND | ✅ | 自风；`count`=风 id，`who=0` |
| 15 | HONBA | ✅ | 本场数（`count` 取低 8 位） |
| 16 | KYOUTAKU | ✅ | 立直棒数量 |
| 17 | REMAINING_TILES | ✅ | 剩余山牌数（0..70） |
| 18 | LAST_DISCARD | ⚠️ 语义混用 | **当前同时被自摸和上家弃牌复用**（`encode()` 第 264–269 行）；需要拆 |
| 19 | PHASE | ✅ | 引擎 phase id；`extra`=riichi 第 2 步标志 |
| 20 | ACTION_HINT | ✅ | 0=self / 1=response / 2=终局 |

### 🟡 计划新增段（修复信息缺口）

| 新 ID | 段名 | 必要性 | 说明 |
|---:|---|---|---|
| 21 | ROUND_INDEX | **必须** | 局数 0..3（东 1=0..东 4=3，南 1=0..），与 GAME_WIND 组合得到完整"东 1 局~南 4 局"。当前缺！|
| 22 | DEALER_SEAT | **必须** | 亲家相对座次 0..3。当前只能由 `SELF_WIND==东` 推出，模型还得学 |
| 23 | TURN_INDEX | 推荐 | 巡目 0..24（自家河长度即可，bucketed） |
| 24 | LAST_DISCARDED_TILE | **必须** | response 阶段才填：被讨论的那张弃牌 + 来自哪家（`who`） |
| 25 | SELF_TSUMO_TILE | **必须** | self-action 阶段刚摸那张 |
| 26 | FUURO_FROM | 推荐 | 鳴き来源座次：碰/明杠/吃从谁打来。当前 fuuro 没标，对防御决策重要 |
| 27 | MY_DORA_COUNT | 可选 | 自家手牌 + 副露中 dora（含赤）数；可由模型推但显式更省参 |

> 重申 §1：以上新增只占用 `segment` vocab 的 7 个 id（27 < 256），`uint8` 仍然够用，**不影响缓存 schema 兼容性后**重新编码即可。

---

## 3. 当前实现 vs 应有信息：审查清单

按"决策需要什么"逐项核对：

| 决策必需信息 | 是否覆盖 | 在哪里 |
|---|---|---|
| 自家手牌（含赤 5） | ✅ | SELF_HAND，赤 5 用独立 tile id |
| 自家副露（含杠类型） | ✅ | SELF_FUURO，extra=BaseAction |
| 三家副露 | ✅ | OPP_FUURO + who |
| 四家牌河（含立直宣言牌、是否手切） | ✅ | SELF_RIVER / OPP_RIVER + extra 位包 |
| 摸牌 / 上家弃牌（这一步要决策的对象） | ⚠️ | LAST_DISCARD 段被复用，**需要拆**为 SELF_TSUMO_TILE / LAST_DISCARDED_TILE |
| ドラ表示牌（含杠后） | ✅ | DORA_INDICATOR，按 `n_active_dora` 截断 |
| 裏ドラ | 🟡 | URA_DORA_INDICATOR 已留段，胡牌后训练时才填 |
| 立直状态（每家） | ✅ | PLAYER_RIICHI |
| 双立直（每家） | ✅ | PLAYER_RIICHI.extra |
| 一発（每家） | ✅ | PLAYER_IPPATSU |
| 门前清（每家） | ✅ | PLAYER_MENZEN |
| **持点（每家）** | ✅ | PLAYER_SCORE，1k 桶 |
| **场风** | ✅ | GAME_WIND |
| **自风** | ✅ | SELF_WIND |
| **亲家是谁** | 🟡 | 仅可由 SELF_WIND==东 推得；建议加 DEALER_SEAT 显式 token |
| **局数（东 1 局/南 2 局…）** | ❌ | 当前缺！必须加 ROUND_INDEX |
| **本場** | ✅ | HONBA |
| **供託 / 立直棒** | ✅ | KYOUTAKU |
| 残山 | ✅ | REMAINING_TILES |
| 巡目 | 🟡 | 隐含于 SELF_RIVER.extra 的 number 字段，建议增显式 TURN_INDEX |
| 鳴き的来源（碰/明杠/吃从谁） | ❌ | fuuro 仅记录类型 + 牌；建议加 FUURO_FROM |
| 引擎 phase / response 标志 | ✅ | PHASE / ACTION_HINT |
| 立直选择第 2 步标志 | ✅ | PHASE.extra |
| Oracle（他家暗手） | ✅ | 仅 oracle 训练时启用 |

**结论**：当前实现已覆盖大多数关键信息，但有 **3 个必修**：
1. 加 ROUND_INDEX（局数）
2. 加 DEALER_SEAT（亲家相对座次）
3. 拆 LAST_DISCARD → SELF_TSUMO_TILE + LAST_DISCARDED_TILE

以及 **2 个推荐补**：FUURO_FROM、TURN_INDEX。

---

## 4. 动作空间（54 维）

完全沿用 `MahjongEnv.ACTION_DIM`，方便复用旧检查点：

| 索引区间 | 含义 |
|---|---|
| 0..33 | 弃 34 种基本牌 |
| 34/35/36 | 弃 红 5m / 5p / 5s |
| 37/38/39 | 吃（左/中/右） |
| 40/41/42 | 吃带赤（左/中/右） |
| 43/44 | 碰 / 碰带赤 |
| 45/46/47 | 暗杠 / 明杠 / 加杠 |
| 48 | 立直 |
| 49 | 荣和 |
| 50 | 自摸 |
| 51 | 九種九牌 |
| 52 | PassRiichi（立直阶段不立直） |
| 53 | PassResponse（响应阶段过） |

**已知瑕疵（当前实现）**：
- 吃的"左/中/右"细分需要 `take` tile 与 `correspond_tiles` 两边比对才能判，pybind 当前不暴露 `take`。`_mask_one_action` 暂时一次点亮三个吃位（含赤 6 位）。
- BC 标签生成 `_engine_idx_to_unified` 也对所有吃统一返回 `CHIMIDDLE`/`CHIMIDDLE_USERED`，会让 BC 学到的"吃"动作不分形状。
- **建议在 C++ 侧给 `SelfAction`/`ResponseAction` 增加一个 `take` 字段**（即吃来的那张），pure Python 侧就能精确区分；这是预计在编码定稿后顺带做的小改动。

---

## 5. 缓存 schema

落盘格式（`pymahjong.rl.cache`）：

```
cache_dir/
    index.json                # 含 schema 指纹
    shard_w00_00000/
        tokens.npy            # (N, L, 5) uint8
        attention_mask.npy    # (N, L)    uint8
        action_mask.npy       # (N, A=54) uint8
        labels.npy            # (N,)      int16
        meta.json
```

`schema_fingerprint` 包含：

```python
{
  "schema_version": 1,
  "max_seq_len": 200,
  "token_features": 5,
  "action_dim": 54,
  "field_vocab": {"segment": 21, "tile": 38, "count": 96, "who": 5, "extra": 256},
  "dtypes": {"tokens": "uint8", "attention_mask": "uint8",
             "action_mask": "uint8", "labels": "int16"}
}
```

**新增 ROUND_INDEX/DEALER_SEAT 等段时，`segment` vocab 涨到 28**，`field_vocab["segment"]` 变化 → schema 指纹自动 mismatch，旧缓存会被显式拒绝（ValueError），不会出现"参数不变但语义错位"。

存储成本：
- 每条样本 = 200×5 + 200 + 54 + 2 = **1256 B** ≈ **1.23 KiB**
- 6e7 条决策（2025 凤凰桌全量预估） ≈ **70 GB**
- 单个 shard 65 536 条 ≈ 80 MB，便于并发写 / 顺序读

---

## 6. 数据增强方案

### ✅ 花色置换 ×6（应用）

把 `{man, pin, sou}` 任一排列映射到 token 的 `tile` 字段：

- 0..8 / 9..17 / 18..26 三段块按排列搬迁；
- 赤 5（34/35/36）跟随其 5 所在的花色一起置换；
- 字牌 27..33、PAD 37 保持不变；
- LUT 长度 38，预先算好 6 张表，`__getitem__` 时随机选一张。

**理由**：花色之间无对称破缺（既无场风/自风涉及到 m/p/s，也无役种区分），完美对称增强。每个样本带 6 倍有效信息。

### ❌ 座次旋转（禁止应用）

> 用户明确指示：东南西北的位置对决策关键，不能旋转。

技术理由也成立：
- 场风（GAME_WIND）+ 自风（SELF_WIND）一起决定**亲家是谁**、**自风牌役种是否成立**（自风的字牌做雀头/刻子能成役）。
- 亲家加分规则（出冲赔率 1.5×、连庄维持等）依赖座次。
- 模型已经看的是"相对座次"（who 字段已经是 `(seat - me) % 4`），但**绝对的场风/自风/局数**是不能动的。

实现上：`CachedTokenDataset` **不再暴露** `seat_rotate` 参数；`BCConfig` 同步移除该字段。

### 🟡 其他可考虑（暂不做）

- 顺位/分数置换：把 4 家分数顺序置换。在 BC 阶段会让"压制对手"类决策学坏；不做。
- 红 5 屏蔽：训练时随机丢弃赤 5 信息。无明显收益；不做。

---

## 7. 兼容性 & 迁移

- **当前 commit (`5cd1577`) 的 schema_version=1**，但段定义只到 ID 20。
- 一旦按 §2 / §3 增加 ROUND_INDEX 等新段，会：
  1. 修改 `tokenization.py` 的 `SegmentType` 枚举与 `encode()` 逻辑；
  2. `NUM_SEGMENTS` / `FIELD_VOCAB["segment"]` 自动变化；
  3. schema 指纹改变，旧缓存被 `assert_schema_compatible` 拒绝；
  4. 重跑 `tools/encode_paipu_to_cache.py` 生成新缓存。
- 因此审查通过后，建议先把所有补丁一次性合入 → 统一升 `CACHE_SCHEMA_VERSION=2` → 再跑大规模编码。

---

## 8. 待办（编码层，等审）

- [ ] 加 `ROUND_INDEX` segment（必须）
- [ ] 加 `DEALER_SEAT` segment（必须）
- [ ] 拆 `LAST_DISCARD` → `SELF_TSUMO_TILE` / `LAST_DISCARDED_TILE`（必须）
- [ ] 加 `FUURO_FROM` extra 字段（推荐）
- [ ] 加 `TURN_INDEX` segment（推荐）
- [ ] 在 C++ 侧暴露 `SelfAction.take` / `ResponseAction.take` 以精确解析吃的形状
- [ ] 升 `CACHE_SCHEMA_VERSION` → 2 并重新编码
- [ ] 单元测试：「编码一局 paipu，检查所有 28 个 segment 至少出现过一次」

---

## 9. 等待审查的关键决定

请确认以下几个判断：

1. **`tile` 总 vocab = 38（含赤 5）** — 是否可接受？另一种方案是把赤标志放到 `extra` 一位，让 `tile` 保持 34；但目前红 5 在很多状态（手牌、副露、河、弃牌）里都要查 dora，独立 id 处理一致性更好。
2. **PLAYER_SCORE 用 1000 点桶（81 个 bucket）** — 是否够细？精确分数必要时可改 100 点桶（vocab 仍 ≤256）。
3. **巡目用 SELF_RIVER 长度推断 vs 单独 token** — 我建议加单独 TURN_INDEX。
4. **Stage 2 RL 阶段是否要换更密的 reward**（当前只在终局给 `payoffs/25000`） — 这一项虽然不在编码层，但相关；编码层无须改动。

请审查并指出补充/调整。

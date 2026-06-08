# pymahjong.rl — MajNova v0 训练栈

用 Transformer 网络训练日本麻将（立直麻将）AI。两阶段训练：**第一阶段** 行为克隆（监督学习），**第二阶段** Mortal 风格价值学习（强化学习）。

## 核心思路

把牌桌状态编码成一段**变长的事件流**（每事件 100-dim bitset，序列长 ≤512），让 Transformer 的注意力机制自动聚焦关键信息。每局产出 4 条 per-seat 轨道（每位玩家的可见视角）。

## 文件说明

| 文件 | 作用 |
|---|---|
| `tokenization.py` | 把 `pm.Table` 转成事件流 + DECIDE 标签；包含 `StreamingPaipuDataset` |
| `live_encoder.py` | 在线推理用的事件流编码器（`LiveEncoder`） |
| `transformer.py` | `EventStreamTransformer`：状态编码器 + 可选 linear policy head |
| `douzero.py` | `DouzeroTransformer(EventStreamTransformer)`：在编码器上加 Douzero 风格按合法动作打分的共享 MLP 头 |
| `mortal_qnet.py` | `MortalQNet`：复用 `EventStreamTransformer` 编码器 + Douzero Q 头（直接输出 Q(s,a)） |
| `mortal.py` | Mortal 风格价值学习训练器 (`train_mortal`) |
| `mortal_eval.py` | 每个 checkpoint 跑 `mjai_bench_v2` 1v3/3v1 对阵 Mortal 基准 |
| `grp.py` | GRP / placement / points 三种顺位奖励计算 |
| `action_features.py` | 54 动作 × 50-dim 描述符表（Douzero 头输入） |
| `legal_actions.py` | 从 (B, 54) action_mask 抽出 K 个合法动作的 per-action 张量 |
| `env.py` | `MultiAgentEnv`：单手牌 4 人环境，事件流观测 |
| `hanchan_env.py` | `HanchanEnv`：完整半庄包装（连庄/本场/供托/飞/西入） |
| `opponent_pool.py` | `OpponentPool`：训练中的历史快照对手池 |
| `selfplay_eval.py` | 训练中的 4 座自互殴评估（agari rate / 决策数 / payoff） |
| `cache.py` | `ShardWriter`：mmap 友好的 packbits 分片输出 |
| `cached_dataset.py` | `CachedEventDataset`：磁盘缓存的 map-style Dataset（含花色增强 collate） |
| `collate.py` | batched event collate 辅助函数 |
| `splits.py` | 训练/验证/测试集切分（按 shard / track / game id） |
| `action_space.py` | 54 动作统一空间 + `ActionEncoder` 双向映射 + 动作掩码填充 |
| `bc.py` | 行为克隆训练器 (`train_bc`)，内置 self-play eval / 早停 / DDP / wandb |
| `common/config.py` | `TransformerConfig`（默认 d=192/L=4/H=6/FF=4） |
| `common/optim.py` | AdamW / Muon 优化器构建 + LR scheduler |
| `_tile_utils.py` | 私有：tile 字符串、meld 类型常量、`CallGroup` 源座位推断 |
| `_manifest.py` | 私有：shard manifest I/O 基础类 |

## 快速开始

### 安装

```bash
uv venv && source .venv/bin/activate
uv pip install ".[dev]"
```

### 第一阶段：行为克隆

```python
from pymahjong.rl.bc import train_bc, BCConfig

train_bc(config=BCConfig(
    cache_dir="cache/houou",   # 预编码的牌谱缓存
    batch_size=256,
    n_steps=100_000,
    suit_permute=True,          # 花色增强 ×2 (万↔筒互换；条不动，因为有绿一色)
))
```

先用工具把天凤 XML 牌谱编码到缓存：

```bash
# 单机
python tools/encode_paipu_to_cache.py --paipu-dir paipuxmls --out cache/houou \
    --workers 8 --shard-rows 8192

# DDP 多卡 BC
torchrun --nproc-per-node=8 tools/train_bc.py \
    --cache-dir cache/houou \
    --split-by track-id --ratios 0.9,0.05,0.05 \
    --d-model 384 --n-layers 6 --n-heads 8 --ff-mult 4 --scorer-hidden 256 \
    --batch-size 256 --n-steps 200000 --suit-permute \
    --save-path checkpoints/bc.pt
```

### 第二阶段：Mortal 风格价值学习

Q 网络 = **`EventStreamTransformer` 编码器 + Douzero Q-head**（`mortal_qnet.py`）：状态用事件流编码，动作用 Douzero 描述符，共享 scorer **直接输出每个合法动作的 Q(s,a)**。

- **蒙特卡洛 Q 目标**：`q_target = gamma^steps_to_done * kyoku_reward`（无 bootstrap）。
- **DQN 损失** `0.5 * MSE(Q[a], q_target)` + 可选 **CQL** 保守正则 + **辅助 next-rank 头**。
- **GRP 顺位奖励**（`grp.py`）：用整局得分序列换算每局「最终顺位期望点数」的增量。三种奖励：`placement`（默认，无需预训练，顺位感知）、`grp`（需训练 GRP）、`points`（原始得分差）。
- 数据来自 `HanchanEnv` 的**完整半庄**自对弈（提供顺位与逐局得分）。
- 更新在 `train()` 模式（MC 回归无重要性比率，dropout 安全）。

```bash
# 从 BC 权重热启动（仅辅助 rank 头是新初始化的）
python tools/train_mortal.py \
    --bc-checkpoint checkpoints/bc.best.pt \
    --save-path checkpoints/mortal.pt \
    --reward-kind placement --total-steps 1000000 --rollout-steps 8192 --lr 1e-4

# 最忠实 Mortal：训练好的 GRP 网络 + CQL
python tools/train_mortal.py --bc-checkpoint checkpoints/bc.best.pt \
    --reward-kind grp --grp-ckpt checkpoints/grp.pt --cql
```


## 关键设计决策

**为什么不用旧的 93×34 矩阵？** 旧编码是给 CNN 设计的，大量位置是零。新编码用变长 token，平均只需 30-80 个 token，信息密度更高。

**为什么不旋转座次？** 场风、自风、亲家位置影响决策（比如东 1 和南 4 策略完全不同），旋转会破坏标签。`who` 字段已用相对座次，不需要额外对称处理。

**为什么花色可以置换？** 万和筒在规则上完全对称，可以安全互换。但**条不能参与置换**——绿一色只使用条子牌（2s,3s,4s,6s,8s）和发，如果条被换成了万或筒，原本的绿一色状态就会变成不合法的游戏状态。因此只有万↔筒互换，提供 2 倍数据增强。

**动作空间 54 维怎么来的？** 34 种基本牌弃牌 + 3 种红 5 弃牌 + 9 种吃碰杠 + 立直/荣和/自摸/九种九牌/2 种 Pass = 54。

**为什么 Douzero 头而不是 Linear 头？** 共享 scorer 跨结构相似的动作复用权重（弃 1m 和弃 2m 不再有完全独立的输出头，只差 tile descriptor），无掩码泄漏（不存在 illegal slot 的 partition function），对合法集排列不变。是 Linear 头的严格超集。

## 与旧版本的兼容性

- 旧的 `MahjongEnv` / `SingleAgentMahjongEnv` 和 VLOG 预训练模型完全不受影响（V1 CNN 编码器保留为 legacy 公共 API）
- `pymahjong.rl` 是可选的，PyTorch 是可选依赖（懒加载）

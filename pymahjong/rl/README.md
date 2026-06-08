# pymahjong.rl — 麻将 AI 训练框架

用 Transformer 网络训练日本麻将（立直麻将）AI。两阶段训练：先监督学习（行为克隆），再强化学习（PPO 自我对弈）。

## 核心思路

把牌桌状态编码成一段**变长的 token 序列**（而非传统的固定大小矩阵），让 Transformer 的注意力机制自动聚焦关键信息。

## 文件说明

| 文件 | 作用 |
|---|---|
| `tokenization.py` | 把 `pm.Table` 转成 token 序列 + 动作掩码 |
| `model.py` | Transformer 策略-价值网络（~5M 参数） |
| `env_v2.py` | Gymnasium 兼容环境（单智能体 / 4人对弈） |
| `cache.py` | 磁盘缓存格式（mmap 友好，带版本校验） |
| `cached_dataset.py` | 从缓存读取的 Dataset（支持花色增强） |
| `dataset.py` | 在线数据集（自博弈 / 牌谱回放） |
| `bc.py` | 第一阶段：行为克隆训练 |
| `ppo.py` | 第二阶段：PPO 自博弈训练 |
| `buffers.py` | PPO 用的 Rollout Buffer（含 GAE） |
| `ENCODING.html` | 编码方案可视化文档 |
| `MODEL.html` | 网络结构可视化文档 |

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

先用工具把牌谱编码到缓存：

```bash
# 随机自博弈生成测试数据
python tools/encode_paipu_to_cache.py selfplay --out cache/smoke --games 200

# 从天凤牌谱 XML 编码
python tools/encode_paipu_to_cache.py paipu --paipu-dir paipuxmls --out cache/houou
```

### 第二阶段：PPO 自博弈

```python
from pymahjong.rl.ppo import train_ppo, PPOConfig

train_ppo(
    bc_checkpoint="checkpoints/bc.pt",
    config=PPOConfig(total_steps=10_000_000),
)
```

### 第二阶段（替代方案）：Mortal 算法（价值型自博弈）

除 PPO 外，还提供 **Mortal 风格的价值学习**（`pymahjong/rl/v5/mortal.py`）。Q 网络 = **原版 `EventStreamTransformer` 编码器 + 独立 Douzero Q-head**（`mortal_qnet.py`）：状态用 V5 事件流编码，动作用 V5 Douzero 描述符，共享 scorer **直接输出每个合法动作的 Q(s,a)**。与 PPO 的区别：

- **蒙特卡洛 Q 目标**：`q_target = gamma^steps_to_done * kyoku_reward`（无 bootstrap）。
- **DQN 损失** `0.5*MSE(Q[a], q_target)` + 可选 **CQL** 保守正则 + **辅助 next-rank 头**。
- **GRP 顺位奖励**（`pymahjong/rl/v5/grp.py`）：用整局得分序列换算每局「最终顺位期望点数」的增量。三种奖励：`placement`（默认，无需预训练，顺位感知）、`grp`（需训练 GRP）、`points`（原始得分差）。
- 数据来自 `HanchanEnv` 的**完整半庄**自对弈（提供顺位与逐局得分）。
- 更新在 `train()` 模式（MC 回归无重要性比率，dropout 安全；与 PPO 必须 `eval()` 不同）。

```bash
# 从 V5 BC 权重热启动（仅辅助 rank 头是新初始化的）
python tools/train_mortal_v5.py \
    --bc-checkpoint checkpoints/bc_v5.best.pt \
    --save-path checkpoints/mortal_v5.pt \
    --reward-kind placement --total-steps 1000000 --rollout-steps 8192 --lr 1e-4

# 最忠实 Mortal：训练好的 GRP 网络 + CQL
python tools/train_mortal_v5.py --bc-checkpoint checkpoints/bc_v5.best.pt \
    --reward-kind grp --grp-ckpt checkpoints/grp.pt --cql
```


## 关键设计决策

**为什么不用旧的 93×34 矩阵？** 旧编码是给 CNN 设计的，大量位置是零。新编码用变长 token，平均只需 30-80 个 token，信息密度更高。

**为什么不旋转座次？** 场风、自风、亲家位置影响决策（比如东 1 和南 4 策略完全不同），旋转会破坏标签。`who` 字段已用相对座次，不需要额外对称处理。

**为什么花色可以置换？** 万和筒在规则上完全对称，可以安全互换。但**条不能参与置换**——绿一色只使用条子牌（2s,3s,4s,6s,8s）和发，如果条被换成了万或筒，原本的绿一色状态就会变成不合法的游戏状态。因此只有万↔筒互换，提供 2 倍数据增强。

**动作空间 54 维怎么来的？** 34 种基本牌弃牌 + 3 种红 5 弃牌 + 9 种吃碰杠 + 立直/荣和/自摸/九种九牌/2 种 Pass = 54。

## 与旧系统的兼容性

- 旧的 `MahjongEnv` / `SingleAgentMahjongEnv` 和预训练模型完全不受影响
- `pymahjong.rl` 是可选的，PyTorch 是可选依赖

## 文档

- [ENCODING.html](ENCODING.html) — 编码方案的图文详解
- [MODEL.html](MODEL.html) — 网络结构的图文详解

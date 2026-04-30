# Paipu Replay

Paipu (牌譜) is the Japanese term for game records. pymahjong supports replaying games from Tenhou.net paipu files for validation and analysis.

## Overview

The paipu replay system allows you to:

1. Validate the game engine against real game records
2. Analyze professional player decisions
3. Generate training data from human games

## Tenhou XML Paipu Format

Tenhou.net publishes game records as XML files (`.txt` extension). The complete format is defined in `pymahjong/tenhou_paipu_check.py`.

### XML Tag Reference

The following table documents all supported XML tags in Tenhou paipu files:

| Tag | 说明 | 属性/内容 |
|-----|------|----------|
| `<SHOWER seed="...">` | 牌山生成 | `seed`: base64 MT19937+SHA512 种子 |
| `<GO type="N">` | 游戏规则 | `type`: 位掩码（见下表） |
| `<UN ...>` | 玩家信息 | 名字/等级等（解析但不使用） |
| `<INIT ten="..." oya="N" seed="..." hai0="..." hai1="..." hai2="..." hai3="...">` | 游戏初始化 | 见下方详解 |
| `<DORA hai="N">` | 翻开宝牌 | `hai`: tile ID |
| `<REACH who="N" step="1\|2">` | 立直宣言 | step1=宣言，step2=成功确认 |
| `<T>` / `<U>` / `<V>` / `<W>` | 摸牌 | Tag索引=玩家ID(0-3)，内容为tile ID |
| `<D>` / `<E>` / `<F>` / `<G>` | 舍牌 | Tag索引=玩家ID(0-3)，内容为tile ID |
| `<N who="N" m="NNNN">` | 鸣牌 | `who`=鸣牌者，`m`=编码的牌组 |
| `<AGARI ...>` | 和牌 | 含详细得分/役种信息 |
| `<RYUUKYOKU ...>` | 流局 | 含tenpai信息 |

### Game Type (`<GO type="N">`)

`type` 是位掩码：

| 位 | 值 | 含义 |
|----|----|------|
| 0 | 1 | PVP（人对人） |
| 1 | 2 | 无赤宝牌 |
| 2 | 4 | 无食断 |
| 3 | 8 | 半庄（hanchan） |
| 4 | 16 | 三人麻将 |
| 5 | 32 | Pro（专业） |
| 6 | 64 | 快速 |
| 7 | 128 | 上级 |

**四人东风为例**：`type=0`（东风/新人）

### `<INIT>` 详解

```
<INIT ten="25000,25000,25000,25000" oya="0"
      seed="123456789,0,0,3,5,..."
      hai0="0,8,18,26,27,30,32,..."
      hai1="1,9,19,27,28,31,33,..."
      hai2="2,10,20,27,29,30,32,..."
      hai3="3,11,21,27,28,31,33,...">
```

- `ten`: 初始分数（除以100后传入 `PaipuReplayer.init()`）
- `oya`: 庄家玩家 ID (0-3)
- `seed`: 逗号分隔：
  - `[0]`: game_order（决定场风：game_order // 4 = 0=东, 1=南, 2=西, 3=北）
  - `[1]`: honba 本场数
  - `[2]`: kyoutaku 立直棒
  - `[3]`: dice1 骰子1
  - `[4]`: dice2 骰子2
  - `[5+]`: dora0, dora1, ... 初始宝牌指示牌
- `hai0..hai3`: 各玩家初始手牌（13张，逗号分隔 tile ID）

### Tile ID 映射规则

Tenhou tile ID (0-135) 编码：

```
tile_id = basetile × 4 + copy_index
basetile = tile_id // 4   (0-33)
copy_index = tile_id % 4 (0-3)
```

**花色/数字映射**：

| basetile | 牌 |
|---------|---|
| 0-8 | 1m-9m |
| 9-17 | 1p-9p |
| 18-26 | 1s-9s |
| 27-33 | 1z-7z（东/南/西/北/白/发/中） |

**赤宝牌**：5m红=id4, 5p红=id13, 5s红=id22

### MT19937 Seed → Yama 生成

`<SHOWER seed="mt19937ar-sha512-n288-base64,...">` 中的 seed 用于初始化 MT19937 伪随机数生成器，产生确定性牌山。

在代码中调用：
```python
from MahjongPy import TenhouShuffle
TenhouShuffle.instance().init(seed)  # base64 seed 字符串
yama = TenhouShuffle.instance().generate_yama()  # 136 tile IDs
```

### 鸣牌编码 (`<N who="N" m="NNNN">`)

`m` 是一个16位整数，二进制编码鸣牌信息：

```
bit[0-1]:   鸣牌类型 (0=Chi, 1=Pon, 2=Kan, 3=AnKan)
bit[2-7]:   被鸣牌 basetile
bit[8-15]:  手牌中用于鸣牌的牌（3个basetile）
```

`decodem()` 函数（`pymahjong/tenhou_paipu_check.py`）负责解码。

### `<REACH>` 立直流程

- **step=1**: 立直宣言，`who` 玩家宣布立直（score -= 1000, kyoutaku++）
- **step=2**: 立直确认，1巡后若未被发现荣和则立直成功

前端实现时，step=1 宣言后须进入特殊状态，等待 step=2 确认。

## Using Paipu Replay

### Python: `paipu_replay()`

```python
import pymahjong as pm
pm.paipu_replay(mode='debug')  # 自动重放 paipuxmls/ 目录下的所有 XML
```

### C++ PaipuReplayer

```python
import MahjongPyWrapper as pm

# Create replayer
replayer = pm.PaipuReplayer()

# Initialize with game state
replayer.init(
    yama=[...],           # 136 tile IDs
    init_scores=[25000]*4,
    kyoutaku=0,
    honba=0,
    game_wind=0,          # 0=East, 1=South, etc.
    oya=0                 # Parent player
)

# Get available actions
phase = replayer.get_phase()
if phase < 4:
    actions = replayer.get_self_actions()
else:
    actions = replayer.get_response_actions()

# Make selection
replayer.make_selection(selection_index)

# Get result (when game_over)
result = replayer.get_result()
```

### Complete Flow: Tenhou XML → Replayer

```python
import MahjongPyWrapper as pm
from pymahjong.tenhou_paipu_check import PaipuReplay

# Parse XML
p = PaipuReplay(xml_path)
p._paipu_replay()  # populates replayer

# Use replayer
rp = p.replayer
for _ in range(200):  # max steps
    if rp.get_phase() == 16:  # GAME_OVER
        break
    phase = rp.get_phase()
    if phase < 4:
        actions = rp.get_self_actions()
    else:
        actions = rp.get_response_actions()
    # replay with same actions
    rp.make_selection(0)  # pass

result = rp.get_result()
```

## Replay Validation

CI validates the engine against real Tenhou games:

1. Download paipu files from `paipuxmls/` or releases
2. Parse XML → `PaipuReplayer`
3. Replay every action
4. Compare final scores with XML `<AGARI>` / `<RYUUKYOKU>` result

This ensures the engine faithfully reproduces real game outcomes.

## Paipu Data Locations

| 来源 | 路径 | 说明 |
|------|------|------|
| CI 数据集 | `pymahjong/paipuxmls/mjlog_*.txt` | 预置的 Tenhou XML 文件 |
| Tenhou 下载 | `https://tenhou.net/mjlog/` | 需登录获取 |
| Releases | `github.com/Agony5757/mahjong/releases` | 预处理数据集 |

## Debug Mode

When debug mode is enabled, the game generates replayable code:

```python
import pymahjong as pm

env = pm.MahjongEnv()
env.reset(debug_mode=1)  # Enable debug mode

# ... play the game ...

# Get replay code
replay_code = env.t.get_debug_replay()
print(replay_code)
```

This outputs code that can be used to reproduce the exact game:

```python
Table table;
table.game_init_for_replay([...], [25000, 25000, 25000, 25000], 0, 0, 0, 0);
table.make_selection(0);
table.make_selection(1);
# ... etc
```

## Offline Dataset

Pre-processed datasets are available for machine learning:

```python
import scipy.io

data = scipy.io.loadmat("mahjong_data.mat")

# data["X"] - Executor observation (93×34)
# data["O"] - Oracle observation (18×34)
# data["A"] - Actions taken
# data["M"] - Valid action masks
# data["R"] - Rewards
# data["D"] - Done signals
```

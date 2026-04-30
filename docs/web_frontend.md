# Mahjong Web 前端文档

## 概述

Web 前端是基于 FastAPI + HTML5 Canvas 的四人日麻（立直麻将）对战平台，包含三个页面：

| 页面 | 路由 | 说明 |
|------|------|------|
| 人机对战 | `/` | 玩家（P0） vs 3个 AI 对手 |
| 4 AI 对战 | `/ai_battle` | 4个 AI 自动对战，可切换视角观战 |
| 牌谱复现 | `/replay` | 上传 Tenhou XML 牌谱，逐步回放 |

技术栈：**FastAPI** + **HTML5 Canvas** + **Vanilla JavaScript**，无外部框架依赖。

---

## 项目结构

```
web/
├── server.py              # FastAPI 主服务器（18个端点）
├── game_manager.py       # 游戏会话封装（MahjongEnvWrapper）
├── ai_player.py          # AI 玩家（随机 AI / 预训练模型）
├── paipu_parser.py       # Tenhou XML 牌谱解析
├── requirements.txt
└── static/
    ├── index.html         # 人机对战页面
    ├── ai_battle.html    # 4 AI 对战页面
    ├── replay.html       # 牌谱复现页面
    ├── css/
    │   └── style.css     # 暗色主题样式
    └── js/
        ├── renderer.js    # Canvas 麻将牌绘制引擎
        ├── game_core.js  # 人机对战状态机
        ├── ai_client.js  # 4 AI 对战客户端
        └── replay.js     # 牌谱复现客户端
```

---

## 核心模块说明

### server.py

FastAPI 应用，端口 8000。关键端点：

**游戏管理**
```
POST /api/game/new
  body: { "mode": "human_ai" | "4ai", "ai_model": null | "random" | "path/to/model.pth", "seed": null | int }
  return: { "session_id": "uuid", "mode": "human_ai", "state": {...} }

GET  /api/game/{session_id}/state?for_player=0
  return: MahjongEnvWrapper._build_state() 序列化结果

POST /api/game/{session_id}/action
  body: { "player_id": 0, "action_idx": 37 }
  return: { "ok": true, "state": {...} }

GET  /api/game/{session_id}/events
  return: SSE 流（ai_action | game_over | error 事件）

GET  /api/game/{session_id}/paipu
  return: 游戏记录 JSON（用于回放）
```

**牌谱复现**
```
POST /api/replay/load
  body: { "xml_content": "<mjlog>..." }
  return: { "ok": true, "paipu": {...} }

GET  /api/replay/builtin
  return: { "paipu_files": ["file1.txt", ...] }

GET  /api/replay/builtin/{filename}
  return: XML 文件内容
```

**SSE 推送机制**

每次 AI 动作执行后，服务器通过 `_broadcast()` 向所有订阅者推送：

```json
{ "type": "ai_action", "player": 2, "action": 37, "state": {...} }
{ "type": "game_over", "state": {...} }
{ "type": "error", "message": "..." }
```

客户端通过 `EventSource` 接收，无需轮询。

### game_manager.py

**MahjongEnvWrapper** — 封装 `pymahjong.env_pymahjong.MahjongEnv`：

| 方法 | 说明 |
|------|------|
| `step(player_id, action_idx)` | 执行动作（处理立直两步流程） |
| `get_valid_actions(player_id)` | 返回合法动作索引列表 |
| `get_state(for_pid)` | 玩家视角的完整状态序列化 |
| `get_random_action(player_id)` | 随机 AI 用 |
| `_build_state()` | 内部状态序列化 |

**立直两步流程实现**：

```
Stage 1: 玩家点击立直候选牌
  → server 返回 state { riichi_stage2: true }
  → 前端进入待确认状态

Stage 2: 玩家确认（action_idx=48）或取消（action_idx=52）
  → MahjongEnvWrapper._resolve_action() 执行完整流程
  → _proceed() 自动推进阶段
  → 返回新状态
```

**动作索引（Python 端 0-53）**：

| 索引 | 动作 |
|------|------|
| 0-36 | 普通舍牌（basetile 0-33，37-39 为赤宝牌） |
| 37-42 | 吃（含赤5变体） |
| 43-44 | 碰（含赤5变体） |
| 45 | 暗杠 |
| 46 | 大明杠 |
| 47 | 加杠 |
| 48 | 立直确认 |
| 49 | 荣和 |
| 50 | 自摸 |
| 51 | 摸牌 |
| 52 | 取消立直 |
| 53 | 跳过（响应阶段） |

### ai_player.py

```python
class RandomAI(BaseAIPlayer):
    def select_action(env_wrapper, player_id) -> int:
        valid = env_wrapper.get_valid_actions(player_id)
        return np.random.choice(valid)
```

可选加载 `pymahjong/models.py` 中的 VLOGMahjong 预训练模型（需 PyTorch）。

### renderer.js

纯 Canvas 绘制，无外部图片依赖。`window.MahjongRenderer` 导出：

```javascript
renderGame(ctx, W, H, state, opts)    // 人机对战渲染
renderReplay(ctx, W, H, state, opts)  // 牌谱复现渲染（4手可见）
drawTile(ctx, x, y, tileStr, isRed5, isHighlighted, isSelected)
drawDoraTile(ctx, x, y, tileStr, hidden)
drawRiverTile(ctx, x, y, tileData)
drawTileBack(ctx, x, y)  // 背面牌（蓝几何图案）
```

麻将牌颜色编码：万（蓝 `#1a5276`）、筒（红 `#922b21`）、索（绿 `#1e8449`）、字（深蓝 `#1a1a6e`）、赤5（红 `#e74c3c`）。

---

## 页面详解

### 人机对战页面（`/`）

流程：
1. 进入页面 → 弹出模式选择（随机 AI / 预训练模型）
2. 点击开始 → `POST /api/game/new` → 创建游戏
3. 玩家回合（P0）：点击手牌舍牌，或在响应阶段选择荣和/碰/杠/吃/跳过
4. AI 回合（P1-P3）：SSE 推送 AI 动作，Canvas 渲染结果
5. 立直两步：点击立直候选牌 → 弹出确认/取消按钮 → 确认则执行立直
6. 结算：弹出结算 Modal，显示胜负、得分、役种

**Canvas 点击逻辑**（`game_core.js:_onCanvasClick`）：
```
点击位置 → 判断是否在自己手牌区域
  → _selectTile(idx, tileData)
      → 若 pendingRiichi=true（第二步）→ submitAction(48)
      → 否则 _findDiscardAction() 找动作索引
          → 检查是否立直候选牌
              → 是：_submitRiichiStep1()（设置pending，提交第一步）
              → 否：submitAction(discardIdx)
```

### 4 AI 对战页面（`/ai_battle`）

流程：
1. 点击开始 → 4 AI 自动对战
2. 每步 SSE 推送 `ai_action`，Canvas 渲染最新状态
3. 玩家可切换跟随视角（只看某一家的牌）
4. 速度控制：慢（1500ms）/ 中（800ms）/ 快（300ms）
5. 结算 Modal 显示终局得分

### 牌谱复现页面（`/replay`）

数据流：
```
Tenhou XML 文件
  → POST /api/replay/load → paipu_data
  → POST /api/replay/steps → steps[]（每步状态快照）
  → ReplayClient 前端控制播放
```

内置牌谱来自 `pymahjong/paipuxmls/` 目录。

---

## 测试方法

### 前置依赖

```bash
# 安装后端 Python 依赖
cd /home/agony/projects/mahjong-dev
pip install -r web/requirements.txt

# 或使用 uv
uv venv && source .venv/bin/activate
uv pip install -r web/requirements.txt
```

`requirements.txt` 内容：
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
numpy>=1.24.0
scipy>=1.10.0
torch>=2.0.0          # 可选，预训练模型用
sse-starlette>=1.8.0
```

### 启动服务器

```bash
cd /home/agony/projects/mahjong-dev/web
uvicorn server:app --reload --port 8000
```

或（非 reload 模式，性能更好）：
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 手动 API 测试

**1. 新建人机对战游戏**
```bash
curl -s -X POST http://localhost:8000/api/game/new \
  -H "Content-Type: application/json" \
  -d '{"mode": "human_ai", "ai_model": "random", "seed": 42}' \
  | python3 -m json.tool
```

返回：
```json
{
  "session_id": "a1b2c3d4-...",
  "mode": "human_ai",
  "state": {
    "phase": 0,
    "turn": 0,
    "players": [...],
    "dora": [],
    "valid_actions": [0, 1, 2, ...],
    "valid_actions_mask": [...]
  }
}
```

**2. 查询游戏状态**
```bash
curl -s "http://localhost:8000/api/game/{session_id}/state?for_player=0" \
  | python3 -m json.tool | head -50
```

**3. 提交动作（舍牌）**
```bash
curl -s -X POST "http://localhost:8000/api/game/{session_id}/action" \
  -H "Content-Type: application/json" \
  -d '{"player_id": 0, "action_idx": 0}' \
  | python3 -m json.tool
```

**4. 查看当前玩家**
```bash
# phase < 4 为自摸阶段，phase >= 4 && phase < 16 为响应阶段
# turn 字段表示当前需要动作的玩家 ID
curl -s "http://localhost:8000/api/game/{session_id}/state?for_player=0" \
  | python3 -c "import sys,json; s=json.load(sys.stdin); print(f'turn={s[\"turn\"]} phase={s[\"phase\"]}')"
```

**5. 测试 SSE 推送**（另开一个终端）
```bash
# 终端 1：先新建游戏
curl -s -X POST http://localhost:8000/api/game/new \
  -H "Content-Type: application/json" \
  -d '{"mode": "4ai"}' | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['session_id'])"

# 终端 2：订阅 SSE（服务器需要先有游戏 session）
SESSION_ID="上面输出的id"
curl -s -N "http://localhost:8000/api/game/${SESSION_ID}/events" \
  --max-time 30
# 应看到 ai_action 和 game_over 事件
```

**6. 测试牌谱解析**
```bash
# 上传内置牌谱文件
curl -s -X GET http://localhost:8000/api/replay/builtin \
  | python3 -m json.tool

# 获取内置牌谱
curl -s "http://localhost:8000/api/replay/builtin/0000.txt" | head -5

# 解析 Tenhou XML（以内置牌谱为例）
curl -s -X POST http://localhost:8000/api/replay/load \
  -H "Content-Type: application/json" \
  -d "{\"xml_content\": $(curl -s 'http://localhost:8000/api/replay/builtin/0000.txt' | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok:', d.get('ok'), 'type:', d.get('paipu',{}).get('type','?'))"
```

**7. 健康检查**
```bash
curl -s http://localhost:8000/api/health
# {"status": "ok"}
```

### 浏览器端测试

1. 启动服务器后，浏览器访问：
   - `http://localhost:8000/` — 人机对战
   - `http://localhost:8000/ai_battle` — 4 AI 对战
   - `http://localhost:8000/replay` — 牌谱复现

2. **人机对战测试路线**（从开牌到和牌/流局）：
   - 选择随机 AI → 开始游戏
   - 玩家回合：点击手牌舍牌（观察正确高亮、响应按钮）
   - AI 出牌：观察 SSE 更新、Canvas 重绘
   - 响应阶段：荣和/碰/杠/吃按钮是否正确出现
   - 立直：点击立直候选牌 → 确认/取消按钮弹出 → 确认
   - 结算：Modal 弹窗是否显示正确得分和役种

3. **4 AI 对战测试路线**：
   - 开始游戏 → 观察 AI 自动出牌
   - 切换跟随视角 → 验证手牌隐藏逻辑
   - 调整速度 → 验证播放节奏变化
   - 等待流局/和牌 → 验证结算 Modal

4. **牌谱复现测试路线**：
   - 点击"加载示例" → 验证内置牌谱加载
   - 上传 Tenhou XML → 验证解析
   - 播放/暂停 → 步进/步退 → 验证状态正确更新
   - 进度条拖拽 → 验证跳转功能

### 单元测试（Python）

```bash
# 基础功能测试
cd /home/agony/projects/mahjong-dev
python3 -c "
from web.game_manager import MahjongEnvWrapper, GameManager, GameMode
from web.ai_player import RandomAI

# 测试 GameManager
gm = GameManager()
s = gm.create_session(GameMode.HUMAN_AI, seed=42)
print('session created:', s.session_id)

# 测试合法动作
valid = s.env.get_valid_actions(0)
print('valid actions count:', len(valid))

# 测试随机 AI
ai = RandomAI()
action = ai.select_action(s.env, 1)
print('AI action:', action)

# 测试 step
state = s.step(0, valid[0])
print('phase after step:', state['phase'])
"

# 测试牌谱解析
python3 -c "
from web.paipu_parser import parse_tenhou_xml

xml = open('pymahjong/paipuxmls/0000.txt').read()
paipu = parse_tenhou_xml(xml)
print('type:', paipu.get('type', '?'))
print('seed:', paipu.get('seed', '?'))
print('ok')
"
```

### 回归测试（原有 C++ 引擎）

```bash
cd /home/agony/projects/mahjong-dev
python3 -c "import pymahjong as pm; pm.test()"
```

此测试验证 `MahjongEnv`（游戏引擎）核心逻辑未被影响。

### 性能基准

```bash
# 模拟 1000 步 AI 决策
python3 -c "
import time, numpy as np
from web.game_manager import GameManager, GameMode
from web.ai_player import RandomAI

gm = GameManager()
s = gm.create_session(GameMode.HUMAN_AI, seed=0)
ai = RandomAI()

start = time.time()
steps = 0
while not s.env.is_over() and steps < 1000:
    curr = s.env.get_curr_player()
    action = ai.select_action(s.env, curr)
    s.step(curr, action)
    steps += 1

elapsed = time.time() - start
print(f'{steps} steps in {elapsed:.3f}s = {steps/elapsed:.1f} steps/s')
"
```

---

## 常见问题排查

| 症状 | 可能原因 | 解决方法 |
|------|----------|----------|
| 舍牌后 AI 不动 | `pendingRiichi` 状态未清除 | 检查 `_selectTile` 逻辑，`submitAction` 后是否正确重置 |
| 响应按钮（荣和/碰）不出现 | `valid_actions_mask` 未正确更新 | 检查 SSE 是否正确推送了新状态 |
| 立直两步流程卡住 | `_riichi_stage2` 未在服务端正确设置 | 打印 `state['riichi_stage2']` 确认 |
| 牌谱复现空白 | `gameSteps` 为空 | 检查 `/api/replay/steps` 返回的 `steps` 数组 |
| SSE 不推送 | 跨域问题或连接断开 | 浏览器控制台检查 Network 面板，`onerror` 是否触发 |
| 编译报错（CMake） | `pybind11` 未找到 | 设置 `cmake -Dpybind11_DIR=/path/to/share/cmake/pybind11` |

---

## 开发提示

### 添加新动作类型

1. **Python 后端**：`game_manager.py` 的 `ACTION_TYPES` 元组添加映射
2. **前端**：在 `renderer.js` 添加牌面渲染，在 `game_core.js` 添加点击处理
3. **测试**：手动 API 测试验证动作索引正确性

### 添加新役种

役种判定在 `Mahjong/YakuDetector.cpp`（C++）或 `pymahjong/models.py`（Python）。前端显示役名在 `game_core.js:_showResultModal()` 的 `typeNames` 映射中。

### 调试 SSE 连接

浏览器控制台：
```javascript
const es = new EventSource('/api/game/{id}/events');
es.addEventListener('message', e => console.log('SSE:', JSON.parse(e.data)));
es.onerror = e => console.error('SSE error:', e);
```

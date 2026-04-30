术语对照表 / Terminology Glossary
=================================

本文件列出 pymahjong 代码中所有关键术语的中文、日文（罗马字）、英文对照，
以及对应的 Python/C++ 变量名。

## 一、麻将通用术语 / General Mahjong Terms

.. list-table::
   :header-rows: 1
   :widths: 30 20 25 25

   * - 中文
     - 日文（罗马字 / 假名）
     - English
     - 变量名
   * - 立直
     - Riichi（リーチ）
     - Riichi (one-way tanyao)
     - ``riichi``, ``Riichi``
   * - 副露（鸣牌）
     - Fuuro（鳴き / 鸣き）
     - Called tiles (chi/pon/kan)
     - ``fuuro``, ``get_fuuros()``
   * - 吃（顺子）
     - Chii（チー）
     - Chow (sequential meld)
     - ``Chi``
   * - 碰（刻子）
     - Pon（ポン）
     - Pong (triplet meld)
     - ``Pon``
   * - 杠（大明杠）
     - Daimin-kan（大明槓）
     - Open kan (added triplet)
     - ``Kan``
   * - 暗杠
     - Ankan（暗槓）
     - Concealed kan
     - ``AnKan``
   * - 加杠
     - Kakan（加槓）
     - Added kan (kan on own triplet)
     - ``KaKan``
   * - 抢杠
     - Chan-kan（槍槓）
     - Robbing a kan
     - ``ChanKan``
   * - 抢暗杠
     - Chan-an-kan（槍暗槓）
     - Robbing a concealed kan
     - ``ChanAnKan``
   * - 荣和（荣）
     - Ron（ロン）
     - Win by discard
     - ``Ron``
   * - 自摸
     - Tsumo（ツモ）
     - Self-draw win
     - ``Tsumo``
   * - 舍牌（丢牌）
     - Sutehai（捨て牌）
     - Discard
     - ``Discard``
   * - 手切
     - Temazari（手直し）
     - Hand tile discard (vs after draw)
     - ``fromhand = true``
   * - 摸切
     - Sumazari（摸了）
     - After-draw discard
     - ``fromhand = false``
   * - 宝牌
     - Dora（ドラ）
     - Bonus indicator tile
     - ``dora_indicator``, ``get_dora()``
   * - 里宝牌
     - Uradora（裏ドラ）
     - Hidden dora (revealed after riichi)
     - ``uradora_indicator``, ``get_ura_dora()``
   * - 食断
     - Shiimantan（食いタン）
     - Tanyao with called tiles
     - (yaku flag)
   * - 一发
     - Ippatsu（一発）
     - Win within one draw after riichi
     - ``ippatsu``
   * - 两立直
     - Double Riichi（ダブルリーチ）
     - Riichi on first discard round
     - ``double_riichi``
   * - 听牌（听）
     - Tenpai（テンパイ）
     - One tile away from winning
     - ``is_tenpai()``
   * - 和了（和）
     - Agari（上がり）
     - Winning hand
     - (result)
   * - 振听
     - Furiten（振りテbian）
     - Furiten (cannot ron on tile in own river)
     - ``furiten_river``, ``furiten_round``, ``furiten_riichi``
   * - 荒牌（牌山）
     - Yama（山）
     - Wall / draw pile
     - ``yama``
   * - 岭上牌
     - Rinshan（嶺上牌）
     - Dead wall draw
     - (drawn after kan)
   * - 本场
     - Honba（ほんば）
     - Repeat counter sticks
     - ``honba``
   * - 立直棒（供托）
     - Kyoutaku（供給）
     - Riichi deposit sticks
     - ``kyoutaku`` (C++), ``riichibo`` (binding)
   * - 亲家（庄家）
     - Oya（親）
     - Parent / dealer round holder
     - ``oya``
   * - 子家
     - Ko（子）
     - Non-dealer
     - (opposite of ``oya``)
   * - 连庄
     - Renchan（連荘）
     - Dealer wins again (honba continues)
     - (honba increments)
   * - 场风
     - Bakaze（場風）
     - Round wind
     - ``game_wind``
   * - 自风
     - Tonkaze / Ji-kaze（自風）
     - Player's seat wind
     - ``wind`` (Player)
   * - 流局
     - Ryuu-kyoku（流局）
     - Draw / abortive draw
     - ``Ryukyouku_*``
   * - 九种九牌
     - Kyuushu-kyuuhai（九種九牌）
     - Nine different terminals/honors (abort right)
     - ``Kyushukyuhai``
   * - 四风子连打
     - Suufuuda-renda（捨て牌）
     - Four riichi draws (abortive)
     - ``Ryukyouku_Interval_4Riichi``
   * - 三家和
     - Sankajou（三家和）
     - Triple ron win
     - ``generate_result_3ron()``
   * - 役（胡牌型）
     - Yaku（役）
     - Winning hand yaku (scoring combination)
     - ``Yaku`` (enum), ``yaku_detected``
   * - 符
     - Fu（フ）
     - Base points (fu)
     - ``FuCalculator``
   * - 翻
     - Han（ハン）
     - Yaku multiplier count
     - ``han``
   * - 满（级别）
     - Mangan / Haneman / Baiman
     - Score ceiling levels
     - ``ScoreCounter``
   * - 断幺
     - Tanyao（タンヤオ）
     - All simples (no terminals/honors)
     - (yaku enum)
   * - 混一色
     - Honiisou（混一色）
     - Mixed one suit
     - (yaku)
   * - 清一色
     - Chiniisou（清一色）
     - Pure one suit
     - (yaku)

----

## 二、牌名 / Tile Names

.. list-table::
   :header-rows: 1
   :widths: 15 15 15 15 40

   * - 中文
     - 日文
     - 英文
     - 代码后缀
     - Tile ID (BaseTile)
   * - 万子
     - Man（マン）
     - Characters
     - ``m``
     - 0–8
   * - 筒子
     - Pin（ピン）
     - Dots
     - ``p``
     - 9–17
   * - 索子
     - Sou（ソー）
     - Bamboo
     - ``s``
     - 18–26
   * - 字牌·东
     - Ton / East（東）
     - East wind
     - ``z`` / ``1z``
     - 27
   * - 字牌·南
     - Nan / South（南）
     - South wind
     - ``2z``
     - 28
   * - 字牌·西
     - Xiaa / West（西）
     - West wind
     - ``3z``
     - 29
   * - 字牌·北
     - Pei / North（北）
     - North wind
     - ``4z``
     - 30
   * - 白
     - Haku（白）
     - White dragon
     - ``5z``
     - 31
   * - 发
     - Hatsu（發）
     - Green dragon
     - ``6z``
     - 32
   * - 中
     - Chun（中）
     - Red dragon
     - ``7z``
     - 33
   * - 赤5万
     - Aka-5m（赤5マン）
     - Red five characters
     - (red_dora flag)
     - tile id 4
   * - 赤5筒
     - Aka-5p（赤5ピン）
     - Red five dots
     - (red_dora flag)
     - tile id 13
   * - 赤5索
     - Aka-5s（赤5ソー）
     - Red five bamboo
     - (red_dora flag)
     - tile id 22

----

## 三、Table 类状态变量 / ``Table`` State Variables

.. list-table::
   :header-rows: 1
   :widths: 20 30 25 25

   * - 变量名
     - 中文
     - English
     - 日文
   * - ``turn``
     - 当前回合玩家
     - Current player ID (whose turn)
     - ターゲットのプレイヤー
   * - ``phase`` / ``PhaseEnum``
     - 当前游戏阶段
     - Phase state machine state
     - フェーズ
   * - ``last_action``
     - 上一次动作类型
     - Last BaseAction performed
     - 最後のアクション
   * - ``oya``
     - 庄家玩家ID
     - Parent/dealer player ID
     - 親プレイヤー
   * - ``honba``
     - 本场数
     - Repeat (honba) counter
     - 本場
   * - ``kyoutaku`` (C++) / ``riichibo`` (binding)
     - 立直棒数
     - Riichi deposit sticks on table
     - 供給（リーチ棒）
   * - ``game_wind``
     - 场风
     - Round wind (East/South/West/North)
     - 場風
   * - ``yama``
     - 牌山（剩余摸牌堆）
     - Wall (remaining draw pile, vector of Tile*)
     - 山（やま）
   * - ``river_counter``
     - 河里牌计数
     - Number of tiles in all rivers combined
     - 河（こう）の牌数
   * - ``dora_indicator``
     - 宝牌指示牌列表
     - Opened dora indicator tiles
     - ドラ表示牌
   * - ``uradora_indicator``
     - 里宝牌指示牌列表
     - Ura-dora indicator tiles
     - 裏ドラ表示牌
   * - ``n_active_dora``
     - 已翻开宝牌数
     - Number of active dora revealed
     - 成立ドラ数
   * - ``players``
     - 四个玩家数组
     - Array of 4 Player objects
     - プレイヤー4人
   * - ``gamelog``
     - 游戏日志
     - Game event log (for replay/debug)
     - ゲームログ
   * - ``result``
     - 游戏结果
     - Game result (type + score breakdown)
     - 結果
   * - ``write_log_mode``
     - 调试日志模式
     - Debug log mode (0=off, 1=buffer, 2=stdout)
     - デバッグモード
   * - ``seed``
     - 随机种子
     - Random seed for reproducibility
     - シード値
   * - ``selection``
     - 当前选择的动作索引
     - Selected action index during phase transition
     - 選択インデックス

----

## 四、Player 类状态变量 / ``Player`` State Variables

.. list-table::
   :header-rows: 1
   :widths: 20 30 25 25

   * - 变量名
     - 中文
     - English
     - 日文
   * - ``hand``
     - 玩家手牌（Tile* 数组）
     - Player's closed hand (array of Tile*)
     - 手牌（てはい）
   * - ``menzen``
     - 是否门清（无副露）
     - Fully concealed (no called tiles)
     - 門前（めんぜん）
   * - ``score``
     - 当前分数
     - Current score in points
     - 点数（点）
   * - ``riichi``
     - 是否已立直
     - Has declared riichi
     - リーチ済み
   * - ``oya``
     - 是否为庄家
     - Is this player the parent/dealer
     - 親かどうか
   * - ``wind``
     - 自风
     - Player's seat wind
     - 自風（じふう）
   * - ``double_riichi``
     - 是否两立直
     - Declared riichi on first discard round
     - ダブルリーチ
   * - ``ippatsu``
     - 一发有效
     - Ippatsu condition still valid
     - 一発
   * - ``first_round``
     - 是否在第一巡
     - Is this the first discard round
     - 第一巡
   * - ``furiten_river``
     - 振听（舍牌振听）
     - Furiten due to own discard
     - 振りテbian（捨て牌）
   * - ``furiten_round``
     - 振听（舍牌振听，同巡内）
     - Furiten within current round
     - 同巡内振りテbian
   * - ``furiten_riichi``
     - 振听（立直振听）
     - Furiten from own riichi discard
     - リーチ振りテbian

----

## 五、PhaseEnum 阶段枚举 / Game Phase States

.. list-table::
   :header-rows: 1
   :widths: 15 25 30 30

   * - 枚举值
     - 中文
     - English
     - 日文
   * - ``P1_ACTION`` (0)
     - 玩家0自摸阶段
     - Player 0 self-action phase
     - プレイヤー0のツモフェーズ
   * - ``P2_ACTION`` (1)
     - 玩家1自摸阶段
     - Player 1 self-action phase
     - プレイヤー1のツモフェーズ
   * - ``P3_ACTION`` (2)
     - 玩家2自摸阶段
     - Player 2 self-action phase
     - プレイヤー2のツモフェーズ
   * - ``P4_ACTION`` (3)
     - 玩家3自摸阶段
     - Player 3 self-action phase
     - プレイヤー3のツモフェーズ
   * - ``P1_RESPONSE`` (4)
     - 玩家0响应阶段
     - Player 0 response phase
     - プレイヤー0の応答フェーズ
   * - ``P2_RESPONSE`` (5)
     - 玩家1响应阶段
     - Player 1 response phase
     - プレイヤー1の応答フェーズ
   * - ``P3_RESPONSE`` (6)
     - 玩家2响应阶段
     - Player 2 response phase
     - プレイヤー2の応答フェーズ
   * - ``P4_RESPONSE`` (7)
     - 玩家3响应阶段
     - Player 3 response phase
     - プレイヤー3の応答フェーズ
   * - ``P*_CHANKAN_RESPONSE`` (8-11)
     - 抢杠响应阶段
     - Robbing-a-kan response phases
     - 槍槓の応答フェーズ
   * - ``P*_CHANANKAN_RESPONSE`` (12-15)
     - 抢暗杠响应阶段
     - Robbing-a-concealed-kan response phases
     - 槍暗槓の応答フェーズ
   * - ``GAME_OVER`` (16)
     - 游戏结束
     - Game is over
     - ゲームオーバー
   * - ``UNINITIALIZED`` (17)
     - 未初始化
     - Not yet initialized
     - 未初期化

----

## 六、环境层变量 / Python Environment Variables

.. list-table::
   :header-rows: 1
   :widths: 20 25 25 30

   * - 变量名 / 类
     - 中文
     - English
     - 说明
   * - ``MahjongEnv``
     - 多智能体环境
     - Multi-agent environment
     - 4玩家对战环境
   * - ``SingleAgentMahjongEnv``
     - 单智能体环境
     - Single-agent environment
     - Gymnasium兼容，1人+3AI
   * - ``TableEncoder`` / ``PassiveTableEncoder``
     - 观察编码器
     - Observation encoder
     - 状态→numpy数组编码
   * - ``PaipuReplayer``
     - 牌谱回放器
     - Paipu replayer
     - 重放天凤XML牌谱
   * - ``TenhouShuffle``
     - 天凤洗牌算法
     - Tenhou shuffle algorithm
     - MT19937+SHA512
   * - ``VLOGMahjong``
     - 预训练VLOG模型
     - VLOG Mahjong RL model
     - 论文 ICLR 2022 模型

----

## 七、观察空间编码 / Observation Encoding

.. list-table::
   :header-rows: 1
   :widths: 20 25 20 35

   * - 术语
     - English
     - 形状
     - 说明
   * - 执行器观察
     - Executor observation
     - ``(93, 34)``
     - 当前玩家可见信息
   * - 神谕观察
     - Oracle observation
     - ``(18, 34)``
     - 对手手牌（隐藏信息）
   * - 完整观察
     - Full observation
     - ``(111, 34)``
     - 执行器 + 神谕拼接
   * - 牌山观察
     - Yama observation
     - 包含在观察矩阵中
     - 剩余牌数信息

----

## 八、Action 动作索引 / Action Index Mapping

.. list-table::
   :header-rows: 1
   :widths: 15 25 30 30

   * - 索引
     - 中文
     - English
     - 说明
   * - 0–33
     - 普通舍牌
     - Normal discard (tile 0–33)
     - Basetile 0-9m, 9-17p, 18-26s, 27-33z
   * - 34–36
     - 赤宝牌舍牌
     - Red dora discard (5m/5p/5s)
     - 37-39 in basetile space
   * - 37–42
     - 吃（含赤5变体）
     - Chi calls (left/middle/right × with/without red)
     - 鸣牌吃
   * - 43–44
     - 碰（含赤5变体）
     - Pon calls (with/without red 5)
     - 鸣牌碰
   * - 45
     - 暗杠
     - Ankan (concealed kan)
     - 手牌4张相同
   * - 46
     - 大明杠
     - Daimin-kan (open kan)
     - 碰后加杠
   * - 47
     - 加杠
     - Kakan (added kan)
     - 手牌已有3张+第4张
   * - 48
     - 立直宣言
     - Riichi declaration
     - 第一步：选舍牌
   * - 49
     - 荣和
     - Ron win
     - 对手舍牌和牌
   * - 50
     - 自摸
     - Tsumo win
     - 摸牌后和牌
   * - 51
     - 摸牌
     - Draw / pass in self-action
     - 通常自动执行
   * - 52
     - 立直确认/取消
     - Riichi confirm / cancel
     - 第二步决策
   * - 53
     - 跳过（响应阶段）
     - Pass (response phase)
     - 鸣牌/荣和跳过

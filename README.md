# 日本麻将

## Project Status
雀魂规则：完成
天凤规则：未完成
测试：未彻底进行

## 综述

本项目包含一个用C++实现的日本麻将游戏。并且提供接口，以便：
	
	实现不同种类的AI Agent
	人类游玩

## 基本架构

Table类：核心数据类，包含整个游戏中涉及到的所有变量的控制

Player类：装载在Table内，用于储存玩家信息

Tile.h：通过BaseTile标记牌类，通过Tile标记一个牌的信息

Rule.h：通过从Table中获得的和Tile，Player……相关的信息，来对和牌，吃，碰，杠，允许打的牌等进行判断

GameLog.h：提供一个通用的游戏记录。它可以记录玩家可以看到的信息，或者游戏的全部记录。

TableStatus.h：提供给Agent的数据类。通过GameLog解析出想要的信息。

Agent类：关于进行实际游戏抉择的抽象基类。它通过TableStatus，以及提供的可用Action，最终提供一个选择。

MahjongAlgorithm文件夹：一个第三方的，可以将牌进行3n+2拆解的库。

## 算法

### Table::GameProcess

这个函数里面涉及到一局内游戏进程控制。

第一步：初始化牌桌

	牌山
	每个人的初始牌13张牌
	初始化场风，门风
	初始化每个人的立直状态
	将Agent注册进来
	初始化庄家的编号
	初始化turn变量=庄家

	初始化第一巡first_round[4] = {true}
	
	杠后after_kan = false
	吃碰after_chipon = false
	
	每个人的振听状态[4] = {false}

第二步：主循环

	0. 循环的起点是player[turn]具有3n+2张牌的情况。
	1. 对于player[turn]，if (after_kan) 摸岭上牌，更新牌山；否则普通摸牌。（记录）。流局：四杠流局判定；荒牌流局判定；四风连打流局判定；四立直流局判定；在摸牌前进行。
	2. 如果是非立直状态 valid_action = GetValidAction()
	   如果是立直状态   valid_action = GetRiichiSelfAction()
	3. 通过Player[turn].gameLog，构造TableStatus对象table_status
	4. 调用agent[turn].get_self_action，传入valid_action, table_status，获得decision(整数类型)
	5. Selection = valid_action[decision].action
	switch (Selection)
	case 打牌:
		对于i = 0,1,2,3 except turn
		如果是非立直状态	response_action = GetResponseAction(i)
		如果是立直状态   response_action = GetRiichiResponse(i)
		将每个response_action传递到对应的agent那里，通过Player[i].gameLog构造TableStatus对象
		获得每个player的Action

		动作优先级是pass < chi < pon < kan < ron
		switch (final_selection)
		case pass:
			player[turn]的一发状态 = false，第一巡状态 = false
			将牌从手牌移动到牌河			
			turn++;  turn%=4; 
			after_chipon = false;
			if (after_kan) 翻一张岭上牌 after_kan = false;
			回到循环起点
		case chi:
			所有人的一发状态 = false，第一巡状态 = false
			player[response_player]的对应牌和打出牌组成副露组，移动到player[response_player].fulus
			turn = response_player
			after_chipon = true;
			if (after_kan) 翻一张岭上牌 after_kan = false;
			回到循环起点
		case pon:
			所有人的一发状态 = false，第一巡状态 = false
			player[response_player]的对应牌和打出牌组成副露组，移动到player[response_player].fulus
			turn = response_player
			after_chipon = true;			
			if (after_kan) 翻一张岭上牌 after_kan = false;
			回到循环起点
		case kan:
			所有人的一发状态 = false，第一巡状态 = false
			player[response_player]的对应牌和打出牌组成副露组，移动到player[response_player].fulus
			turn = response_player
			after_chipon = false;
			if (after_kan) 翻一张岭上牌 after_kan = false;
			回到循环起点

		case ron:
			此时，返回的response_player.size()>=1
			逐个进行游戏结算

	case 加杠：
		对于i = 0,1,2,3 except turn
		response_action = Get抢杠(i)
		将每个response_action传递到对应的agent那里，通过Plyaer[i].gameLog构造TableStatus对象
		获得每个player的Action

		response_action.action只有pass和抢杠
		case pass:
			after_kan = true
			将牌移动到fulus对应的那一项中
			所有人的一发状态 = false，第一巡状态 = false
			after_chipon = false

	case 暗杠：
		对于i = 0,1,2,3 except turn
		response_action = Get抢暗杠(i)
		将每个response_action传递到对应的agent那里，通过Plyaer[i].gameLog构造TableStatus对象
		获得每个player的Action

		response_action.action只有pass和抢杠
		case pass:
			after_kan = true
			将牌移动到fulus对应的那一项中
			所有人的一发状态 = false，第一巡状态 = false
			after_chipon = false

	case 立直:
		和打牌的状态一样。除了ron的情况，在回到循环起点之前，执行:player[turn]的立直状态=true。扣1000点。

	case 自摸:
		进行游戏结算

### GetValidAction

	1. 对于每个牌，判断after_chipon && 能加杠 = 添加加杠
	2. 对于每种牌，判断after_chipon && 能暗杠 = 添加暗杠
	3. 对于每个牌，(after_chipon==true && 非食替) || (after_chipon == false) = 添加打牌
	4. 对于整个手牌，判断是否是 = 添加自摸
	5. 对于整个手牌，判断是否是国士无双胡牌 = 添加自摸
	6. （判断立直）fulus中不存在除了暗杠之外的其他类型 && for (tile in 手牌) 手牌-tile == 普通听牌型 || 国士无双听牌型 ||  = 添加立直
	7. 如果第一巡 = True && 普通胡牌型 = 添加自摸
	8. 判断手牌存在某种役（包括七对和国士无双） = 添加自摸

### GetRiichiAction

	1. 判断手牌+新牌是否为和牌型（包括七对和国士无双）= 添加自摸
	2. 判断能暗杠 = 添加暗杠
	3. 添加打右手第一张

### GetResponseAction
	（注意到不存在人和，所以第一巡状态不影响response)
	1. not振听 && 判断手牌+新牌 == 普通胡牌型 && 存在某种役（包括七对和国士无双） = 添加荣和
	2. 判断手牌中是否能碰 = 添加碰
	3. 判断手牌中是否能杠 = 添加杠
	4. 判断turn和自己的关系是否为上家 && 能吃 = 添加吃
	5. 添加pass

### GetRiichiResponse
	1. not振听 && 判断手牌+新牌是否为普通和牌型 = 添加荣和
	2. 添加pass

### Get抢杠
	1. not振听 && 判断手牌+新牌 == 和牌型 = 添加荣和
	2. 添加pass

### Get抢暗杠
	1. not振听 && 判断手牌+新牌 == 国士无双 = 添加荣和
	2. 添加pass

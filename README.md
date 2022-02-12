# 日本麻将

## 综述

本项目包含一个用C++实现的日本麻将游戏，部分基于雀魂计分规则。

提供C++与Python接口，以便：	
	实现不同种类的AI Agent
	人类游玩（并不

## Performance

C++环境下：
- 运行内存 约800KB
- 单局时间 约131ms（658.594s with 5000 plays, avg. 131.7ms per play)

测试方法：
- 基于main.cpp中test_passive_table_auto，运行5000次，取运行时间平均值
- 其中每个动作都是由std::uniform_distribution进行随机选择
	
关于内存：
- 本项目中主要使用stl容器，没有使用到任何new/delete运算符，因此不会发生内存泄露问题。


## Example

	import numpy as np
	import pymahjong as mp

	for n in range(1000):
		t = mp.Table()
		t.game_init()
		for m in range(5000):        
			if t.get_phase() < 4:
				aval_actions = t.get_self_actions()
				a = np.random.randint(len(aval_actions))
				if aval_actions[a].action == mp.Action.Tsumo:
					print(aval_actions[a].action)
					for i in range(len(aval_actions[a].correspond_tiles)):
						print(aval_actions[a].correspond_tiles[i].tile)
				t.make_selection(a)
			else:
				aval_actions = t.get_response_actions()
				a = np.random.randint(len(aval_actions))
            
				if aval_actions[a].action == mp.Action.Ron:
					print(aval_actions[a].action)
					for i in range(len(aval_actions[a].correspond_tiles)):
						print(aval_actions[a].correspond_tiles[i].tile)
				t.make_selection(a)            
        
			if t.get_phase() == 16:  
				print(t.get_result().result_type)
				break
        
## Table通用接口

### Table::init_game_from_metadata

参数类型:
unordered_map: string, string 表示元数据

metadata现在支持的Key为：
"yama"： "1z1z.... 牌山初始化(默认随机开始)
"oya"： "0"/"1"/"2"/"3" 亲家，默认为"0"
"wind"： 东风局/南风局/西风局分别为"east","north","south"，默认为"east"
"deal"： "from_0"/"from_oya" 从谁开始发牌（从0号玩家/从庄家开始发牌），默认为"from_0"

### Table::get_info 获取牌桌对象

可以进一步通过访问成员来对数据进行获取，包括:
	
	(pybind11封装的接口形式下)
	.def_readonly("dora_spec", &Table::dora_spec)
	.def_readonly("DORA", &Table::宝牌指示牌)
	.def_readonly("URA_DORA", &Table::里宝牌指示牌)
	.def_readonly("YAMA", &Table::牌山)
	.def_readonly("players", &Table::players)
	.def_readonly("turn", &Table::turn)
	.def_readonly("last_action", &Table::last_action)
	.def_readonly("game_wind", &Table::场风)
	.def_readonly("last_action", &Table::last_action)
	.def_readonly("oya", &Table::庄家)
	.def_readonly("honba", &Table::n本场)
	.def_readonly("riichibo", &Table::n立直棒)


### Table::get_result 获取游戏结果

仅在从get_phase/get_phase_mt中获取到GAME_OVER/GAME_OVER_MT值之后，可以获取结果

返回类型是Result类型，参见Result部分的介绍

## Table单线程版本

### Table::get_phase 获取阶段

0,1,2,3分别为每个玩家的主动阶段。
4,5,6,7为回复阶段（鸣牌/pass）。
8,9,10,11为抢杠。
12,13,14,15为抢暗杠。
16为GameOver

### Table::get_self_action/get_response_action 获取允许执行的动作

数据类型是SelfAction和ResponseAction的列表。参见这两个类的介绍。

### Table::make_selection 进行选择

参数类型为int，表示在允许执行的动作的列表中的第几个。

## Table多线程版本

### Table::get_phase_mt 获取阶段

0,1,2,3分别为每个玩家的主动阶段。
4为回复阶段
5为GameOver

### Table::get_self_action_mt/get_response_action_mt 获取允许执行的动作

参数为int，表示第几号玩家。

数据类型是SelfAction和ResponseAction的列表。参见这两个类的介绍。

如果返回空列表，表示还没有轮到你做出选择。这个结果和should_i_make_selection_mt是一致的。

### Table::should_i_make_selection_mt

参数为int，表示第几号玩家。

返回bool，表示你是否可以开始执行动作了。

### Table::make_selection_mt 进行选择

参数1：int，表示第几号玩家
参数2：int，表示在允许执行的动作的列表中的第几个。

## BaseTile枚举	

（参见MahjongPy/MahjongPy.cpp）

## Fulu类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("type", &Fulu::type)
	.def_readonly("tiles", &Fulu::tiles)
	.def_readonly("take", &Fulu::take)	

## Tile类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("tile", &Tile::tile)
	.def_readonly("red_dora", &Tile::red_dora)

## River类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("river", &River::river)

## SelfAction类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("action", &ResponseAction::action)
	.def_readonly("correspond_tiles", &ResponseAction::correspond_tiles)

## ResponseAction类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("action", &ResponseAction::action)
	.def_readonly("correspond_tiles", &ResponseAction::correspond_tiles)

## Player类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("double_riichi", &Player::double_riichi)
	.def_readonly("riichi", &Player::riichi)
	.def_readonly("menchin", &Player::门清)
	.def_readonly("wind", &Player::wind)
	.def_readonly("oya", &Player::亲家)
	.def_readonly("furiten", &Player::振听)
	.def_readonly("riichi_furiten", &Player::立直振听)
	.def_readonly("score", &Player::score)
	.def_readonly("hand", &Player::hand)
	.def_readonly("fulus", &Player::副露s)
	.def_readonly("river", &Player::river)
	.def_readonly("ippatsu", &Player::一发)
	.def_readonly("first_round", &Player::first_round)

## Yaku枚举

（参见MahjongPy/MahjongPy.cpp）

## ResultType枚举

	(pybind11封装的接口形式下)
	.value("RonAgari", ResultType::荣和终局)
	.value("TsumoAgari", ResultType::自摸终局)
	.value("IntervalRyuuKyoku", ResultType::中途流局)
	.value("NoTileRyuuKyoku", ResultType::荒牌流局)
	.value("RyuuKyokuMangan", ResultType::流局满贯)

## Result类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("result_type", &Result::result_type)
	.def_readonly("results", &Result::results)
	.def_readonly("score", &Result::score)

## CounterResult类型

包含一系列可以访问的属性

	(pybind11封装的接口形式下)
	.def_readonly("yakus", &CounterResult::yakus)
	.def_readonly("fan", &CounterResult::fan)
	.def_readonly("fu", &CounterResult::fu)
	.def_readonly("score1", &CounterResult::score1)
	.def_readonly("score2", &CounterResult::score2)

## 全局函数

### yakus_to_string 将役打印出来

参数:Yaku的list
返回:GBK编码的bytes，需要进行decode

### TableToString

参数1: Table
参数2：int : 表示打印选项

打印选项的二进制位来表示需要打印的值，在选项中加上这个值即可
	0：牌山(1)
	1：玩家信息(2)
	2：DORA信息(4)
	3：立直棒(8)
	4：本场棒(16)
	5：亲家(32)
	6：剩余牌量(64)

返回的是GBK编码的bytes，需要进行decode

例：
想打印所有的信息，可以使用TableToString(table, 999)
想打印牌山和玩家信息，可以使用TableToString(table, 1+2)
想打印玩家信息，DORA信息和立直棒信息，可以使用TableToString(table, 2+4+8)

### RiverToString

参数:River类型
返回的是GBK编码的bytes，需要进行decode

### TileToString

参数:Tile类型
返回的是GBK编码的bytes，需要进行decode

### FuluToString

参数:Fulu类型
返回的是GBK编码的bytes，需要进行decode

### SelfActionToString

参数:SelfAction类型
返回的是GBK编码的bytes，需要进行decode

### ResponseActionToString

参数:ResponseAction类型
返回的是GBK编码的bytes，需要进行decode

### PlayerToString

参数:Player类型
返回的是GBK编码的bytes，需要进行decode

### ResultToString

参数:Result类型
返回的是GBK编码的bytes，需要进行decode

### CounterResultToString

参数:CounterResult类型
返回的是GBK编码的bytes，需要进行decode

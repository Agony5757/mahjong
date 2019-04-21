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

### 待完成

﻿#ifndef ACTION_H
#define ACTION_H

#include "Tile.h"

enum class Action : uint8_t {
	// response begin
	pass,
	吃, 
	碰,
	杠,
	荣和,
	// response end
	// 注意到所有的response Action可以通过大小来比较

	抢暗杠,
	抢杠,

	// self action begin
	暗杠,
	加杠,
	出牌,
	立直,
	自摸,
	九种九牌,
	// self action end
};

struct SelfAction {
	SelfAction() = default;
	SelfAction(Action, std::vector<Tile*>);
	Action action = Action::pass;
	std::vector<Tile*> correspond_tiles;
	std::string to_string() const;
};

struct ResponseAction {
	ResponseAction() = default;
	ResponseAction(Action, std::vector<Tile*>);
	Action action = Action::pass;
	std::vector<Tile*> correspond_tiles;
	std::string to_string() const;
};

#endif
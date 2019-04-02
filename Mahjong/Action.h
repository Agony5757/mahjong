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
	Action action;
	std::vector<Tile*> correspond_tiles;
	SelfAction(Action, std::vector<Tile*>);
};

struct ResponseAction {
	Action action;
	std::vector<Tile*> correspond_tiles;
};

#endif
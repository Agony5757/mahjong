#ifndef ACTION_H
#define ACTION_H

#include "Tile.h"

enum class Action : uint8_t {
	pass,
	吃, 碰,
	杠,
	暗杠,
	手切,
	摸切,
	手切立直,
	摸切立直,
	摸牌,
	自摸,
	荣和,
	九种九牌,
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
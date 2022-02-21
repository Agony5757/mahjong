#ifndef ACTION_H
#define ACTION_H

#include "Tile.h"

enum class BaseAction : uint8_t {
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

struct Action
{
	Action() = default;
	Action(BaseAction action, std::vector<Tile*>);
	BaseAction action = BaseAction::pass;
	std::vector<Tile*> correspond_tiles;
	std::string to_string() const;
};

struct SelfAction : public Action
{
	SelfAction() = default;
	SelfAction(BaseAction, std::vector<Tile*>);
};

struct ResponseAction : public Action
{
	ResponseAction() = default;
	ResponseAction(BaseAction, std::vector<Tile*>);
};

#endif
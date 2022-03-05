#ifndef ACTION_H
#define ACTION_H

#include "Tile.h"

enum class BaseAction : uint8_t {
	// response begin
	Pass,
	Chi, 
	Pon,
	Kan,
	Ron,
	// response end
	// 注意到所有的response Action可以通过大小来比较

	ChanAnKan,
	ChanKan,

	// self action begin
	AnKan,
	KaKan,
	Discard,
	Riichi,
	Tsumo,
	Kyushukyuhai,
	// self action end
};

struct Action
{
	Action() = default;
	Action(BaseAction action, std::vector<Tile*>);
	BaseAction action = BaseAction::Pass;
	std::vector<Tile*> correspond_tiles;
	std::string to_string() const;
    bool operator==(const Action& other);
};


struct SelfAction : public Action
{
	SelfAction() = default;
	SelfAction(BaseAction, std::vector<Tile*>);
    bool operator==(const SelfAction& other);
};

struct ResponseAction : public Action
{
	ResponseAction() = default;
	ResponseAction(BaseAction, std::vector<Tile*>);
    bool operator==(const ResponseAction& other);
};

#endif
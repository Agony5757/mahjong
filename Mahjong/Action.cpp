#include "Action.h"
#include "Action.h"

SelfAction::SelfAction(Action action, std::vector<Tile*> tiles)
	:action(action), correspond_tiles(tiles)
{
}

std::string SelfAction::to_string()
{
	switch (action) {
	case Action::pass:
		return "pass";
	case Action::吃:
		return "吃" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string();
	case Action::碰:
		return "碰" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string();
	case Action::杠:
		return "杠" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string() + correspond_tiles[2]->to_string();
	case Action::荣和:
		return "荣和";
	case Action::暗杠:
		return "暗杠" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string() + correspond_tiles[2]->to_string();
	case Action::加杠:
		return "加杠"; 
	case Action::出牌:
		return "出牌" + correspond_tiles[0]->to_string();
	case Action::立直:
		return "立直"; 
	case Action::自摸:
		return "自摸";
	case Action::九种九牌:
		return "九种九牌";
	default:
		throw std::runtime_error("Invalid Action");
	}
}

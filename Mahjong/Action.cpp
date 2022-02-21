#include "Action.h"

using namespace std;

Action::Action(BaseAction action, vector<Tile*> tiles)
	:action(action), correspond_tiles(tiles)
{ }

SelfAction::SelfAction(BaseAction action, vector<Tile*> tiles)
	: Action(action, tiles)
{ }

ResponseAction::ResponseAction(BaseAction action, vector<Tile*> tiles)
	: Action(action, tiles)
{ }


string Action::to_string() const 
{
	switch (action) {
	case BaseAction::暗杠:
		return "暗杠" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string() + correspond_tiles[2]->to_string();
	case BaseAction::加杠:
		return "加杠";
	case BaseAction::出牌:
		return "出牌" + correspond_tiles[0]->to_string();
	case BaseAction::立直:
		return "立直";
	case BaseAction::自摸:
		return "自摸";
	case BaseAction::九种九牌:
		return "九种九牌";
	case BaseAction::pass:
		return "pass";
	case BaseAction::吃:
		return "吃" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string();
	case BaseAction::碰:
		return "碰" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string();
	case BaseAction::杠:
		return "杠" + correspond_tiles[0]->to_string() + correspond_tiles[1]->to_string() + correspond_tiles[2]->to_string();
	case BaseAction::荣和:
		return "荣和"; 
	default:
		throw runtime_error("Invalid BaseAction");
	}
}

#include "Action.h"
#include <tuple>

using namespace std;
namespace_mahjong

Action::Action(BaseAction action, vector<Tile*> tiles)
	:action(action), correspond_tiles(tiles)
{ }

bool Action::operator==(const Action& other) const
{
	if (other.action == this->action && other.correspond_tiles == correspond_tiles)
	    return true;
	else return false;
}

bool Action::operator<(const Action& other) const
{
	return tie(action, correspond_tiles) < tie(other.action, other.correspond_tiles);
}

SelfAction::SelfAction(BaseAction action, vector<Tile*> tiles)
	: Action(action, tiles)
{ }

bool SelfAction::operator==(const SelfAction& other) const
{	
	if (other.action == this->action && other.correspond_tiles == correspond_tiles)
	    return true;
	else return false;
}

ResponseAction::ResponseAction(BaseAction action, vector<Tile*> tiles)
	: Action(action, tiles)
{ }

bool ResponseAction::operator==(const ResponseAction& other) const
{
	if (other.action == this->action && other.correspond_tiles == correspond_tiles)
	    return true;
	else return false;
}

string Action::to_string() const 
{
	switch (action) {
	case BaseAction::AnKan:
		return fmt::format("AnKan {}", correspond_tiles[0]->to_string());
	case BaseAction::KaKan:
		return fmt::format("KaKan {}", correspond_tiles[0]->to_string());
	case BaseAction::Discard:
		return "Discard " + correspond_tiles[0]->to_string();
	case BaseAction::Riichi:
		return "Riichi";
	case BaseAction::Tsumo:
		return "Tsumo";
	case BaseAction::Kyushukyuhai:
		return "Kyushukyuhai";
	case BaseAction::Pass:
		return "Pass";
	case BaseAction::Chi:
		return "Chi" + correspond_tiles[0]->to_string()
					+ correspond_tiles[1]->to_string();
	case BaseAction::Pon:
		return "Pon" + correspond_tiles[0]->to_string() 
		            + correspond_tiles[1]->to_string();
	case BaseAction::Kan:
		return "Kan" + correspond_tiles[0]->to_string() 
		            + correspond_tiles[1]->to_string() 
					+ correspond_tiles[2]->to_string();
	case BaseAction::Ron:
		return "Ron"; 		
	case BaseAction::ChanKan:
		return "ChanKan";
	case BaseAction::ChanAnKan:
		return "ChanAnKan";
	default:
		throw runtime_error("Invalid BaseAction");
	}
}

namespace_mahjong_end

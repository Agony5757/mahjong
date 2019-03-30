#include "Action.h"

SelfAction::SelfAction(Action action, std::vector<Tile*> tiles)
	:action(action), correspond_tiles(tiles)
{
}

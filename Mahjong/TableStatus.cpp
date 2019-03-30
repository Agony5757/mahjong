#include "TableStatus.h"

using namespace std;

AbstractTableStatus::AbstractTableStatus(const GameLog & gameLog)
	:game_log(gameLog)
{

}

GameLog AbstractTableStatus::get_gamelog()
{
	return game_log;
}



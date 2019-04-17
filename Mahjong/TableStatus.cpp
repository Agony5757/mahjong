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

void AbstractTableStatus::parse_gamelog()
{
}

std::string AbstractTableStatus::to_string()
{
	return status;
}



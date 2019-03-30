#ifndef GAMELOG_H
#define GAMELOG_H

#include "Action.h"

struct BaseGameLog {
	int player; // 主叫
	int player2;// 被叫
	Action action;
	Tile* 牌;
	std::vector<Tile*> 副露;

	BaseGameLog(int, int, Action, Tile*, std::vector<Tile*>);

	std::string to_string();
};

class GameLog {
public:
	std::vector<BaseGameLog> logs;
	std::string to_string();
	void _log(int player1, int player2, Action, Tile*, std::vector<Tile*>);
	void log摸牌(int player, Tile*);
	void log摸切(int player, Tile*);
	void log手切(int player, Tile*);
};

#endif
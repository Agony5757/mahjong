#ifndef GAMELOG_H
#define GAMELOG_H

#include "Tile.h"

enum LogAction {
	暗杠,
	碰,
	吃,
	手切,
	摸切,
	摸牌,
	手切立直,
	摸切立直,
};

struct BaseGameLog {
	int player; // 主叫
	int player2;// 被叫
	LogAction action;
	Tile* 牌;
	std::vector<Tile*> 副露;

	BaseGameLog(int, int, LogAction, Tile*, std::vector<Tile*>);

	std::string to_string();
};

class GameLog {
public:
	std::vector<BaseGameLog> logs;
	std::string to_string();
	void _log(int player1, int player2, LogAction, Tile*, std::vector<Tile*>);
	void log摸牌(int player, Tile*);
	void log摸切(int player, Tile*);
	void log手切(int player, Tile*);
};

#endif
#ifndef GAMELOG_H
#define GAMELOG_H

#include "Tile.h"
#include "Action.h"
#include "GameResult.h"
#include "macro.h"

enum class LogAction {
	暗杠,
	碰,
	吃,
	杠,
	加杠,
	手切,
	摸切,
	摸牌,
	手切立直,
	摸切立直,
	九种九牌,
	荣和,
	自摸,
	立直通过,
};

constexpr bool DiscardFromTsumo = false;
constexpr bool DiscardFromHand = true;

class Table;

struct BaseGameLog {

protected:
	BaseGameLog() {}

public:
	int player; // 主叫
	int player2;// 被叫
	LogAction action;
	Tile* 牌;
	std::vector<Tile*> 副露;
	std::array<int, 4> score;

	BaseGameLog(int, int, LogAction, Tile*, std::vector<Tile*>);
	BaseGameLog(std::array<int, 4> scores);
	virtual std::string to_string();
};

class GameLog {
public:
	std::vector<int> winner;
	std::vector<int> loser;
	std::array<int, 4> start_scores;
	std::string yama;
	int start本场;
	int end本场;

	int start立直棒;
	int end立直棒;
	int 庄家;

	Wind 场风;
	Result result;
	std::vector<BaseGameLog> logs;

	void _log(BaseGameLog log);
	void logGameStart(int start本场, int start立直棒, int oya, Wind 场风,
		std::string yama,
		std::array<int, 4>);
	void log摸牌(int player, Tile*);
	void log摸切(int player, Tile*);
	void log手切(int player, Tile*);

	inline void log出牌(int player, Tile* tile, bool 手切摸切) {
		if (手切摸切 == DiscardFromHand)
			log手切(player, tile);
		else
			log摸切(player, tile);
	}

	void log摸切立直(int player, Tile*);
	void log手切立直(int player, Tile*);

	inline void log立直(int player, Tile* tile, bool 手切摸切) {
		if (手切摸切 == DiscardFromHand)
			log手切立直(player, tile);
		else
			log摸切立直(player, tile);
	}

	void log_response_鸣牌(int player_call, int player_turn,
		Tile*, std::vector<Tile*> tiles, BaseAction action);

	void log加杠(int player, Tile*);
	void log暗杠(int player, std::vector<Tile*> tiles);
	void log立直通过(Table* table);
	void log九种九牌(int player, Result result);
	void logGameOver(Result result);
	std::string to_string();
};

#endif
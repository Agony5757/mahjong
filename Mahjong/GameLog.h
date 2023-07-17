#ifndef GAMELOG_H
#define GAMELOG_H

#include "Tile.h"
#include "Action.h"
#include "GameResult.h"
#include "macro.h"

namespace_mahjong

enum class LogAction {
	AnKan,
	Pon,
	Chi,
	Kan,
	KaKan,
	DiscardFromHand,
	DiscardFromTsumo,
	Draw,
	RiichiDiscardFromHand,
	RiichiDiscardFromTsumo,
	Kyushukyuhai,
	Ron,
	Tsumo,
	RiichiSuccess,
};

constexpr bool DiscardFromTsumo = false;
constexpr bool DiscardFromHand = true;

class Table;

struct BaseGameLog {

protected:
	BaseGameLog() {}

public:
	int player;
	int player2; 
	LogAction action;
	Tile* tile;
	std::vector<Tile*> call_tiles;
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
	int start_honba;
	int end_honba;

	int start_kyoutaku;
	int end_kyoutaku;
	int oya;

	Wind game_wind;
	Result result;
	std::vector<BaseGameLog> logs;

	void _log(BaseGameLog log);
	void log_game_start(int start_honba, int start_kyoutaku, int oya, Wind game_wind,
		std::string yama,
		std::array<int, 4>);
	void log_draw(int player, Tile*);
	void log_discard_from_tsumo(int player, Tile*);
	void log_discard_from_hand(int player, Tile*);

	inline void log_discard(int player, Tile* tile, bool fromhand) {
		if (fromhand == DiscardFromHand)
			log_discard_from_hand(player, tile);
		else
			log_discard_from_tsumo(player, tile);
	}

	void log_riichi_discard_from_tsumo(int player, Tile*);
	void log_riichi_discard_from_hand(int player, Tile*);

	inline void log_riichi_discard(int player, Tile* tile, bool fromhand) {
		if (fromhand == DiscardFromHand)
			log_riichi_discard_from_hand(player, tile);
		else
			log_riichi_discard_from_tsumo(player, tile);
	}

	void log_call(int player_call, int player_turn,
		Tile*, std::vector<Tile*> tiles, BaseAction action);

	void log_kakan(int player, Tile*);
	void log_ankan(int player, std::vector<Tile*> tiles);
	void log_riichi_success(Table* table);
	void log_kyushukyuhai(int player, Result result);
	void log_gameover(Result result);
	std::string to_string();
};

namespace_mahjong_end

#endif
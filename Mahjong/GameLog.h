#ifndef GAMELOG_H
#define GAMELOG_H

#include "Tile.h"
#include "Action.h"
#include "GameResult.h"
#include "macro.h"

namespace_mahjong

enum class LogAction {
	AnKan, // 暗杠
	Pon,   // 碰
	Chi,   // 吃
	Kan,   // 杠
	KaKan, // 加杠
	DiscardFromHand, // 手切
	DiscardFromTsumo,// 摸切
	RiichiDiscardFromHand, // 宣告手切立
	RiichiDiscardFromTsumo,// 宣告摸切立
	RiichiSuccess, // 立直通过
	DrawNormal,   // 正常摸牌
	DrawRinshan,  // 摸岭上牌
	DoraReveal, // 翻1张宝牌
	Kyushukyuhai, // 宣告九种九牌
	Ron, // 宣告Ron
	Tsumo, // 宣告自摸
	InvalidLogAction,
};

constexpr bool DiscardFromTsumo = false;
constexpr bool DiscardFromHand = true;
constexpr bool DrawNormally = false;
constexpr bool DrawFromRinshan = true;

class Table;

struct BaseGameLog {
	BaseGameLog() = delete;
	int player = 0;
	int player2 = 0; 
	LogAction action = LogAction::InvalidLogAction;
	Tile* tile = nullptr;
	std::vector<Tile*> call_tiles;
	std::array<int, 4> score = { 0 };

	BaseGameLog(int p1, int p2, LogAction action, Tile* tile,
		const std::vector<Tile*>& callgroup);
	BaseGameLog(const std::array<int, 4> &scores);
	virtual std::string to_string();
};

class GameLog {
public:
	std::vector<int> winner;
	std::vector<int> loser;
	std::array<int, 4> start_scores;
	std::vector<Tile*> init_yama;
	std::array<std::vector<Tile*>, 4> init_hands;
	int start_honba;
	int end_honba = -1;

	int start_kyoutaku;
	int end_kyoutaku = -1;
	int oya;

	Wind game_wind;
	Result result;
	std::vector<BaseGameLog> logs;

	GameLog() 
	{ 
		/* avoid reallocation */ 
		logs.reserve(128);
	}

	void _log(BaseGameLog log);

	void log_game_start(int start_honba, int start_kyoutaku, int oya, Wind game_wind,
		const std::vector<Tile*> &yama, const std::array<int, 4> &start_scores,
		const std::vector<Tile*> init_hand0,
		const std::vector<Tile*> init_hand1,
		const std::vector<Tile*> init_hand2,
		const std::vector<Tile*> init_hand3
		);

	void _log_draw_normal(int player, Tile* tile);
	void _log_draw_rinshan(int player, Tile* tile);
	inline void log_draw(int player, Tile* tile, bool from_rinshan)
	{
		if (from_rinshan)
			_log_draw_rinshan(player, tile);
		else
			_log_draw_normal(player, tile);
	}

	void _log_discard_from_tsumo(int player, Tile* tile);
	void _log_discard_from_hand(int player, Tile* tile);

	inline void log_discard(int player, Tile* tile, bool fromhand) {
		if (fromhand == DiscardFromHand)
			_log_discard_from_hand(player, tile);
		else
			_log_discard_from_tsumo(player, tile);
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
	void log_tsumo(int player);
	void log_ron(int player_win, int player_lose, Tile* tile);
	void log_reveal_dora(Tile* tile);
	void log_gameover(Result result);
	inline size_t logsize() const { return logs.size(); }
	inline auto& operator[](size_t loc) const { return logs[loc]; }
	inline auto& operator[](size_t loc) { return logs[loc]; }

	std::string to_string();
};

namespace_mahjong_end

#endif
#include "GameLog.h"
#include "Table.h"
#include "fmt/core.h"
#include <sstream>

using namespace std;
namespace_mahjong

BaseGameLog::BaseGameLog(int p1, int p2, LogAction action, Tile* tile,
	const vector<Tile*> &callgroup)
	: player(p1), player2(p2), action(action), tile(tile), call_tiles(callgroup)
{
}

BaseGameLog::BaseGameLog(const array<int, 4> &scores)
{
	score = scores;
}

string BaseGameLog::to_string()
{
	switch (action) {
	case LogAction::KaKan:
		return fmt::format("p{} Kakan {}", player, tile->to_string());
	case LogAction::AnKan:
		return fmt::format("p{} AnKan {}", player, tiles_to_string(call_tiles));
	case LogAction::Pon:
		return fmt::format("p{} Pon {} with {}", player, tile->to_string(), tiles_to_string(call_tiles));
	case LogAction::Chi:
		return fmt::format("p{} Chi {} with {}", player, tile->to_string(), tiles_to_string(call_tiles));
	case LogAction::Kan:
		return fmt::format("p{} Kan {} with {}", player, tile->to_string(), tiles_to_string(call_tiles));
	case LogAction::DiscardFromHand:
		return fmt::format("p{} Discard (from hand) {}", player, tile->to_string());
	case LogAction::DiscardFromTsumo:
		return fmt::format("p{} Discard (from tsumo) {}", player, tile->to_string());
	case LogAction::DrawNormal:
		return fmt::format("p{} Draw {}", player, tile->to_string());
	case LogAction::DrawRinshan:
		return fmt::format("p{} Draw (rinshan) {}", player, tile->to_string());
	case LogAction::RiichiDiscardFromHand:
		return fmt::format("p{} Riichi discard (from hand) {}", player, tile->to_string());
	case LogAction::RiichiDiscardFromTsumo:
		return fmt::format("p{} Riichi discard (from tsumo) {}", player, tile->to_string());
	case LogAction::Kyushukyuhai:
		return fmt::format("p{} Kyushukyuhai", player);
	case LogAction::RiichiSuccess:
		return fmt::format("p{} Riichi Success {}", player, score_to_string(score));
	case LogAction::DoraReveal:
		return fmt::format("Reveal dora: {}", tile->to_string());
	default:
		throw runtime_error("Invalid LogAction. LogAction: " + std::to_string(int(action)));
	}
}

string GameLog::to_string()
{
	stringstream ss;
	ss << fmt::format(
		"Oya: Player {}\n"
		"Game wind: {}\n"
		"{} honba, {} kyoutaku\n"
		"Initial points: {}\n"
		"Initial yama: {}\n"
		"Hand0: {}\n"
		"Hand1: {}\n"
		"Hand2: {}\n"
		"Hand3: {}\n"
		,
		oya,
		wind_to_string(game_wind),
		start_honba, start_kyoutaku,
		start_scores,
		vector_tile_to_string(init_yama),
		vector_tile_to_string(init_hands[0]),
		vector_tile_to_string(init_hands[1]),
		vector_tile_to_string(init_hands[2]),
		vector_tile_to_string(init_hands[3])
	);

	//ss << "Oya: Player " << oya << endl
	//	<< "场风: " << wind_to_string(game_wind) << endl
	//	<< start_honba << "本场 " << start_kyoutaku << "立直棒" << endl
	//	<< "点数:" << score_to_string(start_scores) << endl
	//	<< "牌山:" << init_yama << endl;
	for (auto log : logs) {
		ss << log.to_string() << endl;
	}
	if (result.result_type != ResultType::Error)
		ss << "Result:" << result.to_string() << endl;

	return ss.str();
}

void GameLog::_log(BaseGameLog log) {
	FunctionProfiler;
	logs.push_back(log);
}

void GameLog::log_game_start(
	int start_honba_, int start_kyoutaku_, int oya_, Wind game_wind_, 
	const std::vector<Tile*>& yama_, const std::array<int, 4> &scores,
	const std::vector<Tile*> init_hand0,
	const std::vector<Tile*> init_hand1,
	const std::vector<Tile*> init_hand2,
	const std::vector<Tile*> init_hand3)
{
	start_honba = start_honba_;
	start_kyoutaku = start_kyoutaku_;
	oya = oya_;
	game_wind = game_wind_;
	init_yama = yama_;
	start_scores = scores;
	init_hands = {
		init_hand0,
		init_hand1,
		init_hand2,
		init_hand3
	};
	for (const auto& hand : init_hands)
	{
		if (hand.size() != 13)
			throw std::runtime_error("Game init log failed. Hand size is not 13 at the beginning.");
	}
}

void GameLog::_log_draw_normal(int player, Tile* tile)
{
	_log({ player, -1, LogAction::DrawNormal, tile, {} });
}

void GameLog::_log_draw_rinshan(int player, Tile* tile)
{
	_log({ player, -1, LogAction::DrawRinshan, tile, {} });
}

void GameLog::_log_discard_from_tsumo(int player, Tile* tile)
{
	_log({ player, -1, LogAction::DiscardFromTsumo, tile, {} });
}

void GameLog::_log_discard_from_hand(int player, Tile* tile)
{
	_log({ player, -1, LogAction::DiscardFromHand, tile, {} });
}

void GameLog::log_riichi_discard_from_tsumo(int player, Tile* tile)
{
	_log({ player, -1, LogAction::RiichiDiscardFromTsumo, tile, {} });
}

void GameLog::log_riichi_discard_from_hand(int player, Tile* tile)
{
	_log({ player, -1, LogAction::RiichiDiscardFromHand, tile, {} });
}

void GameLog::log_call(int player_call, int player_turn,
	Tile* tile, vector<Tile*> tiles, BaseAction action)
{
	LogAction la;
	switch (action)
	{
	case BaseAction::Chi:
		la = LogAction::Chi;
		break;
	case BaseAction::Pon:
		la = LogAction::Pon;
		break;
	case BaseAction::Kan:
		la = LogAction::Kan;
		break;
	default:
		throw runtime_error("Invalid BaseAction when logging. BaseAction:" +
			std::to_string(int(action)));
	}
	_log({ player_call, player_turn, la, tile, tiles });
}

void GameLog::log_kakan(int player, Tile* tile)
{
	_log({ player, -1, LogAction::KaKan, tile, {} });
}

void GameLog::log_ankan(int player, vector<Tile*> tiles)
{
	_log({ player, -1, LogAction::AnKan, nullptr, tiles });
}

void GameLog::log_riichi_success(Table* table)
{
	BaseGameLog gamelog(table->get_scores());
	gamelog.player = table->turn;
	gamelog.action = LogAction::RiichiSuccess;
	logs.push_back(gamelog);
}

void GameLog::log_kyushukyuhai(int player, Result result)
{
	_log({ player,-1, LogAction::Kyushukyuhai, nullptr, {} });
	log_gameover(result);
}

void GameLog::log_tsumo(int player)
{
	_log({ player, -1, LogAction::Tsumo, nullptr, {} });
}

void GameLog::log_ron(int player_win, int player_lose, Tile* tile)
{
	_log({ player_win, player_lose, LogAction::Tsumo, tile, {} });
}

void GameLog::log_reveal_dora(Tile* tile)
{
	_log({ -1, -1, LogAction::DoraReveal, tile, {} });
}

void GameLog::log_gameover(Result _result)
{
	result = _result;
}

namespace_mahjong_end

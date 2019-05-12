#include "GameLog.h"
#include "GameLog.h"
#include "GameLog.h"
#include "GameLog.h"
#include "GameLog.h"
#include "Table.h"
#include <sstream>

using namespace std;

BaseGameLog::BaseGameLog(int p1, int p2, LogAction action, Tile *tile,
	std::vector<Tile*> fulu)
	:player(p1), player2(p2), action(action), 牌(tile), 副露(fulu)
{
}

BaseGameLog::BaseGameLog(std::array<int, 4> scores)
{
	score = scores;
}

std::string BaseGameLog::to_string()
{
	stringstream ss;
	ss << "p" << player;
	switch (action) {
	case LogAction::暗杠:
		ss << "暗杠" << tiles_to_string(副露);
		return ss.str();
	case LogAction::碰:
		ss << "碰" << 牌->to_string() << "with" << tiles_to_string(副露);
		return ss.str();
	case LogAction::吃:
		ss << "吃" << 牌->to_string() << "with" << tiles_to_string(副露);
		return ss.str();
	case LogAction::手切:
		ss << "手切" << 牌->to_string();
		return ss.str();
	case LogAction::摸切:
		ss << "摸切" << 牌->to_string();
		return ss.str();
	case LogAction::摸牌:
		ss << "摸牌" << 牌->to_string();
		return ss.str();
	case LogAction::手切立直:
		ss << "手切立直" << 牌->to_string();
		return ss.str();
	case LogAction::摸切立直:
		ss << "摸切立直" << 牌->to_string();
		return ss.str();
	case LogAction::九种九牌:
		ss << "九种九牌";
		return ss.str();
	case LogAction::立直通过:
		ss << "立直通过:" << score_to_string(score);
		return ss.str();
	default:
		throw runtime_error("Invalid LogAction. Action: " + std::to_string(int(action)));
	}
}

std::string GameLog::to_string()
{
	stringstream ss;
	ss << "庄家: Player " << 庄家 << endl
		<< "场风: " << wind_to_string(场风) << endl
		<< start本场 << "本场 " << start立直棒 << "立直棒" << endl
		<< "点数:" << score_to_string(start_scores) << endl
		<< "牌山:" << yama << endl;
	for (auto log : logs) {
		ss << log.to_string() << endl;
	}
	ss << "结果:" << result.to_string() << endl;

	return ss.str();
}

void GameLog::_log(BaseGameLog log) {
	logs.push_back(log);
}

void GameLog::logGameStart(
	int _start本场, int _start立直棒, int _oya, Wind _场风, string _yama,
	std::array<int,4> scores)
{
	start本场 = _start本场;
	start立直棒 = _start立直棒;
	庄家 = _oya;
	场风 = _场风;
	yama = _yama;
	start_scores = scores;
}

void GameLog::log摸牌(int player, Tile* tile)
{
	_log({ player, -1, LogAction::摸牌, tile, {} });
}

void GameLog::log摸切(int player, Tile *tile)
{
	_log({ player, -1, LogAction::摸切, tile, {} });
}

void GameLog::log手切(int player, Tile *tile)
{
	_log({ player, -1, LogAction::手切, tile, {} });
}

void GameLog::log摸切立直(int player, Tile *tile)
{
	_log({ player, -1, LogAction::摸切立直, tile, {} });
}

void GameLog::log手切立直(int player, Tile *tile)
{
	_log({ player, -1, LogAction::手切立直, tile, {} });
}

void GameLog::log_response_鸣牌(int player_call, int player_turn, 
	Tile *tile, std::vector<Tile*> tiles, Action action)
{
	LogAction la;
	switch (action)
	{
	case Action::吃:
		la = LogAction::吃;
		break;
	case Action::碰:
		la = LogAction::碰;
		break;
	case Action::杠:
		la = LogAction::杠;
		break;
	default:
		throw runtime_error(
			"Invalid Action when logging. Action:" + 
			std::to_string(int(action))
		);
	}
	_log({ player_call, player_turn, la, tile, tiles });
}

void GameLog::log加杠(int player, Tile *tile)
{
	_log({ player, -1, LogAction::加杠, tile, {} });
}

void GameLog::log暗杠(int player, vector<Tile*> tiles)
{
	_log({ player, -1, LogAction::加杠, nullptr, tiles });
}

void GameLog::log立直通过(Table * table)
{
	BaseGameLog gamelog(table->get_scores());
	gamelog.player = table->turn;
	gamelog.action = LogAction::立直通过;
	logs.push_back(gamelog);
}

void GameLog::log九种九牌(int player)
{
	_log({ player,-1, LogAction::九种九牌, nullptr, {} });
}

void GameLog::logGameOver(Result _result)
{
	result = _result;
}





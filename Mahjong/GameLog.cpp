#include "GameLog.h"
#include <sstream>

using namespace std;

BaseGameLog::BaseGameLog(int p1, int p2, Action action, Tile *tile,
	std::vector<Tile*> fulu)
	:player(p1), player2(p2), action(action), 牌(tile), 副露(fulu)
{
}

std::string BaseGameLog::to_string()
{
	stringstream ss;
	switch (action) {
	case Action::暗杠:
		ss << "暗杠|";
		goto 副露情况;
	case Action::碰:
		ss << "碰|";
		goto 副露情况;
	case Action::吃:
		ss << "吃|";
		goto 副露情况;
	case Action::手切:
		ss << "手切|";
		goto 出牌情况;
	case Action::摸切:
		ss << "摸切|";
		goto 出牌情况;
	case Action::摸牌:
		ss << "摸牌|";
		goto 出牌情况;
	case Action::手切立直:
		ss << "手切立直|";
		goto 立直情况;
	case Action::摸切立直:
		ss << "摸切立直|";
		goto 立直情况;
	default:
		return "??\n";
	}
立直情况:
出牌情况:
	if (牌 == nullptr) {
		ss << "-";
	}
	else {
		ss << 牌->to_string();
	}
	ss << "|Player" << player << endl;
	return ss.str();
副露情况:
	ss << 副露_to_string(牌, 副露)
		<< "|Player" << player
		<< "|Player2" << player2
		<< endl;
	return ss.str();
}

std::string GameLog::to_string()
{
	stringstream ss;
	for (auto log : logs) {
		ss << log.to_string();
	}
	return ss.str();
}

void GameLog::_log(int player1, int player2, Action action,
	Tile *tile, std::vector<Tile*> fulu)
{
	logs.push_back(BaseGameLog(player1, player2, action, tile, fulu));
}

void GameLog::log摸牌(int player, Tile* tile)
{
	_log(player, -1, Action::摸牌, tile, {});
}

void GameLog::log摸切(int player, Tile *tile)
{
	_log(player, -1, Action::摸切, tile, {});
}

void GameLog::log手切(int player, Tile *tile)
{
	_log(player, -1, Action::手切, tile, {});
}
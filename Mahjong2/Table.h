#pragma once

#include <memory>
#include <vector>
#include <unordered_map>
#include <string>
#include <iostream>
#include <sstream>
#include <exception>
#include <algorithm>
#include <stdlib.h>
#include <time.h>

constexpr auto N_TILES = (34*4);
constexpr auto INIT_SCORE = 25000;

enum class Belong : uint8_t {
	p1手, p1河,
	p2手, p2河,
	p3手, p3河,
	p4手, p4河,
	yama,
};

enum BaseTile {
	_1m, _2m, _3m, _4m, _5m, _6m, _7m, _8m, _9m,
	_1s, _2s, _3s, _4s, _5s, _6s, _7s, _8s, _9s,
	_1p, _2p, _3p, _4p, _5p, _6p, _7p, _8p, _9p,
	east, south, west, north,
	白, 发, 中
};

enum Wind {
	East = 1, South, West, North
};

enum Action {
	吃, 碰,
	杠,
	暗杠,
	手切,
	摸切,
	摸牌,
};

class Tile {
public:
	BaseTile tile;
	bool red_dora;
	Belong belongs;
	inline std::string to_string() {
		std::string ret;
		if (0 <= tile && tile <= 8) {
			ret = "[" + std::to_string(static_cast<int>(tile) + 1) + "m";
		}
		else if (9 <= tile && tile <= 17) {
			ret = "[" + std::to_string(static_cast<int>(tile) - 8) + "s";
		}
		else if (18 <= tile && tile <= 26) {
			ret = "[" + std::to_string(static_cast<int>(tile) - 17) + "p";
		}
		else if (tile == east) {
			ret = "[东";
		}
		else if (tile == south) {
			ret = "[南";
		}
		else if (tile == west) {
			ret = "[西";
		}
		else if (tile == north) {
			ret = "[北";
		}
		else if (tile == 白) {
			ret = "[白";
		}
		else if (tile == 发) {
			ret = "[发";
		}
		else if (tile == 中) {
			ret = "[中";
		}
		else throw std::runtime_error("unknown tile");

		if (red_dora) {
			ret += '*';
		}
		return ret + ']';
	}
};

inline bool tile_comparator(Tile* t2, Tile* t1) {
	if (t1->tile > t2->tile) {
		return true;
	}
	else if (t1->tile < t2->tile) {
		return false;
	}
	else {
		return t1 > t2;
	}
}

inline std::string tiles_to_string(std::vector<Tile*> tiles) {
	std::stringstream ss;
	for (auto tile : tiles) {
		ss << tile->to_string();
	}
	return ss.str();
}

inline std::string 副露_to_string(Tile* head, std::vector<Tile*> fulu) {
	std::stringstream ss;
	ss << "[" << head->to_string() << "]";
	ss << tiles_to_string(fulu);
	return ss.str();
}

inline std::string wind_to_string(Wind wind) {
	switch (wind) {
	case Wind::East:
		return "东";
	case Wind::South:
		return "南";
	case Wind::West:
		return "西";
	case Wind::North:
		return "北";
	default:
		return "??";
	}
}

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

class Player {
public:
	Player();
	bool riichi;
	Wind wind;
	bool 亲家;
	int score;
	std::vector<Tile*> hand;
	std::vector<Tile*> river;
	std::unordered_map<Tile*, std::vector<Tile*>> 副露s;
	std::string hand_to_string();
	std::string river_to_string();

	std::string to_string();

	void play_tile();

	void sort_hand();
	void test_show_hand();	
};

enum ResultType {
	荣和终局,
	自摸终局,
	九种九牌流局终局,
	流局满贯,
	无人听牌流局,
	一人听牌流局,
	两人听牌流局,
	三人听牌流局,
	四人听牌流局,
	两家荣和,
	三家荣和,
};

struct Result {
	ResultType result_type;

	// 自摸，一家荣和的情况
	int score;
	int fan;
	int fu;
	int 役满倍数;

	// 两家荣和的情况
	int score2;
	int fan2;
	int fu2;
	int 役满倍数2;

	// 三家荣和的情况
	int score3;
	int fan3;
	int fu3;
	int 役满倍数3;

	std::vector<int> winner;
	std::vector<int> loser;
};

class Table
{
private:
	Tile tiles[N_TILES];
public:
	int dora_spec;
	Wind 场风;
	int 庄家;
	void init_tiles();
	void init_red_dora_3();
	void shuffle_tiles();
	void init_yama();

	void init_wind();
	
	void _deal(int i_player);
	void _deal(int i_player, int n_tiles);

	void 发牌(int i_player);

	inline void next_turn() { turn++; turn = turn % 4; }

	GameLog openGameLog;
	GameLog fullGameLog;

	int turn;

	Table(int 庄家);

	int GetValidActions();

	std::vector<Tile*> 牌山;
	Player player[4];
	~Table();

	void test_show_yama_with_王牌();
	void test_show_yama();
	void test_show_player_hand(int i_player);
	void test_show_all_player_hand();
	void test_show_player_info(int i_player);
	void test_show_all_player_info();
	void test_show_open_gamelog();
	void test_show_full_gamelog();

	inline void test_show_all() {
		test_show_yama_with_王牌();
		test_show_all_player_info();
		test_show_open_gamelog();
		test_show_full_gamelog();
		std::cout << "轮到Player" << turn << std::endl;
	}

	Result GameProcess(bool);

};


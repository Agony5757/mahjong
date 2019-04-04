#ifndef TABLE_H
#define TABLE_H

#include "Tile.h"
#include "Action.h"
#include "GameLog.h"
#include "GameResult.h"

constexpr auto N_TILES = (34*4);
constexpr auto INIT_SCORE = 25000;

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

	bool 一发;
	bool first_round;

	void play_tile();

	void sort_hand();
	void test_show_hand();	
};

// Forward Decl
class Agent;

class Table
{
private:
	Tile tiles[N_TILES];
public:

	Agent* agents[4];
	int dora_spec;
	Wind 场风;
	int 庄家; // 庄家
	int n本场;
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

	// 下标表示玩家编号，bool表示是否进入该状态, int表示下一次轮到该玩家打牌时,
	// 解除对应的振听状态
	std::vector<std::pair<bool, int>> 同巡振听;

	Table(int 庄家, Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4]);

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> GetValidActions();
	std::vector<ResponseAction> GetValidResponse(int player);

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

#endif
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
	bool riichi = false;
	bool 门清 = true;
	Wind wind;
	bool 亲家;
	bool 振听 = false;
	int score;
	std::vector<Tile*> hand;
	std::vector<Tile*> river;
	std::vector<Fulu> 副露s;
	std::string hand_to_string();
	std::string river_to_string();

	std::string to_string();

	bool 一发;
	bool first_round;

	// SelfAction
	std::vector<SelfAction> get_加杠(bool after_chipon);
	std::vector<SelfAction> get_暗杠(bool after_chipon);
	std::vector<SelfAction> get_打牌(bool after_chipon);
	std::vector<SelfAction> get_自摸();
	std::vector<SelfAction> get_立直();
	std::vector<SelfAction> get_九种九牌(bool 第一巡);

	// Response Action
	std::vector<ResponseAction> get_荣和(Tile* tile);
	std::vector<ResponseAction> get_Chi(Tile* tile);
	std::vector<ResponseAction> get_Pon(Tile* tile);
	std::vector<ResponseAction> get_Kan(Tile* tile); // 大明杠

	void move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile);
	void remove_from_hand(Tile* tile);
	void play_暗杠(std::vector<Tile*> tiles);

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
	
	bool after_chipon = false;
	bool after_kan = false;

	Table(int 庄家 = 0, Agent* p1 = nullptr, Agent* p2 = nullptr, Agent* p3 = nullptr, Agent* p4 = nullptr);
	Table(int 庄家, Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4]);

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> GetValidActions();

	// 根据turn打出的tile，可以做出的决定
	std::vector<ResponseAction> GetValidResponse(int player, Tile* tile);

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
#ifndef TABLE_H
#define TABLE_H

#include "Tile.h"
#include "Action.h"
#include "GameLog.h"
#include "GameResult.h"

constexpr auto N_TILES = (34*4);
constexpr auto INIT_SCORE = 25000;

// Forward Decl
class Table;

class Player {
public:
	Player();
	bool double_riichi = false;
	bool riichi = false;
	// 第几张开始是立直牌
	int riichi_n = 0;
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
	std::vector<SelfAction> get_加杠();
	std::vector<SelfAction> get_暗杠();
	std::vector<SelfAction> get_打牌(bool after_chipon);
	std::vector<SelfAction> get_自摸(Table*);
	std::vector<SelfAction> get_立直();
	std::vector<SelfAction> get_九种九牌();

	// Response Action
	std::vector<ResponseAction> get_荣和(Table*, Tile* tile);
	std::vector<ResponseAction> get_Chi(Tile* tile);
	std::vector<ResponseAction> get_Pon(Tile* tile);
	std::vector<ResponseAction> get_Kan(Tile* tile); // 大明杠
	
	// Response Action (抢暗杠)
	std::vector<ResponseAction> get_抢暗杠(Tile* tile);

	// Response Action (抢杠)
	std::vector<ResponseAction> get_抢杠(Tile* tile);

	void move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile);
	void remove_from_hand(Tile* tile);

	// 将所有的BaseTile值为tile的四个牌移动到副露区
	void play_暗杠(BaseTile tile);

	// 移动tile到副露中和它basetile相同的刻子中
	void play_加杠(Tile* tile);

	// 将牌移动到牌河（一定没有人吃碰杠）
	void move_from_hand_to_river(Tile* tile);

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

	// 翻开了几张宝牌指示牌
	int dora_spec;
	std::vector<Tile*> 宝牌指示牌;
	std::vector<Tile*> 里宝牌指示牌;

	inline int get_remain_kan_tile() {
		auto iter = find(牌山.begin(), 牌山.end(), 宝牌指示牌[0]);
		return iter - 牌山.begin() - 1;
	}

	inline int get_remain_tile() {
		return 牌山.size() - 14;
	}

	Wind 场风;
	int 庄家; // 庄家
	int n本场;
	int n立直棒;
	void init_tiles();
	void init_red_dora_3();
	void shuffle_tiles();
	void init_yama();

	std::string export_yama();
	void import_yama(std::string);
	void init_wind();
	
	void _deal(int i_player);
	void _deal(int i_player, int n_tiles);

	void 发牌(int i_player);
	void 发岭上牌(int i_player);

	inline void next_turn() { turn++; turn = turn % 4; }

	GameLog openGameLog;
	GameLog fullGameLog;

	int turn;
	
	Action last_action;
	inline bool after_chipon(){
		return last_action == Action::吃 ||
			last_action == Action::碰;
	}

	inline bool after_daiminkan() {
		return last_action == Action::杠;
	}

	inline bool after_ankan() {
		return last_action == Action::暗杠;
	}

	inline bool after_加杠() {
		return last_action == Action::加杠;
	}

	inline bool after_杠() {
		return after_daiminkan() || after_ankan() || after_加杠();
	}

	Table(int 庄家 = 0, Agent* p1 = nullptr, Agent* p2 = nullptr, Agent* p3 = nullptr, Agent* p4 = nullptr);
	Table(int 庄家, Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4]);

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> GetValidActions();

	// 根据turn打出的tile，可以做出的决定
	std::vector<ResponseAction> GetValidResponse(int player, Tile* tile, bool);

	// 根据turn打出的tile，可以做出的抢杠决定
	std::vector<ResponseAction> Get抢暗杠(int player, Tile* tile);

	// 根据turn打出的tile，可以做出的抢杠决定
	std::vector<ResponseAction> Get抢杠(int player, Tile* tile);

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
		//test_show_open_gamelog();
		//test_show_full_gamelog();
		std::cout << "轮到Player" << turn << std::endl;
	}

	Result GameProcess(bool, std::string = "");

};

#endif
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

class RiverTile {
public:
	Tile* tile;

	// 第几张牌丢下去的
	int number;

	// 是不是立直后弃牌
	bool riichi;

	// 这张牌明面上还在不在河里
	bool remain;

	// true为手切，false为摸切
	bool fromhand;
};

class River {
	// 记录所有的弃牌，而不是仅仅在河里的牌
public:
	std::vector<RiverTile> river;
	inline std::vector<BaseTile> to_basetile() {
		std::vector<BaseTile> basetiles;
		for (auto &tile : river) {
			basetiles.push_back(tile.tile->tile);
		}
		return basetiles;
	}
	inline std::string to_string() {
		std::stringstream ss;

		for (auto tile : river) {
			ss << tile.tile->to_string() << tile.number;
			if (tile.fromhand)
				ss << "h";
			if (tile.riichi)
				ss << "r";
			if (!tile.remain)
				ss << "-";
			ss << " ";
		}
		return ss.str();
	}

	inline RiverTile& operator[](size_t n) {
		return river[n];
	}

	inline size_t size() {
		return river.size();
	}

	inline void push_back(RiverTile rt) {
		river.push_back(rt);
	}
};

class Player {
public:
	Player();
	bool double_riichi = false;
	bool riichi = false;

	inline bool is_riichi() { return riichi || double_riichi; }

	bool 门清 = true;
	Wind wind;
	bool 亲家;
	bool 振听 = false;
	bool 立直振听 = false;

	bool is振听() { return 振听 || 立直振听; }

	int score;
	std::vector<Tile*> hand;
	River river;
	std::vector<Fulu> 副露s;
	std::string hand_to_string();
	std::string river_to_string();

	std::string to_string();

	bool 一发;
	bool first_round = true;

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

	// 立直后
	std::vector<SelfAction> riichi_get_暗杠(Table* table);
	std::vector<SelfAction> riichi_get_打牌();

	void move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile);
	void remove_from_hand(Tile* tile);

	// 将所有的BaseTile值为tile的四个牌移动到副露区
	void play_暗杠(BaseTile tile);

	// 移动tile到副露中和它basetile相同的刻子中
	void play_加杠(Tile* tile);

	// 将牌移动到牌河（一定没有人吃碰杠）
	// remain指这张牌是不是明面上还在牌河
	void move_from_hand_to_river(Tile* tile, int &number, bool remain, bool fromhand);

	inline void move_from_hand_to_river_log_only(Tile* tile, int &number, bool fromhand) {
		return move_from_hand_to_river(tile, number, false, fromhand);
	}

	inline void move_from_hand_to_river_really(Tile* tile, int& number, bool fromhand) {
		return move_from_hand_to_river(tile, number, true, fromhand);
	}

	void sort_hand();
	void test_show_hand();	
};

// Forward Decl
class Agent;

class Table
{
private:

	int river_counter = 0;

	Tile tiles[N_TILES];
public:

	Agent* agents[4];

	// 翻开了几张宝牌指示牌
	int dora_spec;
	std::vector<Tile*> 宝牌指示牌;
	std::vector<Tile*> 里宝牌指示牌;

	inline std::vector<BaseTile> get_dora() {
		std::vector<BaseTile> doratiles;
		for (int i = 0; i < dora_spec; ++i) {
			doratiles.push_back(get_dora_next(宝牌指示牌[i]->tile));
		}
		return doratiles;
	}

	inline std::vector<BaseTile> get_ura_dora() {
		std::vector<BaseTile> doratiles;
		for (int i = 0; i < dora_spec; ++i) {
			doratiles.push_back(get_dora_next(里宝牌指示牌[i]->tile));
		}
		return doratiles;
	}

	inline int get_remain_kan_tile() {
		auto iter = find(牌山.begin(), 牌山.end(), 宝牌指示牌[0]);
		return iter - 牌山.begin() - 1;
	}

	inline int get_remain_tile() {
		return 牌山.size() - 14;
	}

	Wind 场风 = Wind::East;
	int 庄家; // 庄家
	int n本场 = 0;
	int n立直棒 = 0;
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

	enum ToStringOption : int {
		YAMA = 1 << 0,
		PLAYER = 1 << 1,
		DORA = 1 << 2,
		N_立直棒 = 1 << 3,
		N_本场 = 1 << 4,
		亲家 = 1 << 5,
		REMAIN_TILE = 1 << 6,
	};

	std::string to_string(int option =
		YAMA | PLAYER | DORA | N_立直棒 | N_本场 | 亲家 | REMAIN_TILE);

	int turn;
	
	Action last_action = Action::出牌;
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
		return after_daiminkan() || after_加杠();
	}

	Table(int 庄家 = 0, Agent* p1 = nullptr, Agent* p2 = nullptr, Agent* p3 = nullptr, Agent* p4 = nullptr);
	Table(int 庄家, Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4]);

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> GetValidActions();

	std::vector<SelfAction> GetRiichiActions();

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
#ifndef TABLE_H
#define TABLE_H

#include "Tile.h"
#include "Action.h"
#include "GameLog.h"
#include "GameResult.h"
#include "macro.h"
#include <array>
#include <mutex>
#include <algorithm>

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
	inline std::string to_string() const {
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
	std::string hand_to_string() const;
	std::string river_to_string() const;

	std::string to_string() const;

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
	int dora_spec; // 翻开了几张宝牌指示牌
	std::vector<Tile*> 宝牌指示牌;
	std::vector<Tile*> 里宝牌指示牌;
	std::vector<Tile*> 牌山;

	int remain_岭上牌 = 4;

	// Player players[4];
	std::array<Player, 4> players;
	int turn;
	Action last_action = Action::出牌;
	Wind 场风 = Wind::East;
	int 庄家 = 0; // 庄家
	int n本场 = 0;
	int n立直棒 = 0;

	std::string export_yama();

	inline std::vector<BaseTile> get_dora() const {
		std::vector<BaseTile> doratiles;
		for (int i = 0; i < dora_spec; ++i) {
			doratiles.push_back(get_dora_next(宝牌指示牌[i]->tile));
		}
		return doratiles;
	}

	inline std::vector<BaseTile> get_ura_dora() const {
		std::vector<BaseTile> doratiles;
		for (int i = 0; i < dora_spec; ++i) {
			doratiles.push_back(get_dora_next(里宝牌指示牌[i]->tile));
		}
		return doratiles;
	}

	inline int get_remain_kan_tile() const {
		return remain_岭上牌;
	}

	inline int get_remain_tile() const {
		return int(牌山.size() - 14);
	}

	void init_tiles();
	void init_red_dora_3();
	void shuffle_tiles();
	void init_yama();

	// std::string export_yama();
	// void import_yama(std::string);
	void init_wind();
	
	void _deal(int i_player);
	void _deal(int i_player, int n_tiles);

	void 发牌(int i_player);
	void 发岭上牌(int i_player);

	inline void next_turn() { turn++; turn = turn % 4; }

	GameLog game_log;

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
		YAMA | PLAYER | DORA | N_立直棒 | N_本场 | 亲家 | REMAIN_TILE) const;

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

	inline std::array<int, 4> get_scores() {
		std::array<int, 4> scores;
		for (int i = 0; i < 4; ++i) 
			scores[i] = players[i].score;
		return scores;
	}

	Table() = default;
	Table(int 庄家, Agent* p1 = nullptr, Agent* p2 = nullptr, Agent* p3 = nullptr, Agent* p4 = nullptr);
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

	void test_show_yama_with_王牌();
	void test_show_yama();
	void test_show_player_hand(int i_player);
	void test_show_all_player_hand();
	void test_show_player_info(int i_player);
	void test_show_all_player_info();

	inline void test_show_all() {
		test_show_yama_with_王牌();
		test_show_all_player_info();
		//test_show_open_gamelog();
		//test_show_full_gamelog();
		std::cout << "轮到Player" << turn << std::endl;
	}

	Result GameProcess(bool, std::string = "");

	// The following part is for the manual instead of the automatic.
	// Never mix using GameProcess and using the following functions. 
public:
	enum _Phase_ {
		P1_ACTION, P2_ACTION, P3_ACTION, P4_ACTION,
		P1_RESPONSE, P2_RESPONSE, P3_RESPONSE, P4_RESPONSE,
		P1_抢杠RESPONSE, P2_抢杠RESPONSE, P3_抢杠RESPONSE, P4_抢杠RESPONSE,
		P1_抢暗杠RESPONSE, P2_抢暗杠RESPONSE, P3_抢暗杠RESPONSE, P4_抢暗杠RESPONSE,
		GAME_OVER,
	};

	// These Phases specifies the multithreading cases.
	enum _Phase_MultiThread_ {
		P1_ACTION_MT, P2_ACTION_MT, P3_ACTION_MT, P4_ACTION_MT,
		RESPONSE_MT,
		GAME_OVER_MT,
	};

private:
	std::vector<SelfAction> self_action;
	std::vector<ResponseAction> response_action;

	// specially for multi thread
	std::unordered_map<int, std::vector<ResponseAction>> response_action_mt;
	std::unordered_map<int, ResponseAction> decided_response_action_mt;
	std::mutex lock;
	_Phase_MultiThread_ phase_mt;
	void _action_phase_mt(int selection);
	void _final_response_mt();
	void _from_beginning_mt();

	Result result;
	_Phase_ phase;
	int selection;
	SelfAction selected_action;
	Tile* tile;
	std::vector<ResponseAction> actions; // player actions
	bool FROM_手切摸切;
	Action final_action = Action::pass;
	void _from_beginning();
public:

	// Initialize the game.
	inline void game_init()	{
		init_tiles();
		init_red_dora_3();
		shuffle_tiles();
		init_yama();

		// 每人发13张牌
		_deal(0, 13);
		_deal(1, 13);
		_deal(2, 13);
		_deal(3, 13);
		ALLSORT;

		// 初始化每人自风
		init_wind();

		turn = 庄家;

		game_log.logGameStart(n本场, n立直棒, 庄家, 场风, export_yama(), get_scores());
		_from_beginning();
	}

	inline void tenhou_game_init(
		std::array<std::array<int, 13>, 4> hands,
		std::vector<int> drawtiles,
		std::vector<int> doras,
		std::vector<int> uradoras,
		std::vector<int> kantiles,
		std::array<int, 4> scores,
		int riichi,
		int honba,
		int oya,
		int gamewind
	) {
		using namespace std;
		// init_tiles();
		// init_tiles_as_tenhou_rule

		for (int i = 0; i < N_TILES; ++i) {
			tiles[i].tile = static_cast<BaseTile>(i / 4);
			tiles[i].red_dora = false;
		}

		//init_red_dora_3();
		tiles[BaseTile::_5m * 4].red_dora = true;
		tiles[BaseTile::_5p * 4].red_dora = true;
		tiles[BaseTile::_5s * 4].red_dora = true;
		/* Generate yama with already known message */
		//init_yama();
		vector<Tile*> empty;
		牌山.swap(empty);
		for (int i = 0; i < 4; i++)	{
			for (int j = 0; j < 13; j++) {
				牌山.push_back(&tiles[hands[i][j]]);
			}
		}
		dora_spec = 1;
		for (int i = 0; i < 5; ++i) {
			if (i < doras.size()) 宝牌指示牌[i] = &tiles[doras[i]];
			else 宝牌指示牌[i] = tiles;
		}
		for (int i = 0; i < 5; ++i) {
			if (i < doras.size()) 里宝牌指示牌[i] = &tiles[uradoras[i]];
			else 里宝牌指示牌[i] = tiles;
		}
		for (int i = 0; i < drawtiles.size(); ++i) {
			牌山.push_back(&tiles[drawtiles[i]]);
		}
		for (int i = 0; i < N_TILES - kantiles.size() - 13 * 4 - drawtiles.size(); ++i)
			牌山.push_back(tiles);

		for (int i = 0; i < kantiles.size(); ++i) {
			牌山.push_back(&tiles[kantiles[kantiles.size() - 1 - i]]);
		}
		std::reverse(牌山.begin(), 牌山.end());

		for (int i = 0; i < 4; ++i)
		{
			players[i].score = scores[i];
		}
		n立直棒 = riichi;
		n本场 = honba;
		庄家 = oya;
		场风 = (Wind)gamewind;

		_deal(0, 13);
		_deal(1, 13);
		_deal(2, 13);
		_deal(3, 13);

		init_wind();
		turn = 庄家;
		game_log.logGameStart(n本场, n立直棒, 庄家, 场风, export_yama(), get_scores());
		_from_beginning();
	}

	void game_init_with_metadata(
		std::unordered_map<std::string, std::string> metadata);
	
	// Get the phase of the game
	inline int get_phase() { return (int)phase; }

	// For AI Env
	static std::array<float, 29> generate_state_vector_features_frost2(
		int turn,
		int yama_len,
		bool first_round,
		int dora_spec,
		int player_no,
		int oya,
		std::array<bool, 4> riichi,
		std::array<bool, 4> double_riichi,
		std::array<bool, 4> ippatsu,
		std::array<int, 4> hand,
		std::array<bool, 4> mentsun,
		bool agari	
	);
	static std::array<float, 34 * 55> generate_state_matrix_features_frost2();

	std::array<float, 29> get_state_vector_features_frost2(int playerNo);
	std::array<float, 34 * 55> get_state_matrix_features_frost2(int playerNo);

	std::array<float, 29> get_next_aval_states_vector_features_frost2(int playerNo);
	std::array<float, 34 * 55> get_state_matrix_features_frost2(int playerNo);

	// Make a selection and game moves on.
	void make_selection(int selection);

	// Multithread selection control, return the status.
	int get_phase_mt() const;
	bool make_selection_mt(int player, int selection);
	const std::vector<SelfAction> get_self_actions_mt(int player);
	const std::vector<ResponseAction> get_response_actions_mt(int player);
	bool should_i_make_selection_mt(int player);
	
	// Get Information. Return the table itself.
	inline Table* get_info() { return this; }

	// When a player needs response, it can refer to the selection made by the "self-action" player
	inline SelfAction get_full_selected_action() { return selected_action; }
	inline Action get_selected_action() { return selected_action.action; }	
	inline Tile* get_selected_action_tile() { return tile; };

	// Tells that who has to make the selection.
	inline int who_make_selection() { return (get_phase() - Table::P1_ACTION) % 4; }
	
	inline Result get_result() { return result; }
	
	inline std::vector<SelfAction> get_self_actions() { return self_action; }
	inline std::vector<ResponseAction> get_response_actions() { return response_action; }

};

#endif
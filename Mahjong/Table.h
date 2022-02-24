#ifndef TABLE_H
#define TABLE_H

#include "Tile.h"
#include "Action.h"
#include "GameLog.h"
#include "GameResult.h"
#include "macro.h"
#include "Player.h"
#include <array>

constexpr auto N_TILES = (34*4);
constexpr auto INIT_SCORE = 25000;

// Forward Decl
class Agent;

class Table
{
public:
	int river_counter = 0;
	Tile tiles[N_TILES];
	Agent* agents[4] = { nullptr };
	int dora_spec = 1; // 翻开了几张宝牌指示牌
	std::vector<Tile*> 宝牌指示牌;
	std::vector<Tile*> 里宝牌指示牌;
	
	// 牌山的起始是岭上牌(0,1,2,3)
	// 然后标记宝牌和ura的位置(5,7,9,11,13)、(4,6,8,10,12)
	// 初始情况dora_spec = 1，每次翻宝牌只需要dora_spec++
	// 杠的时候所有牌在vector牌山中位置变化的
	// 并不会影响到宝牌/ura的位置，因为它们一开始就被标记过了
	// 当牌山.size() <= 14的时候结束游戏
	std::vector<Tile*> 牌山; 
	
	std::array<Player, 4> players;
	int turn = 0;
	BaseAction last_action = BaseAction::出牌;
	Wind 场风 = Wind::East;
	int 庄家 = 0; // 庄家
	int n本场 = 0;
	int n立直棒 = 0;
	GameLog fullGameLog;

public:
	Table() = default;
	Table(int 庄家, Agent* p1 = nullptr, Agent* p2 = nullptr, Agent* p3 = nullptr, Agent* p4 = nullptr);
	Table(int 庄家, Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4]);

	std::vector<BaseTile> get_dora() const;
	std::vector<BaseTile> get_ura_dora() const;

	// 通过这种方式判断杠了几次，相对于判断dora个数更为准确
	inline int get_remain_kan_tile() const 
	{ return int(std::find(牌山.begin(), 牌山.end(), 宝牌指示牌[0]) - 牌山.begin()); }

	inline int get_remain_tile() const 
	{ return int(牌山.size() - 14);	}

	void init_tiles();
	void init_red_dora_3();
	void shuffle_tiles();
	void init_yama();
	void init_dora();
	void import_yama(std::string yama);
	void import_yama(std::vector<int> yama);
	std::string export_yama();
	void init_wind();
	void deal_tile(int i_player);
	void deal_tile(int i_player, int n_tiles);
	void deal_tile_岭上(int i_player);
	void deal_tenhou_style();

	void 发牌(int i_player);
	void 发岭上牌(int i_player);

	void next_turn(int nextturn);

	enum ToStringOption : int {
		YAMA = 1 << 0,
		PLAYER = 1 << 1,
		DORA = 1 << 2,
		N_立直棒 = 1 << 3,
		N_本场 = 1 << 4,
		亲家 = 1 << 5,
		REMAIN_TILE = 1 << 6,
	};
	std::string to_string(int option = YAMA | PLAYER | DORA | N_立直棒 | N_本场 | 亲家 | REMAIN_TILE) const;

	inline bool after_chipon() { return last_action == BaseAction::吃 || last_action == BaseAction::碰; }
	inline bool after_daiminkan() {	return last_action == BaseAction::杠; }
	inline bool after_ankan() {	return last_action == BaseAction::暗杠; }
	inline bool after_加杠() { return last_action == BaseAction::加杠; }
	inline bool after_杠() { return after_daiminkan() || after_加杠(); }
	std::array<int, 4> get_scores();

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> GetSelfActions();
	std::vector<SelfAction> GetRiichiSelfActions();

	// 根据turn打出的tile，可以做出的决定
	std::vector<ResponseAction> GetResponseActions(int player, Tile* tile, bool);

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
	void test_show_open_gamelog();
	void test_show_full_gamelog();

	inline void test_show_all() {
		test_show_yama_with_王牌();
		test_show_all_player_info();		
		std::cout << "轮到Player" << turn << std::endl;
	}

	Result GameProcess(bool, std::string = "");

public:
	// ---------------------Manual Mode------------------------------
	// The following part is for the manual instead of the automatic.
	// Never mix using GameProcess and using the following functions.
	// -------------------------------------------------------------- 
	enum PhaseEnum {
		P1_ACTION, P2_ACTION, P3_ACTION, P4_ACTION,
		P1_RESPONSE, P2_RESPONSE, P3_RESPONSE, P4_RESPONSE,
		P1_抢杠RESPONSE, P2_抢杠RESPONSE, P3_抢杠RESPONSE, P4_抢杠RESPONSE,
		P1_抢暗杠RESPONSE, P2_抢暗杠RESPONSE, P3_抢暗杠RESPONSE, P4_抢暗杠RESPONSE,
		GAME_OVER,
	};
	std::vector<SelfAction> self_actions;
	std::vector<ResponseAction> response_actions;

	Result result;
	PhaseEnum phase = GAME_OVER; // initialized to GAME_OVER to avoid illegal gameplay.
	int selection = -1;	// initialized to -1 to avoid illegal gameplay.
	SelfAction selected_action;
	Tile* tile = nullptr;
	std::vector<ResponseAction> actions; // response actions
	bool FROM_手切摸切 = false; // global variable for river log
	BaseAction final_action = BaseAction::pass;
	
	void from_beginning();

	// Initialize the game.
	void game_init();
	void game_init_for_replay(std::vector<int> yama, std::vector<int> init_scores, int 立直棒, int 本场, int 场风, int 亲家);

	void game_init_with_metadata(std::unordered_map<std::string, std::string> metadata);
	
	// Get the phase of the game
	inline int get_phase() const { return (int)phase; }

	// Make a selection and game moves on.
	void make_selection(int selection);

	// Get Information. Return the table itself. (For python wrapper)
	inline Table* get_info() { return this; }

	// When a player needs response, it can refer to the selection made by the "self-action" player
	inline SelfAction get_selected_action() const { return selected_action; }
	inline BaseAction get_selected_base_action() const { return selected_action.action; }
	inline Tile* get_selected_action_tile() { return tile; };

	// Tell that who has to make the selection.
	inline int who_make_selection() const { return (get_phase() - Table::P1_ACTION) % 4; }
	
	inline Result get_result() const { return result; }	
	inline std::vector<SelfAction> get_self_actions() const { return self_actions; }
	inline std::vector<ResponseAction> get_response_actions() const { return response_actions; }

};

#endif
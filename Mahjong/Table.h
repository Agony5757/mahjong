#ifndef TABLE_H
#define TABLE_H

#include "Tile.h"
#include "Action.h"
#include "GameLog.h"
#include "GameResult.h"
#include "macro.h"
#include "Player.h"
#include <array>

constexpr auto N_TILES = (34 * 4);

class Table
{
public:
	int river_counter = 0;
	Tile tiles[N_TILES];
	int n_active_dora = 1; // 翻开了几张宝牌指示牌
	std::vector<Tile*> dora_indicator;
	std::vector<Tile*> uradora_indicator;
	
	// 牌山的起始是岭上牌(0,1,2,3)
	// 然后标记宝牌和ura的位置(5,7,9,11,13)、(4,6,8,10,12)
	// 初始情况dora_spec = 1，每次翻宝牌只需要dora_spec++
	// 杠的时候所有牌在vector牌山中位置变化的
	// 并不会影响到宝牌/ura的位置，因为它们一开始就被标记过了
	// 当牌山.size() <= 14的时候结束游戏
	std::vector<Tile*> yama; 
	
	std::array<Player, 4> players;
	int turn = 0;
	BaseAction last_action = BaseAction::Discard;
	Wind game_wind = Wind::East;
	int oya = 0; // oya
	int honba = 0;
	int kyoutaku = 0;
	GameLog gamelog;

	Table() = default;

	inline void new_dora() { n_active_dora++; }
	std::vector<BaseTile> get_dora() const;
	std::vector<BaseTile> get_ura_dora() const;

	// 通过这种方式判断杠了几次，相对于判断dora个数更为准确
	inline int get_remain_kan_tile() const 
	{ return int(std::find(yama.begin(), yama.end(), dora_indicator[0]) - yama.begin() - 1); }

	inline int get_remain_tile() const 
	{ return int(yama.size() - 14);	}

	void init_tiles();
	void init_red_dora_3();
	void shuffle_tiles();
	void init_yama();
	void init_dora();
	void init_before_playing();
	void import_yama(std::string yama);
	void import_yama(std::vector<int> yama);
	std::string export_yama();
	void init_wind();
	void draw(int i_player);
	void draw(int i_player, int n_tiles);
	void draw_rinshan(int i_player);
	void draw_tenhou_style();

	void draw_normal(int i_player);
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

	inline bool after_chipon() { return last_action == BaseAction::Chi || last_action == BaseAction::Pon; }
	inline bool after_daiminkan() {	return last_action == BaseAction::Kan; }
	inline bool after_ankan() {	return last_action == BaseAction::AnKan; }
	inline bool after_kakan() { return last_action == BaseAction::KaKan; }
	inline bool after_kan() { return after_daiminkan() || after_ankan(); }
	std::array<int, 4> get_scores();

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> generate_self_actions();
	std::vector<SelfAction> generate_riichi_self_actions();

	// 根据turn打出的tile，可以做出的决定
	std::vector<ResponseAction> generate_response_actions(int player, Tile* tile, bool);

	// 根据turn打出的tile，可以做出的抢杠决定
	std::vector<ResponseAction> generate_chanankan_response_actions(int player, Tile* tile);

	// 根据turn打出的tile，可以做出的抢杠决定
	std::vector<ResponseAction> generate_chankan_response_actions(int player, Tile* tile);

public:
	// ---------------------Manual Mode------------------------------
	// The following part is for the manual instead of the automatic.
	// Never mix using GameProcess and using the following functions.
	// -------------------------------------------------------------- 
	enum PhaseEnum {
		P1_ACTION, P2_ACTION, P3_ACTION, P4_ACTION,
		P1_RESPONSE, P2_RESPONSE, P3_RESPONSE, P4_RESPONSE,
		P1_CHANKAN_RESPONSE, P2_CHANKAN_RESPONSE, P3_CHANKAN_RESPONSE, P4_CHANKAN_RESPONSE,
		P1_CHANANKAN_RESPONSE, P2_CHANANKAN_RESPONSE, P3_CHANANKAN_RESPONSE, P4_CHANANKAN_RESPONSE,
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
	// bool FROM_手切摸切 = false; // global variable for river log
	BaseAction final_action = BaseAction::Pass;
	
	void from_beginning();

	// Initialize the game.
	void game_init();
	void game_init_for_replay(std::vector<int> yama, std::vector<int> init_scores, int kyoutaku, int honba, int game_wind, int oya);

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
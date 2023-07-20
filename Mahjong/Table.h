#ifndef TABLE_H
#define TABLE_H

#include "Tile.h"
#include "Action.h"
#include "GameLog.h"
#include "GameResult.h"
#include "macro.h"
#include "Player.h"
#include "fmt/os.h"
#include <array>

namespace_mahjong

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

	/* For debug */
	int write_log_mode;
	std::vector<int> yama_log;
	std::string log_buffer_prefix;
	std::vector<int> selection_log;

	/* Set seed (set_seed) before init*/
	bool use_seed = false;
	int seed = 0;

public:
	Table() = default;

	void new_dora();
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
	void import_yama(const std::vector<int> &yama);
	std::string export_yama();
	void init_wind();

	// game init draw with tenhou style
	void draw_tenhou_style();

	// Draw from the head (the normal sequence)
	void draw_normal(int i_player);

	// Draw from the head without record.
	// This is for initializing the game
	void draw_normal_no_record(int i_player);

	// Draw n tiles from the head (the normal sequence)
	// **No Record**, implemented by ``draw_normal_no_record''
	void draw_n_normal(int i_player, int n_tiles);

	// Draw from the tail (from rinshan)
	void draw_rinshan(int i_player);

	void next_turn(int nextturn);

	/* debug mode 
	   0: no debug
	   1: debug by write buffer
	   2: debug by write stdout	
	*/
	static const int debug_close = 0;
	static const int debug_buffer = 1;
	static const int debug_stdout = 2;
	inline void set_debug_mode(int debug_mode) 
	{
		write_log_mode = debug_mode; 
	}
	inline void set_seed(int new_seed) 
	{ 
		seed = new_seed; 
		use_seed = true; 
	}
	// inline int get_seed() { return seed; }
	inline std::string get_debug_replay()
	{
		std::string ret;
		ret += fmt::format("{}", log_buffer_prefix);
		for (auto selection : selection_log) {
			ret += fmt::format("table.make_selection({});\n", selection);
		}
		return ret;
	}
	inline void print_debug_replay()
	{
		fmt::print("{}", log_buffer_prefix);
		for (auto selection : selection_log) {
			fmt::print("table.make_selection({});\n", selection);
		}
	}
	inline void debug_replay_init()
	{
		if (write_log_mode) {
			auto init_score = {
				players[0].score,
				players[1].score,
				players[2].score,
				players[3].score,
			};
			log_buffer_prefix = fmt::format("Table table;\ntable.game_init_for_replay({}, {}, {}, {}, {}, {});\n",
				vec2str(yama_log), vec2str(init_score), kyoutaku, honba, game_wind, oya);
			selection_log.reserve(512); // avoid reallocation
			if (write_log_mode == debug_stdout)
				fmt::print("{}", log_buffer_prefix);
		}
	}
	inline void debug_selection_record()
	{
		selection_log.push_back(selection);
		if (write_log_mode == debug_stdout)
			fmt::print("table.make_selection({})", selection);
	}

	std::string to_string() const;

	inline bool after_chipon() { return last_action == BaseAction::Chi || last_action == BaseAction::Pon; }
	inline bool after_daiminkan() {	return last_action == BaseAction::Kan; }
	inline bool after_ankan() {	return last_action == BaseAction::AnKan; }
	inline bool after_kakan() { return last_action == BaseAction::KaKan; }
	inline bool after_kan() { return after_daiminkan() || after_ankan(); }
	std::array<int, 4> get_scores();

	// 因为一定是turn所在的player行动，所以不需要输入playerID
	std::vector<SelfAction> _generate_self_actions();
	std::vector<SelfAction> _generate_riichi_self_actions();

	// 根据turn打出的tile，可以做出的决定
	std::vector<ResponseAction> _generate_response_actions(int player, Tile* tile, bool);

	// 根据turn打出的tile，可以做出的抢杠决定
	std::vector<ResponseAction> _generate_chanankan_response_actions(int player, Tile* tile);

	// 根据turn打出的tile，可以做出的抢杠决定
	std::vector<ResponseAction> _generate_chankan_response_actions(int player, Tile* tile);

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
		GAME_OVER, UNINITIALIZED,
	};
	std::vector<SelfAction> self_actions;
	std::vector<ResponseAction> response_actions;

	Result result;
	PhaseEnum phase = UNINITIALIZED; // initialized to UNINITIALIZED to avoid illegal gameplay.
	int selection = -1;	// initialized to -1 to avoid illegal gameplay.
	SelfAction selected_action;
	Tile* tile = nullptr;
	std::vector<ResponseAction> actions; // response actions
	// bool FROM_手切摸切 = false; // global variable for river log
	BaseAction final_action = BaseAction::Pass;
	
	void from_beginning();

	// Initialize the game.
	void game_init();
	void game_init_for_replay(const std::vector<int> &yama, const std::vector<int> &init_scores, int 立直棒, int 本场, int 场风, int 亲家);
	void game_init_with_metadata(std::unordered_map<std::string, std::string> metadata);
	
	// Get the phase of the game
	inline int get_phase() const { return (int)phase; }

	// Make a selection from tiles
	int get_selection_from_action_tile(BaseAction action_type, const std::vector<Tile*> &tiles) const;
	void make_selection_from_action_tile(BaseAction action, const std::vector<Tile*>& tiles);
	int get_selection_from_action_basetile(BaseAction action_type, const std::vector<BaseTile>& tiles, bool use_red_dora) const;
	void make_selection_from_action_basetile(BaseAction action, const std::vector<BaseTile> &tiles, bool use_red_dora);
	inline int get_selection_from_action_basetile_int(BaseAction action, const std::vector<int> &tiles, bool use_red_dora)
	{
		std::vector<BaseTile> tiles_basetile;
		tiles_basetile.resize(tiles.size());
		for (size_t i = 0; i < tiles_basetile.size();++i){
			tiles_basetile[i] = BaseTile(tiles[i]);
		}
		return get_selection_from_action_basetile(action, tiles_basetile, use_red_dora);
	}
	inline void make_selection_from_action_basetile_int(BaseAction action, const std::vector<int>& tiles, bool use_red_dora)
	{
		int idx = get_selection_from_action_basetile_int(action, tiles, use_red_dora);
		if (idx >= 0)
			make_selection(idx);
		else {
			throw std::runtime_error(fmt::format("Cannot locate action with action = {}", action));
		}
	}

	// Make a selection and game moves on.
	void make_selection(int selection);

	// handle the "selection" variable
	// if self action, then assign this->selected_action
	// if response, then push_back this->actions
	void _check_selection();

	void _handle_self_action();
	void _handle_response_action();
	void _handle_response_chankan_action();
	void _handle_response_chanankan_action();
	void _handle_response_final_execution();
	void _handle_response_final_chankan_execution();
	void _handle_response_final_chanankan_execution();

	// Get Information. Return the table itself. (For python wrapper)
	inline Table* get_info() { return this; }

	// When a player needs response, it can refer to the selection made by the "self-action" player
	inline SelfAction get_selected_action() const { return selected_action; }
	inline BaseAction get_selected_base_action() const { return selected_action.action; }
	inline Tile* get_selected_action_tile() { return tile; };

	// Tell that who has to make the selection.
	inline int who_make_selection() const { return (get_phase() - Table::P1_ACTION) % 4; }
	inline bool is_self_acting() const { return get_phase() <= Table::P4_ACTION; }
	inline bool is_over() const { return get_phase() == Table::GAME_OVER; }

	inline Result get_result() const { return result; }	
	inline std::vector<SelfAction> get_self_actions() const { return self_actions; }
	inline std::vector<ResponseAction> get_response_actions() const { return response_actions; }
};

namespace_mahjong_end

#endif
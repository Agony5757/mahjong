#ifdef __GNUC__
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-value"
#endif

#include "Table.h"
#include "ScoreCounter.h"
#include "GamePlay.h"
#include "tenhou.h"
#include "EncodingPy.h"
#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "pybind11/complex.h"
#include "pybind11/functional.h"
#include "pybind11/operators.h"

using_mahjong;
using namespace std;
using namespace pybind11::literals;
namespace py = pybind11;

PYBIND11_MODULE(MahjongPyWrapper, m)
{
	m.doc() = "An essential Japanese riichi mahjong environment.";

	py::enum_<BaseTile>(m, "BaseTile", "Enum of 34 Mahjong tile types (0-33).")
		.value("_1m", BaseTile::_1m)
		.value("_2m", BaseTile::_2m)
		.value("_3m", BaseTile::_3m)
		.value("_4m", BaseTile::_4m)
		.value("_5m", BaseTile::_5m)
		.value("_6m", BaseTile::_6m)
		.value("_7m", BaseTile::_7m)
		.value("_8m", BaseTile::_8m)
		.value("_9m", BaseTile::_9m)

		.value("_1s", BaseTile::_1s)
		.value("_2s", BaseTile::_2s)
		.value("_3s", BaseTile::_3s)
		.value("_4s", BaseTile::_4s)
		.value("_5s", BaseTile::_5s)
		.value("_6s", BaseTile::_6s)
		.value("_7s", BaseTile::_7s)
		.value("_8s", BaseTile::_8s)
		.value("_9s", BaseTile::_9s)

		.value("_1p", BaseTile::_1p)
		.value("_2p", BaseTile::_2p)
		.value("_3p", BaseTile::_3p)
		.value("_4p", BaseTile::_4p)
		.value("_5p", BaseTile::_5p)
		.value("_6p", BaseTile::_6p)
		.value("_7p", BaseTile::_7p)
		.value("_8p", BaseTile::_8p)
		.value("_9p", BaseTile::_9p)

		.value("east", BaseTile::_1z)
		.value("_1z", BaseTile::_1z)
		.value("south", BaseTile::_2z)
		.value("_2z", BaseTile::_2z)
		.value("west", BaseTile::_3z)
		.value("_3z", BaseTile::_3z)
		.value("north", BaseTile::_4z)
		.value("_4z", BaseTile::_4z)
		.value("haku", BaseTile::_5z)
		.value("_5z", BaseTile::_5z)
		.value("hatsu", BaseTile::_6z)
		.value("_6z", BaseTile::_6z)
		.value("chu", BaseTile::_7z)
		.value("_7z", BaseTile::_7z)
		;

	py::class_<CallGroup>(m, "CallGroup", "A called meld (chi/pon/kan) group.")
		.def_readonly("type", &CallGroup::type, "Action type of this call.")
		.def_readonly("tiles", &CallGroup::tiles, "Tiles in the called meld.")
		.def_readonly("take", &CallGroup::take, "Tile taken from another player's discard.")
		.def("to_string", &CallGroup::to_string, "Return a string representation.")
		;

	m.def("CallGroupToString", [](const CallGroup &CallGroup) {return py::bytes(CallGroup.to_string()); },
		"Convert a CallGroup to a byte string.");

	py::class_<Tile>(m, "Tile", "A Mahjong tile with identity and red dora info.")
		.def_readonly("tile", &Tile::tile, "BaseTile type of this tile.")
		.def_readonly("red_dora", &Tile::red_dora, "Whether this tile is a red dora (aka-dora).")
		.def_readonly("id", &Tile::id, "Unique tile ID (0-135).")
		.def("to_string", &Tile::to_string, "Return a string representation.")
		;

	m.def("TileToString", [](const Tile *tile) {return py::bytes(tile->to_string()); },
		"Convert a Tile to a byte string.");

	py::class_<River>(m, "River", "A player's discard pool (river).")
		.def_readonly("river", &River::river, "List of RiverTiles in the discard pool.")
		.def("size", &River::size, "Return the number of discarded tiles.")
		.def("to_string", &River::to_string, "Return a string representation.")
		;

	m.def("RiverToString", [](const River& river) {return py::bytes(river.to_string()); },
		"Convert a River to a byte string.");

	py::class_<RiverTile>(m, "RiverTile", "A tile in a player's discard pool.")
		.def_readonly("tile", &RiverTile::tile, "BaseTile type.")
		.def_readonly("number", &RiverTile::number, "Order number in the river.")
		.def_readonly("riichi", &RiverTile::riichi, "Whether this discard declared riichi.")
		.def_readonly("remain", &RiverTile::remain, "Whether this tile is still in play.")
		.def_readonly("fromhand", &RiverTile::fromhand, "Whether discarded from hand (vs. drawn).")
		;

	py::enum_<Wind>(m, "Wind", "Player wind (seat) enum.")
		.value("East", Wind::East)
		.value("South", Wind::South)
		.value("West", Wind::West)
		.value("North", Wind::North)
		;

	py::enum_<BaseAction>(m, "BaseAction", "Enum of base action types in Mahjong.")
		.value("Pass", BaseAction::Pass)
		.value("Chi", BaseAction::Chi)
		.value("Pon", BaseAction::Pon)
		.value("Kan", BaseAction::Kan)
		.value("Ron", BaseAction::Ron)

		.value("ChanAnKan", BaseAction::ChanAnKan)
		.value("ChanKan", BaseAction::ChanKan)

		.value("AnKan", BaseAction::AnKan)
		.value("KaKan", BaseAction::KaKan)
		.value("Discard", BaseAction::Discard)
		.value("Riichi", BaseAction::Riichi)
		.value("Tsumo", BaseAction::Tsumo)
		.value("Kyushukyuhai", BaseAction::Kyushukyuhai)
		;

	py::class_<SelfAction>(m, "SelfAction", "An available self-action (draw phase) for a player.")
		.def_readonly("action", &SelfAction::action, "The BaseAction type.")
		.def_readonly("correspond_tiles", &SelfAction::correspond_tiles, "Tiles involved in this action.")
		.def("to_string", &SelfAction::to_string, "Return a string representation.")
		;

	m.def("SelfActionToString", [](const SelfAction &sa) {return py::bytes(sa.to_string()); },
		"Convert a SelfAction to a byte string.");

	py::class_<ResponseAction>(m, "ResponseAction", "An available response action for a player after another's discard/kan.")
		.def_readonly("action", &ResponseAction::action, "The BaseAction type.")
		.def_readonly("correspond_tiles", &ResponseAction::correspond_tiles, "Tiles involved in this action.")
		.def("to_string", &ResponseAction::to_string, "Return a string representation.")
		;

	m.def("ResponseActionToString", [](const ResponseAction &ra) {return py::bytes(ra.to_string()); },
		"Convert a ResponseAction to a byte string.");

	py::class_<Player>(m, "Player", "A Mahjong player with hand, river, and game state.")
		// 成员变量们
		.def_readonly("double_riichi", &Player::double_riichi, "Whether double riichi was declared.")
		.def_readonly("riichi", &Player::riichi, "Whether riichi was declared.")
		.def_readonly("menzen", &Player::menzen, "Whether the hand is closed (menzenchin).")
		.def_readonly("wind", &Player::wind, "Player's seat wind.")
		.def_readonly("oya", &Player::oya, "Whether this player is the dealer (oya).")
		.def_readonly("toujun_furiten", &Player::furiten_round, "Whether in temporary furiten this round.")
		.def_readonly("sutehai_furiten", &Player::furiten_river, "Whether in sutehai (discard) furiten.")
		.def_readonly("riichi_furiten", &Player::furiten_riichi, "Whether in riichi furiten.")
		.def_readonly("score", &Player::score, "Current score (points).")
		.def_readonly("hand", &Player::hand, "Tiles in the player's hand.")
		.def_readonly("ippatsu", &Player::ippatsu, "Whether ippatsu is possible this turn.")
		.def_readonly("first_round", &Player::first_round, "Whether this is the first go-around.")
		.def_readonly("atari_tiles", &Player::atari_tiles, "Tiles that would complete a winning hand (tenpai).")

		// 函数们
		.def("get_fuuros", &Player::get_fuuros, "Get the list of called melds (fuuro).")
		.def("get_river", &Player::get_river, "Get the player's discard pool (river).")
		.def("is_tenpai", &Player::is_tenpai, "Check if the player is in tenpai (ready to win).")
		.def("is_menzen", &Player::is_menzen, "Check if the hand is closed.")
		.def("is_riichi", &Player::is_riichi, "Check if the player has declared riichi.")
		.def("is_furiten", &Player::is_furiten, "Check if the player is in any furiten state.")
		.def("to_string", &Player::to_string, "Return a string representation of the player state.")
		.def("hand_to_string", &Player::to_string, "Return a string representation of the hand.")
		.def("tenpai_to_string", &Player::tenpai_to_string, "Return a string of tenpai (winning) tiles.")
		;

	m.def("PlayerToString", [](const Player& player) {return py::bytes(player.to_string()); },
		"Convert a Player to a byte string.");

	py::class_<Table>(m, "Table", "Central game state manager for a Mahjong game.")
		.def(py::init<>(), "Create a new Table with default state.")

		// 函数们
		.def("game_init", &Table::game_init,
			"Initialize a new game with default settings.")
		.def("game_init_with_config", &Table::game_init_with_config,
			"Initialize a game with custom configuration.",
			py::arg("yama"), py::arg("init_scores"), py::arg("kyoutaku"),
			py::arg("honba"), py::arg("game_wind"), py::arg("oya"))
		.def("game_init_with_metadata", &Table::game_init_with_metadata,
			"Initialize a game using metadata string.")
		.def("reshuffle_yama", &Table::reshuffle_yama,
			"Reshuffle the tile wall (yama).")
		.def("get_phase", &Table::get_phase,
			"Get the current game phase (see PhaseEnum).")
		.def("make_selection", &Table::make_selection,
			"Execute the action at the given index in self/response actions.",
			py::arg("selection"))
		.def("get_selection_from_action_tile", &Table::get_selection_from_action_tile,
			"Find action index matching the given action type and tiles.",
			py::arg("action"), py::arg("correspond_tiles"))
		.def("make_selection_from_action_tile", &Table::make_selection_from_action_tile,
			"Execute the action matching the given action type and tiles.",
			py::arg("action"), py::arg("correspond_tiles"))
		.def("get_selection_from_action_basetile", &Table::get_selection_from_action_basetile_int,
			"Find action index matching the given action type and basetiles.",
			py::arg("action"), py::arg("correspond_tiles"), py::arg("use_red_dora"))
		.def("make_selection_from_action_basetile", &Table::make_selection_from_action_basetile_int,
			"Execute the action matching the given action type and basetiles.",
			py::arg("action"), py::arg("correspond_tiles"), py::arg("use_red_dora"))
		.def("get_info", &Table::get_info, py::return_value_policy::reference,
			"Get game info string.")
		.def("get_selected_base_action", &Table::get_selected_base_action,
			"Get the BaseAction of the last selected action.")
		.def("who_make_selection", &Table::who_make_selection,
			"Get the player ID who should make the next selection.")
		.def("get_selected_action_tile", &Table::get_selected_action_tile, py::return_value_policy::reference,
			"Get the tile of the last selected action.")
		.def("get_selected_action", &Table::get_selected_action,
			"Get the currently selected action object.")
		.def("get_result", &Table::get_result,
			"Get the game result (only valid after GAME_OVER phase).")

		// change to reference will cause error (why?)
		.def("get_self_actions", &Table::get_self_actions,
			"Get the list of available self-actions for the current player.")
		.def("get_response_actions", &Table::get_response_actions,
			"Get the list of available response-actions for the current player.")

		.def("set_seed", &Table::set_seed,
			"Set the random seed for tile shuffling.", py::arg("seed"))
		.def("set_debug_mode", &Table::set_debug_mode,
			"Enable debug mode (1 or 2) for replayable logs.", py::arg("debug_mode"))
		.def("print_debug_replay", &Table::print_debug_replay,
			"Print replayable debug code to stdout.")
		.def("get_debug_replay", &Table::get_debug_replay,
			"Get replayable debug code as a string.")

		// 成员变量们
		.def_readonly("n_active_dora", &Table::n_active_dora, "Number of active dora indicators.")
		.def_readonly("dora_indicator", &Table::dora_indicator, "List of dora indicator tiles.")
		.def_readonly("uradora_indicator", &Table::uradora_indicator, "List of uradora indicator tiles.")
		.def_readonly("yama", &Table::yama, "The tile wall (remaining draw pile).")
		.def_readonly("players", &Table::players, "List of 4 Player objects.")
		.def_readonly("turn", &Table::turn, "Current turn number.")
		.def_readonly("last_action", &Table::last_action, "The last action taken.")
		.def_readonly("game_wind", &Table::game_wind, "Current game wind.")
		.def_readonly("oya", &Table::oya, "Current dealer (oya) player ID.")
		.def_readonly("honba", &Table::honba, "Number of repeat counters (honba).")
		.def_readonly("riichibo", &Table::kyoutaku, "Number of riichi deposit sticks on the table.")

		// 辅助函数们
		.def("get_dora", &Table::get_dora, "Get the list of active dora tiles.")
		.def("get_ura_dora", &Table::get_ura_dora, "Get the list of uradora tiles (revealed after riichi win).")
		.def("get_remain_kan_tile", &Table::get_remain_kan_tile, "Get remaining kan draw tiles count.")
		.def("get_remain_tile", &Table::get_remain_tile, "Get remaining tiles in the wall.")
		.def("to_string", static_cast<std::string(Table::*)() const>(&Table::to_string),
			"Return a string representation of the table state.")
		;

	m.def("TableToString", [](const Table& table) {return py::bytes(table.to_string()); },
		"Convert a Table to a byte string.");

	py::enum_<ResultType>(m, "ResultType", "Enum of game result types.")
		.value("RonAgari", ResultType::RonAgari)
		.value("TsumoAgari", ResultType::TsumoAgari)
		.value("NoTileRyuuKyoku", ResultType::Ryukyouku_Notile)
		.value("NagashiMangan", ResultType::NagashiMangan)
		.value("Ryukyouku_Interval_9Hai", ResultType::Ryukyouku_Interval_9Hai)
		.value("Ryukyouku_Interval_4Wind", ResultType::Ryukyouku_Interval_4Wind)
		.value("Ryukyouku_Interval_4Riichi", ResultType::Ryukyouku_Interval_4Riichi)
		.value("Ryukyouku_Interval_4Kan", ResultType::Ryukyouku_Interval_4Kan)
		.value("Ryukyouku_Interval_3Ron", ResultType::Ryukyouku_Interval_3Ron)
		;

	py::class_<Result>(m, "Result", "Game result containing scores, winners, and losers.")
		.def_readonly("result_type", &Result::result_type, "Type of game result (ron, tsumo, ryuukyoku).")
		.def_readonly("results", &Result::results, "Detailed counter results for each winner.")
		.def_readonly("score", &Result::score, "Final scores for all 4 players.")
		.def_readonly("winner", &Result::winner, "List of winner player IDs.")
		.def_readonly("loser", &Result::loser, "List of loser player IDs.")
		.def_readonly("n_riichibo", &Result::n_riichibo, "Number of riichi sticks collected.")
		.def_readonly("n_honba", &Result::n_honba, "Number of honba counters.")
		.def_readonly("renchan", &Result::renchan, "Whether the dealer continues (renchan).")
		.def("to_string", &Result::to_string, "Return a string representation.")
		;

	py::enum_<Yaku>(m, "Yaku", "Enum of Mahjong yaku (scoring patterns).")
		.value("NoYaku", Yaku::None)

		.value("Riichi", Yaku::Riichi)
		.value("Tanyao", Yaku::Tanyao)
		.value("Menzentsumo", Yaku::Menzentsumo)
		.value("SelfWind_East", Yaku::Jikaze_Ton)
		.value("SelfWind_South", Yaku::Jikaze_Nan)
		.value("SelfWind_West", Yaku::Jikaze_Sha)
		.value("SelfWind_North", Yaku::Jikaze_Pei)
		.value("GameWind_East", Yaku::Bakaze_Ton)
		.value("GameWind_South", Yaku::Bakaze_Nan)
		.value("GameWind_West", Yaku::Bakaze_Sha)
		.value("GameWind_North", Yaku::Bakaze_Pei)
		.value("Yakuhai_haku", Yaku::Yakuhai_Haku)
		.value("Yakuhai_hatsu", Yaku::Yakuhai_Hatsu)
		.value("Yakuhai_chu", Yaku::Yakuhai_Chu)
		.value("Pinfu", Yaku::Pinfu)
		.value("Yiipeikou", Yaku::Ippeikou)
		.value("Chankan", Yaku::Chankan)
		.value("Rinshankaihou", Yaku::Rinshankaihou)
		.value("Haitiraoyue", Yaku::Haiteiraoyue)
		.value("Houtiraoyui", Yaku::Houteiraoyu)
		.value("Ippatsu", Yaku::Ippatsu)
		.value("Dora", Yaku::Dora)
		.value("UraDora", Yaku::Uradora)
		.value("AkaDora", Yaku::Akadora)
		.value("Chantai_", Yaku::Honchantaiyaochu_Naki)
		.value("Ikkitsuukan_", Yaku::Ikkitsuukan_Naki)
		.value("Sanshokudoujun_", Yaku::Sanshokudoujun_Naki)

		.value("DoubleRiichi", Yaku::Dabururiichi)
		.value("Sanshokudoukou", Yaku::Sanshokudoukou)
		.value("Sankantsu", Yaku::Sankantsu)
		.value("Toitoi", Yaku::Toitoiho)
		.value("Sanankou", Yaku::Sanankou)
		.value("Shosangen", Yaku::Shousangen)
		.value("Honrotou", Yaku::Honroutou)
		.value("Chitoitsu", Yaku::Chiitoitsu)
		.value("Chantai", Yaku::Honchantaiyaochu)
		.value("Ikkitsuukan", Yaku::Ikkitsuukan)
		.value("Sanshokudoujun", Yaku::Sanshokudoujun)
		.value("Junchan_", Yaku::Junchantaiyaochu_Naki)
		.value("Honitsu_", Yaku::Honitsu_Naki)

		.value("Ryanpeikou", Yaku::Rianpeikou)
		.value("Junchan", Yaku::Junchantaiyaochu)
		.value("Honitsu", Yaku::Honitsu)

		.value("Chinitsu_", Yaku::Chinitsu_Naki)

		.value("Chinitsu", Yaku::Chinitsu)

		.value("RyuukokuMangan", Yaku::Nagashimangan)

		.value("Tenho", Yaku::Tenhou)
		.value("Chiiho", Yaku::Chihou)
		.value("Daisangen", Yaku::Daisangen)
		.value("Suuanko", Yaku::Siiankou)
		.value("Tsuuiisou", Yaku::Tsuiisou)
		.value("Ryuiisou", Yaku::Ryuiisou)
		.value("Chinroutou", Yaku::Chinroutou)
		.value("Koukushimusou", Yaku::Kokushimusou)
		.value("Shosushi", Yaku::Shousuushi)
		.value("Suukantsu", Yaku::Siikantsu)
		.value("Churenpoutou", Yaku::Chuurenpoutou)

		.value("SuuankoTanki", Yaku::Siiankou_1)
		.value("Koukushimusou_13", Yaku::Koukushimusou_13)
		.value("Pure_Churenpoutou", Yaku::Chuurenpoutou_9)
		.value("Daisushi", Yaku::Daisuushi)
		;

	py::class_<CounterResult>(m, "CounterResult", "Result of yaku counting (fan, fu, score).")
		.def_readonly("yakus", &CounterResult::yakus, "List of yaku in this hand.")
		.def_readonly("fan", &CounterResult::fan, "Total fan count.")
		.def_readonly("fu", &CounterResult::fu, "Fu (minipoints) count.")
		.def_readonly("score1", &CounterResult::score1, "Score paid by non-dealer.")
		.def_readonly("score2", &CounterResult::score2, "Score paid by dealer (for tsumo).")
		;

	py::enum_<Table::PhaseEnum>(m, "PhaseEnum", "Enum of game phases in the state machine.")
		.value("GAME_OVER", Table::PhaseEnum::GAME_OVER)
		.value("P1_ACTION", Table::PhaseEnum::P1_ACTION)
		.value("P2_ACTION", Table::PhaseEnum::P2_ACTION)
		.value("P3_ACTION", Table::PhaseEnum::P3_ACTION)
		.value("P4_ACTION", Table::PhaseEnum::P4_ACTION)

		.value("P1_RESPONSE", Table::PhaseEnum::P1_RESPONSE)
		.value("P2_RESPONSE", Table::PhaseEnum::P2_RESPONSE)
		.value("P3_RESPONSE", Table::PhaseEnum::P3_RESPONSE)
		.value("P4_RESPONSE", Table::PhaseEnum::P4_RESPONSE)

		.value("P1_chankan", Table::PhaseEnum::P1_CHANKAN_RESPONSE)
		.value("P2_chankan", Table::PhaseEnum::P2_CHANKAN_RESPONSE)
		.value("P3_chankan", Table::PhaseEnum::P3_CHANKAN_RESPONSE)
		.value("P4_chankan", Table::PhaseEnum::P4_CHANKAN_RESPONSE)

		.value("P1_chanankan", Table::PhaseEnum::P1_CHANANKAN_RESPONSE)
		.value("P2_chanankan", Table::PhaseEnum::P2_CHANANKAN_RESPONSE)
		.value("P3_chanankan", Table::PhaseEnum::P3_CHANANKAN_RESPONSE)
		.value("P4_chanankan", Table::PhaseEnum::P4_CHANANKAN_RESPONSE)
		;

	py::class_<PaipuReplayer>(m, "PaipuReplayer", "Replay a recorded Mahjong game from a paipu log.")
		.def(py::init<>(), "Create a new PaipuReplayer.")
		.def_readwrite("table", &PaipuReplayer::table, "The game table being replayed.")
		.def("init", &PaipuReplayer::init,
			"Initialize the replayer with game configuration.",
			py::arg("yama"), py::arg("scores"), py::arg("kyoutaku"),
			py::arg("honba"), py::arg("game_wind"), py::arg("oya"))
		.def("get_self_actions", &PaipuReplayer::get_self_actions,
			"Get available self-actions for the current player.")
		.def("get_response_actions", &PaipuReplayer::get_response_actions,
			"Get available response-actions for the current player.")
		.def("make_selection", &PaipuReplayer::make_selection,
			"Execute the action at the given index.", py::arg("selection"))
		.def("make_selection_from_action", &PaipuReplayer::make_selection_from_action,
			"Execute the action matching the given action type and tiles.",
			py::arg("action"), py::arg("correspond_tiles"))
	    .def("get_selection_from_action", &PaipuReplayer::get_selection_from_action,
			"Find the action index matching the given action type and tiles.",
			py::arg("action"), py::arg("correspond_tiles"))
		.def("get_phase", &PaipuReplayer::get_phase,
			"Get the current game phase.")
		.def("get_result", &PaipuReplayer::get_result,
			"Get the game result (valid after GAME_OVER).")
		.def("set_write_log", &PaipuReplayer::set_write_log,
			"Enable or disable log writing.", py::arg("write_log"))
		;

	py::class_<TenhouShuffle>(m, "TenhouShuffle", "Tenhou-style MT19937 shuffle for deterministic tile wall generation.")
		.def_static("instance", &TenhouShuffle::instance,
			"Get the singleton TenhouShuffle instance.")
		.def("init", &TenhouShuffle::init,
			"Initialize the shuffler with a base64 seed string.", py::arg("seed"))
		.def("generate_yama", &TenhouShuffle::generate_yama,
			"Generate a deterministic tile wall (yama) as a list of tile IDs.")
		;

	py::class_<BaseGameLog>(m, "BaseGameLog", "A single action log entry in a game.")
		.def_readonly("player", &BaseGameLog::player, "Player who performed the action.")
		.def_readonly("player2", &BaseGameLog::player2, "Second player involved (e.g., for ron).")
		.def_readonly("action", &BaseGameLog::action, "The action type.")
		.def_readonly("tile", &BaseGameLog::tile, "The tile involved.")
		.def_readonly("call_tiles", &BaseGameLog::call_tiles, "Tiles involved in a call (chi/pon/kan).")
		.def_readonly("score", &BaseGameLog::score, "Score after this action.")
		.def("to_string", &BaseGameLog::to_string, "Return a string representation.")
		;

	py::class_<GameLog>(m, "GameLog", "Complete log of a Mahjong game.")
		.def_readonly("winner", &GameLog::winner, "List of winner player IDs.")
		.def_readonly("loser", &GameLog::loser, "List of loser player IDs.")
		.def_readonly("start_scores", &GameLog::start_scores, "Scores at the start of the game.")
		.def_readonly("init_yama", &GameLog::init_yama, "Initial tile wall.")
		.def_readonly("init_hands", &GameLog::init_hands, "Initial hands for each player.")
		.def_readonly("start_honba", &GameLog::start_honba, "Honba at game start.")
		.def_readonly("end_honba", &GameLog::end_honba, "Honba at game end.")
		.def_readonly("start_kyoutaku", &GameLog::start_kyoutaku, "Riichi sticks at game start.")
		.def_readonly("end_kyoutaku", &GameLog::end_kyoutaku, "Riichi sticks at game end.")
		.def_readonly("oya", &GameLog::oya, "Dealer player ID.")
		.def_readonly("game_wind", &GameLog::game_wind, "Game wind.")
		.def_readonly("result", &GameLog::result, "Game result.")
		.def_readonly("logs", &GameLog::logs, "List of action log entries.")
		.def("to_string", &GameLog::to_string, "Return a string representation.")
		;

	auto get_self_action_index =
	[](const std::vector<SelfAction> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
		{ return get_action_index(actions, action_type, correspond_tiles, use_red_dora); };

	auto get_response_action_index =
	[](const std::vector<ResponseAction> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
		{ return get_action_index(actions, action_type, correspond_tiles, use_red_dora); };

	m.def("get_self_action_index", get_self_action_index,
		"Find the index of a self-action matching the given type and tiles.",
		py::arg("actions"), py::arg("action_type"), py::arg("correspond_tiles"), py::arg("use_red_dora"));
	m.def("get_response_action_index", get_response_action_index,
		"Find the index of a response-action matching the given type and tiles.",
		py::arg("actions"), py::arg("action_type"), py::arg("correspond_tiles"), py::arg("use_red_dora"));

	namespace encv1 = TrainingDataEncoding::v1;
	m.def("encv1_encode_table", &encv1::py_encode_table,
		"Encode the table state into a numpy array (V1 encoding).",
		py::arg("table"), py::arg("pid"), py::arg("use_oracle"), py::arg("arr"));
	m.def("encv1_encode_table_riichi_step2", &encv1::py_encode_table_riichi_step2,
		"Encode the table state during riichi step 2 (V1 encoding).",
		py::arg("table"), py::arg("riichi_tile_id"), py::arg("arr"));
	m.def("encv1_encode_action", &encv1::py_encode_action,
		"Encode available actions into a numpy array (V1 encoding).",
		py::arg("table"), py::arg("pid"), py::arg("arr"));
	m.def("encv1_encode_action_riichi_step2", &encv1::py_encode_action_riichi_step2,
		"Encode actions during riichi step 2 (V1 encoding).",
		py::arg("arr"));
	m.def("encv1_get_riichi_tiles", &encv1::py_get_riichi_tiles,
		"Get the list of tile IDs that can be discarded for riichi.",
		py::arg("table"));

	namespace encv2 = TrainingDataEncoding::v2;

	py::class_<encv2::TableEncoder>(m, "TableEncoder", "V2 encoding: encodes the full table state for training.")
		.def(py::init<Table*>(), "Create a TableEncoder for the given table.", py::arg("table"))
		.def_readonly("self_infos", &encv2::TableEncoder::self_infos, "Self-info encoding.")
		.def_readonly("records", &encv2::TableEncoder::records, "Encoded records.")
		.def_readonly("global_infos", &encv2::TableEncoder::global_infos, "Global info encoding.")
		.def("init", &encv2::TableEncoder::init, "Initialize the encoder.")
		.def("update", &encv2::TableEncoder::update, "Update encoding after each action.")
		.def("_require_update", &encv2::TableEncoder::_require_update, "Check if encoding needs updating.")
		.def_readonly("record_count", &encv2::TableEncoder::record_count, "Number of encoded records.")
		;

	py::class_<encv2::PassiveTableEncoder>(m, "PassiveTableEncoder", "V2 passive encoding: encodes individual aspects of the table state.")
		.def(py::init<>(), "Create a new PassiveTableEncoder.")
		.def_readonly("self_info", &encv2::PassiveTableEncoder::self_info, "Self-info encoding.")
		.def_readonly("records", &encv2::PassiveTableEncoder::records, "Encoded records.")
		.def_readonly("global_info", &encv2::PassiveTableEncoder::global_info, "Global info encoding.")
		.def("encode_game_basic", &encv2::PassiveTableEncoder::encode_game_basic,
			"Encode basic game info (wind, oya, scores).",
			py::arg("game_number"), py::arg("game_size"), py::arg("honba"),
			py::arg("kyoutaku"), py::arg("self_wind"), py::arg("game_wind"))
		.def("encode_hand", &encv2::PassiveTableEncoder::encode_hand,
			"Encode the player's hand.",
			py::arg("hand"), py::arg("after_chipon"))
		.def("encode_self_river", &encv2::PassiveTableEncoder::encode_self_river,
			"Encode the player's own discard river.", py::arg("river"))
		.def("encode_next_river", &encv2::PassiveTableEncoder::encode_next_river,
			"Encode the next player's discard river.", py::arg("river"))
		.def("encode_opposite_river", &encv2::PassiveTableEncoder::encode_opposite_river,
			"Encode the opposite player's discard river.", py::arg("river"))
		.def("encode_river", &encv2::PassiveTableEncoder::encode_river,
			"Encode all players' discard rivers.",
			py::arg("river"), py::arg("relative_position"))
		.def("encode_self_fuuro", &encv2::PassiveTableEncoder::encode_self_fuuro,
			"Encode the player's own called melds.", py::arg("callgroups"))
		.def("encode_next_fuuro", &encv2::PassiveTableEncoder::encode_next_fuuro,
			"Encode the next player's called melds.", py::arg("callgroups"))
		.def("encode_opposite_fuuro", &encv2::PassiveTableEncoder::encode_opposite_fuuro,
			"Encode the opposite player's called melds.", py::arg("callgroups"))
		.def("encode_previous_fuuro", &encv2::PassiveTableEncoder::encode_previous_fuuro,
			"Encode the previous player's called melds.", py::arg("callgroups"))
		.def("encode_fuuro", &encv2::PassiveTableEncoder::encode_fuuro,
			"Encode all players' called melds.",
			py::arg("callgroups"), py::arg("relative_position"))
		.def("encode_dora", &encv2::PassiveTableEncoder::encode_dora,
			"Encode the dora indicators.", py::arg("revealed_doras"))
		.def("encode_points", &encv2::PassiveTableEncoder::encode_points,
			"Encode the players' scores/points.", py::arg("points"))
		.def("encode_remaining_tiles", &encv2::PassiveTableEncoder::encode_remaining_tiles,
			"Encode the remaining tile counts.", py::arg("remain_tiles"))
		.def("encode_riichi_states", &encv2::PassiveTableEncoder::encode_riichi_states,
			"Encode the riichi declaration states.", py::arg("riichi_states"))
		.def("encode_ippatsu_states", &encv2::PassiveTableEncoder::encode_ippatsu_states,
			"Encode the ippatsu possibility states.", py::arg("ippatsu_states"))
		;
}

#ifdef __GNUC__
#pragma GCC diagnostic pop
#endif
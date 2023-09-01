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
	
	py::enum_<BaseTile>(m, "BaseTile")
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

	py::class_<CallGroup>(m, "CallGroup")
		.def_readonly("type", &CallGroup::type)
		.def_readonly("tiles", &CallGroup::tiles)
		.def_readonly("take", &CallGroup::take)
		.def("to_string", &CallGroup::to_string)
		;

	m.def("CallGroupToString", [](const CallGroup &CallGroup) {return py::bytes(CallGroup.to_string()); });

	py::class_<Tile>(m, "Tile")
		.def_readonly("tile", &Tile::tile)
		.def_readonly("red_dora", &Tile::red_dora)
		.def_readonly("id", &Tile::id)
		.def("to_string", &Tile::to_string)
		// .def("to_simple_string", &Tile::to_string)
		;

	m.def("TileToString", [](const Tile *tile) {return py::bytes(tile->to_string()); });

	py::class_<River>(m, "River")
		.def_readonly("river", &River::river)
		.def("size", &River::size)
		.def("to_string", &River::to_string)
		;

	m.def("RiverToString", [](const River& river) {return py::bytes(river.to_string()); });

	py::class_<RiverTile>(m, "RiverTile")
		.def_readonly("tile", &RiverTile::tile)
		.def_readonly("number", &RiverTile::number)
		.def_readonly("riichi", &RiverTile::riichi)
		.def_readonly("remain", &RiverTile::remain)
		.def_readonly("fromhand", &RiverTile::fromhand)
		;

	py::enum_<Wind>(m, "Wind")
		.value("East", Wind::East)
		.value("South", Wind::South)
		.value("West", Wind::West)
		.value("North", Wind::North)
		;

	py::enum_<BaseAction>(m, "BaseAction")
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

	py::class_<SelfAction>(m, "SelfAction")
		.def_readonly("action", &SelfAction::action)
		.def_readonly("correspond_tiles", &SelfAction::correspond_tiles)
		.def("to_string", &SelfAction::to_string)
		;

	m.def("SelfActionToString", [](const SelfAction &sa) {return py::bytes(sa.to_string()); });

	py::class_<ResponseAction>(m, "ResponseAction")
		.def_readonly("action", &ResponseAction::action)
		.def_readonly("correspond_tiles", &ResponseAction::correspond_tiles)
		.def("to_string", &ResponseAction::to_string)
		;

	m.def("ResponseActionToString", [](const ResponseAction &ra) {return py::bytes(ra.to_string()); });

	py::class_<Player>(m, "Player")
		// 成员变量们
		.def_readonly("double_riichi", &Player::double_riichi)
		.def_readonly("riichi", &Player::riichi)
		.def_readonly("menzen", &Player::menzen)
		.def_readonly("wind", &Player::wind)
		.def_readonly("oya", &Player::oya)
		.def_readonly("toujun_furiten", &Player::furiten_round)
		.def_readonly("sutehai_furiten", &Player::furiten_river)
		.def_readonly("riichi_furiten", &Player::furiten_riichi)
		.def_readonly("score", &Player::score)
		.def_readonly("hand", &Player::hand)
		// .def_readonly("fulus", &Player::副露s)
		// .def_readonly("river", &Player::river)
		.def_readonly("ippatsu", &Player::ippatsu)
		.def_readonly("first_round", &Player::first_round)
		
		// 函数们
		.def("get_fuuros", &Player::get_fuuros)
		.def("get_river", &Player::get_river)
		.def("is_furiten", &Player::is_furiten)
		.def("to_string", &Player::to_string)
		.def("hand_to_string", &Player::to_string)
		.def("tenpai_to_string", &Player::tenpai_to_string)
		;

	m.def("PlayerToString", [](const Player& player) {return py::bytes(player.to_string()); });

	py::class_<Table>(m, "Table")
		.def(py::init<>())

		// 函数们
		.def("game_init", &Table::game_init)
		.def("game_init_with_metadata", &Table::game_init_with_metadata)
		.def("get_phase", &Table::get_phase)
		.def("make_selection", &Table::make_selection)
		.def("get_selection_from_action_tile", &Table::get_selection_from_action_tile)
		.def("make_selection_from_action_tile", &Table::make_selection_from_action_tile)
		.def("get_selection_from_action_basetile", &Table::get_selection_from_action_basetile_int)
		.def("make_selection_from_action_basetile", &Table::make_selection_from_action_basetile_int)
		.def("get_info", &Table::get_info, py::return_value_policy::reference)
		.def("get_selected_base_action", &Table::get_selected_base_action)
		.def("who_make_selection", &Table::who_make_selection)
		.def("get_selected_action_tile", &Table::get_selected_action_tile, py::return_value_policy::reference)
		.def("get_selected_action", &Table::get_selected_action)
		.def("get_result", &Table::get_result)

		// change to reference will cause error (why?)
		.def("get_self_actions", &Table::get_self_actions)
		.def("get_response_actions", &Table::get_response_actions)

		.def("set_seed", &Table::set_seed)
		.def("set_debug_mode", &Table::set_debug_mode)
		.def("print_debug_replay", &Table::print_debug_replay)
		.def("get_debug_replay", &Table::get_debug_replay)

		// 成员变量们
		.def_readonly("n_active_dora", &Table::n_active_dora)
		.def_readonly("dora_indicator", &Table::dora_indicator)
		.def_readonly("uradora_indicator", &Table::uradora_indicator)
		.def_readonly("yama", &Table::yama)
		.def_readonly("players", &Table::players)
		.def_readonly("turn", &Table::turn)
		.def_readonly("last_action", &Table::last_action)
		.def_readonly("game_wind", &Table::game_wind)
		.def_readonly("last_action", &Table::last_action)
		.def_readonly("oya", &Table::oya)
		.def_readonly("honba", &Table::honba)
		.def_readonly("riichibo", &Table::kyoutaku)
		
		// 辅助函数们
		.def("get_dora", &Table::get_dora)
		.def("get_ura_dora", &Table::get_ura_dora)
		.def("get_remain_kan_tile", &Table::get_remain_kan_tile)
		.def("get_remain_tile", &Table::get_remain_tile)
		.def("to_string", static_cast<std::string(Table::*)() const>(&Table::to_string))
		;

	m.def("TableToString", [](const Table& table) {return py::bytes(table.to_string()); });

	py::enum_<ResultType>(m, "ResultType")
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

	py::class_<Result>(m, "Result")
		.def_readonly("result_type", &Result::result_type)
		.def_readonly("results", &Result::results)
		.def_readonly("score", &Result::score)
		.def_readonly("winner", &Result::winner)
		.def_readonly("loser", &Result::loser)
		.def("to_string", &Result::to_string)
		;	

	py::enum_<Yaku>(m, "Yaku")
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

	py::class_<CounterResult>(m, "CounterResult")
		.def_readonly("yakus", &CounterResult::yakus)
		.def_readonly("fan", &CounterResult::fan)
		.def_readonly("fu", &CounterResult::fu)
		.def_readonly("score1", &CounterResult::score1)
		.def_readonly("score2", &CounterResult::score2)
		;

	py::enum_<Table::PhaseEnum>(m, "PhaseEnum")
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

	py::class_<PaipuReplayer>(m, "PaipuReplayer")
		.def(py::init<>())
		.def_readwrite("table", &PaipuReplayer::table)
		.def("init", &PaipuReplayer::init)
		.def("get_self_actions", &PaipuReplayer::get_self_actions)
		.def("get_response_actions", &PaipuReplayer::get_response_actions)
		.def("make_selection", &PaipuReplayer::make_selection)
		.def("make_selection_from_action", &PaipuReplayer::make_selection_from_action)
	    .def("get_selection_from_action", &PaipuReplayer::get_selection_from_action)
		.def("get_phase", &PaipuReplayer::get_phase)
		.def("get_result", &PaipuReplayer::get_result)
		.def("set_write_log", &PaipuReplayer::set_write_log)
		;

	py::class_<TenhouShuffle>(m, "TenhouShuffle")
		.def_static("instance", &TenhouShuffle::instance)
		.def("init", &TenhouShuffle::init)
		.def("generate_yama", &TenhouShuffle::generate_yama)
		;

	py::class_<BaseGameLog>(m, "BaseGameLog")
		.def_readonly("player", &BaseGameLog::player)
		.def_readonly("player2", &BaseGameLog::player2)
		.def_readonly("action", &BaseGameLog::action)
		.def_readonly("tile", &BaseGameLog::tile)
		.def_readonly("call_tiles", &BaseGameLog::call_tiles)
		.def_readonly("score", &BaseGameLog::score)
		.def("to_string", &BaseGameLog::to_string)
		;

	py::class_<GameLog>(m, "GameLog")
		.def_readonly("winner", &GameLog::winner)
		.def_readonly("loser", &GameLog::loser)
		.def_readonly("start_scores", &GameLog::start_scores)
		.def_readonly("init_yama", &GameLog::init_yama)
		.def_readonly("init_hands", &GameLog::init_hands)
		.def_readonly("start_honba", &GameLog::start_honba)
		.def_readonly("end_honba", &GameLog::end_honba)
		.def_readonly("start_kyoutaku", &GameLog::start_kyoutaku)
		.def_readonly("end_kyoutaku", &GameLog::end_kyoutaku)
		.def_readonly("oya", &GameLog::oya)
		.def_readonly("game_wind", &GameLog::game_wind)
		.def_readonly("result", &GameLog::result)
		.def_readonly("logs", &GameLog::logs)
		.def("to_string", &GameLog::to_string)
		;

	auto get_self_action_index = 
	[](const std::vector<SelfAction> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
		{ return get_action_index(actions, action_type, correspond_tiles, use_red_dora); };
		
	auto get_response_action_index = 
	[](const std::vector<ResponseAction> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
		{ return get_action_index(actions, action_type, correspond_tiles, use_red_dora); };

	m.def("get_self_action_index", get_self_action_index);
	m.def("get_response_action_index", get_response_action_index);

	namespace encv1 = TrainingDataEncoding::v1;
	m.def("encv1_encode_table", &encv1::py_encode_table);
	m.def("encv1_encode_table_riichi_step2", &encv1::py_encode_table_riichi_step2);
	m.def("encv1_encode_action", &encv1::py_encode_action);
	m.def("encv1_encode_action_riichi_step2", &encv1::py_encode_action_riichi_step2);
	m.def("encv1_get_riichi_tiles", &encv1::py_get_riichi_tiles);

	namespace encv2 = TrainingDataEncoding::v2;

	py::class_<encv2::TableEncoder>(m, "TableEncoder")
		.def(py::init<Table*>())
		.def_readonly("self_infos", &encv2::TableEncoder::self_infos)
		.def_readonly("records", &encv2::TableEncoder::records)
		.def_readonly("global_infos", &encv2::TableEncoder::global_infos)
		.def("init", &encv2::TableEncoder::init)
		.def("update", &encv2::TableEncoder::update)
		.def("_require_update", &encv2::TableEncoder::_require_update)
		.def_readonly("record_count", &encv2::TableEncoder::record_count)
		;
}

#ifdef __GNUC__
#pragma GCC diagnostic pop
#endif
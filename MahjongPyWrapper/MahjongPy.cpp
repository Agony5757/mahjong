#ifdef __GNUC__
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-value"
#endif

#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "pybind11/complex.h"
#include "pybind11/functional.h"
#include "pybind11/operators.h"
#include "Table.h"
#include "ScoreCounter.h"
#include "GamePlay.h"
#include "tenhou.h"
#include "EncodingPy.h"

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

	py::class_<Fulu>(m, "Fulu")
		.def_readonly("type", &Fulu::type)
		.def_readonly("tiles", &Fulu::tiles)
		.def_readonly("take", &Fulu::take)
		.def("to_string", &Fulu::to_string)
		;

	m.def("FuluToString", [](const Fulu &fulu) {return py::bytes(fulu.to_string()); });

	py::class_<Tile>(m, "Tile")
		.def_readonly("tile", &Tile::tile)
		.def_readonly("red_dora", &Tile::red_dora)
		.def_readonly("id", &Tile::id)
		.def("to_string", &Tile::to_string)
		.def("to_simple_string", &Tile::to_simple_string)
		;

	m.def("TileToString", [](const Tile *tile) {return py::bytes(tile->to_string()); });

	py::class_<River>(m, "River")
		.def_readonly("river", &River::river)
		.def("size", &River::size)
		.def("to_string", &River::to_string)
		;

	m.def("RiverToString", [](const River& river) {return py::bytes(river.to_string()); });

	py::enum_<Wind>(m, "Wind")
		.value("East", Wind::East)
		.value("South", Wind::South)
		.value("West", Wind::West)
		.value("North", Wind::North)
		;

	py::enum_<BaseAction>(m, "BaseAction")
		.value("Pass", BaseAction::pass)
		.value("Chi", BaseAction::吃)
		.value("Pon", BaseAction::碰)
		.value("Kan", BaseAction::杠)
		.value("Ron", BaseAction::荣和)

		.value("ChanAnKan", BaseAction::抢暗杠)
		.value("ChanKan", BaseAction::抢杠)

		.value("AnKan", BaseAction::暗杠)
		.value("KaKan", BaseAction::加杠)
		.value("Play", BaseAction::出牌)
		.value("Riichi", BaseAction::立直)
		.value("Tsumo", BaseAction::自摸)
		.value("KyuShuKyuHai", BaseAction::九种九牌)
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
		.def_readonly("menchin", &Player::门清)
		.def_readonly("wind", &Player::wind)
		.def_readonly("oya", &Player::亲家)
		.def_readonly("toujun_furiten", &Player::同巡振听)
		.def_readonly("sutehai_furiten", &Player::舍牌振听)
		.def_readonly("riichi_furiten", &Player::立直振听)
		.def_readonly("score", &Player::score)
		.def_readonly("hand", &Player::hand)
		.def_readonly("fulus", &Player::副露s)
		.def_readonly("river", &Player::river)
		.def_readonly("ippatsu", &Player::一发)
		.def_readonly("first_round", &Player::first_round)
		
		// 函数们
		.def("is_furiten", &Player::is振听)
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
		.def("make_selection_from_action_tile", &Table::make_selection_from_action_tile)
		.def("make_selection_from_action_basetile", &Table::make_selection_from_action_basetile_int)
		.def("get_info", &Table::get_info, py::return_value_policy::reference)
		.def("get_selected_base_action", &Table::get_selected_base_action)
		.def("who_make_selection", &Table::who_make_selection)
		.def("get_selected_action_tile", &Table::get_selected_action_tile, py::return_value_policy::reference)
		.def("get_selected_action", &Table::get_selected_action)
		.def("get_result", &Table::get_result)
		.def("get_self_actions", &Table::get_self_actions)
		.def("get_response_actions", &Table::get_response_actions)

		// 成员变量们
		.def_readonly("dora_spec", &Table::dora_spec)
		.def_readonly("DORA", &Table::宝牌指示牌)
		.def_readonly("URA_DORA", &Table::里宝牌指示牌)
		.def_readonly("YAMA", &Table::牌山)
		.def_readonly("players", &Table::players)
		.def_readonly("turn", &Table::turn)
		.def_readonly("last_action", &Table::last_action)
		.def_readonly("game_wind", &Table::场风)
		.def_readonly("last_action", &Table::last_action)
		.def_readonly("oya", &Table::庄家)
		.def_readonly("honba", &Table::n本场)
		.def_readonly("riichibo", &Table::n立直棒)
		
		// 辅助函数们
		.def("get_dora", &Table::get_dora)
		.def("get_ura_dora", &Table::get_ura_dora)
		.def("get_remain_kan_tile", &Table::get_remain_kan_tile)
		.def("get_remain_tile", &Table::get_remain_tile)
		.def("to_string", &Table::to_string)
		;

	m.def("TableToString", [](const Table& table, int mode) {return py::bytes(table.to_string(mode)); });

	py::enum_<ResultType>(m, "ResultType")
		.value("RonAgari", ResultType::荣和终局)
		.value("TsumoAgari", ResultType::自摸终局)
		.value("IntervalRyuuKyoku", ResultType::中途流局)
		.value("NoTileRyuuKyoku", ResultType::荒牌流局)
		.value("NagashiMangan", ResultType::流局满贯)
		;

	py::class_<Result>(m, "Result")
		.def_readonly("result_type", &Result::result_type)
		.def_readonly("results", &Result::results)
		.def_readonly("score", &Result::score)
		.def_readonly("winner", &Result::winner)
		.def_readonly("loser", &Result::loser)
		.def("to_string", &Result::to_string)
		;	

	m.def("ResultToString", [](const Result& result) {return py::bytes(result.to_string()); });

	py::enum_<Yaku>(m, "Yaku")
		.value("NoYaku", Yaku::None)

		.value("Riichi", Yaku::立直)
		.value("Tanyao", Yaku::断幺九)
		.value("Menzentsumo", Yaku::门前清自摸和)
		.value("SelfWind_East", Yaku::自风_东)
		.value("SelfWind_South", Yaku::自风_南)
		.value("SelfWind_West", Yaku::自风_西)
		.value("SelfWind_North", Yaku::自风_北)
		.value("GameWind_East", Yaku::场风_东)
		.value("GameWind_South", Yaku::场风_南)
		.value("GameWind_West", Yaku::场风_西)
		.value("GameWind_North", Yaku::场风_北)
		.value("Yakuhai_haku", Yaku::役牌_白)
		.value("Yakuhai_hastu", Yaku::役牌_发)
		.value("Yakuhai_chu", Yaku::役牌_中)
		.value("Pinfu", Yaku::平和)
		.value("Yiipeikou", Yaku::一杯口)
		.value("Chankan", Yaku::抢杠)
		.value("Rinshankaihou", Yaku::岭上开花)
		.value("Haitiraoyue", Yaku::海底捞月)
		.value("Houtiraoyui", Yaku::河底捞鱼)
		.value("Ippatsu", Yaku::一发)
		.value("Dora", Yaku::宝牌)
		.value("UraDora", Yaku::里宝牌)
		.value("AkaDora", Yaku::赤宝牌)
		.value("Chantai_", Yaku::混全带幺九副露版)
		.value("Ikkitsukan_", Yaku::一气通贯副露版)
		.value("Sanshokudoujun_", Yaku::三色同顺副露版)

		.value("DoubleRiichi", Yaku::两立直)
		.value("Sanshokudoukou", Yaku::三色同刻)
		.value("Sankantsu", Yaku::三杠子)
		.value("Toitoi", Yaku::对对和)
		.value("Sanankou", Yaku::三暗刻)
		.value("Shosangen", Yaku::小三元)
		.value("Honrotou", Yaku::混老头)
		.value("Chitoitsu", Yaku::七对子)
		.value("Chantai", Yaku::混全带幺九)
		.value("Ikkitsuukan", Yaku::一气通贯)
		.value("Sanshokudoujun", Yaku::三色同顺)
		.value("Junchan_", Yaku::纯全带幺九副露版)
		.value("Honitsu_", Yaku::混一色副露版)

		.value("Ryanpeikou", Yaku::二杯口)
		.value("Junchan", Yaku::纯全带幺九)
		.value("Honitsu", Yaku::混一色)

		.value("Chinitsu_", Yaku::清一色副露版)

		.value("Chinitsu", Yaku::清一色)

		.value("RyuukokuMangan", Yaku::流局满贯)

		.value("Tenho", Yaku::天和)
		.value("Chiiho", Yaku::地和)
		.value("Daisangen", Yaku::大三元)
		.value("Suuanko", Yaku::四暗刻)
		.value("Tsuuiisou", Yaku::字一色)
		.value("Ryuiisou", Yaku::绿一色)
		.value("Chinroutou", Yaku::清老头)
		.value("Koukushimusou", Yaku::国士无双)
		.value("Shosushi", Yaku::小四喜)
		.value("Suukantsu", Yaku::四杠子)
		.value("Churenpoutou", Yaku::九莲宝灯)

		.value("SuuankoTanki", Yaku::四暗刻单骑)
		.value("Koukushimusou_13", Yaku::国士无双十三面)
		.value("Pure_Churenpoutou", Yaku::纯正九莲宝灯)
		.value("Daisushi", Yaku::大四喜)
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
		
		.value("P1_chankan", Table::PhaseEnum::P1_抢杠RESPONSE)
		.value("P2_chankan", Table::PhaseEnum::P2_抢杠RESPONSE)
		.value("P3_chankan", Table::PhaseEnum::P3_抢杠RESPONSE)
		.value("P4_chankan", Table::PhaseEnum::P4_抢杠RESPONSE)
		
		.value("P1_chanankan", Table::PhaseEnum::P1_抢暗杠RESPONSE)
		.value("P2_chanankan", Table::PhaseEnum::P2_抢暗杠RESPONSE)
		.value("P3_chanankan", Table::PhaseEnum::P3_抢暗杠RESPONSE)
		.value("P4_chanankan", Table::PhaseEnum::P4_抢暗杠RESPONSE)
		;

	m.def("yakus_to_string", [](std::vector<Yaku> yakus) {return py::bytes(yakus_to_string(yakus)); });

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
		.def("set_log", &PaipuReplayer::set_log)
		;

	py::class_<TenhouShuffle>(m, "TenhouShuffle")
		.def_static("instance", &TenhouShuffle::instance)
		.def("init", &TenhouShuffle::init)
		.def("generate_yama", &TenhouShuffle::generate_yama)
		;

	m.def("encode_table", &encode_table);
	m.def("encode_table_riichi_step2", &encode_table_riichi_step2);
	m.def("encode_action", &encode_action);
	m.def("encode_action_riichi_step2", &encode_action_riichi_step2);
	m.def("get_riichi_tiles", &TrainingDataEncoding::get_riichi_tiles);

	auto get_self_action_index = 
	[](const std::vector<SelfAction> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
		{ return get_action_index(actions, action_type, correspond_tiles, use_red_dora); };
		
	auto get_response_action_index = 
	[](const std::vector<ResponseAction> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
		{ return get_action_index(actions, action_type, correspond_tiles, use_red_dora); };

	m.def("get_self_action_index", get_self_action_index);
	m.def("get_response_action_index", get_response_action_index);
}

#ifdef __GNUC__
#pragma GCC diagnostic pop
#endif
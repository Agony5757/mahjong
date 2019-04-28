#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "pybind11/complex.h"
#include "pybind11/functional.h"
#include "pybind11/operators.h"
#include "Mahjong/Table.h"
#include <map>

using namespace std;
using namespace pybind11::literals;
namespace py = pybind11;

PYBIND11_MODULE(MahjongPy, m)
{
	m.doc() = "";
	
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

		.value("east", BaseTile::east)
		.value("south", BaseTile::south)
		.value("west", BaseTile::west)
		.value("north", BaseTile::north)
		.value("haku", BaseTile::��)
		.value("hatsu", BaseTile::��)
		.value("chu", BaseTile::��)
		;

	py::class_<Tile>(m, "Tile")
		.def_readonly("tile", &Tile::tile)
		.def_readonly("red_dora", &Tile::red_dora)
		;

	py::class_<River>(m, "River")
		.def_readonly("river", &River::river)
		.def("size", &River::size)
		;

	py::enum_<Wind>(m, "Wind")
		.value("East", Wind::East)
		.value("South", Wind::South)
		.value("West", Wind::West)
		.value("North", Wind::North)
		;

	py::enum_<Action>(m, "Action")
		.value("pass", Action::pass)
		.value("Chi", Action::��)
		.value("Pon", Action::��)
		.value("Kan", Action::��)
		.value("Ron", Action::�ٺ�)

		.value("ChanAnKan", Action::������)
		.value("ChanKan", Action::����)

		.value("Ankan", Action::����)
		.value("Kakan", Action::�Ӹ�)
		.value("Play", Action::����)
		.value("Riichi", Action::��ֱ)
		.value("Tsumo", Action::����)
		.value("KyuShuKyuHai", Action::���־���)
		;

	py::class_<Player>(m, "Player")
		// ��Ա������
		.def_readonly("double_riichi", &Player::double_riichi)
		.def_readonly("riichi", &Player::riichi)
		.def_readonly("menchin", &Player::����)
		.def_readonly("wind", &Player::wind)
		.def_readonly("oya", &Player::�׼�)
		.def_readonly("furiten", &Player::����)
		.def_readonly("riichi_furiten", &Player::��ֱ����)
		.def_readonly("score", &Player::score)
		.def_readonly("hand", &Player::hand)
		.def_readonly("fulus", &Player::��¶s)
		.def_readonly("river", &Player::river)
		.def_readonly("ippatsu", &Player::һ��)
		.def_readonly("first_round", &Player::first_round)
		
		// ������
		.def("is_furiten", &Player::is����)
		;

	py::class_<Table>(m, "Table")
		.def(py::init<>())

		// ������
		.def("game_init", &Table::game_init)
		.def("get_phase", &Table::get_phase)
		.def("make_selection", &Table::make_selection)
		.def("get_info", &Table::get_info, py::return_value_policy::reference)
		.def("get_selected_action", &Table::get_selected_action)
		.def("who_make_selection", &Table::who_make_selection)
		.def("get_tile", &Table::get_tile, py::return_value_policy::reference)
		.def("get_result", &Table::get_result)
		.def("get_self_actions", &Table::get_self_actions)
		.def("get_response_actions", &Table::get_response_actions)

		// ��Ա������
		.def_readonly("dora_spec", &Table::dora_spec)
		.def_readonly("DORA", &Table::����ָʾ��)
		.def_readonly("URA_DORA", &Table::�ﱦ��ָʾ��)
		.def_readonly("YAMA", &Table::��ɽ)
		.def_readonly("players", &Table::players)
		.def_readonly("turn", &Table::turn)
		.def_readonly("last_action", &Table::last_action)
		.def_readonly("game_wind", &Table::����)
		.def_readonly("last_action", &Table::last_action)
		.def_readonly("oya", &Table::ׯ��)
		.def_readonly("honba", &Table::n����)
		.def_readonly("riichibo", &Table::n��ֱ��)
		
		// ����������
		.def("get_dora", &Table::get_dora)
		.def("get_ura_dora", &Table::get_ura_dora)
		.def("get_remain_kan_tile", &Table::get_remain_kan_tile)
		.def("get_remain_tile", &Table::get_remain_tile)
		;

	py::enum_<ResultType>(m, "ResultType")
		.value("RonAgari", ResultType::�ٺ��վ�)
		.value("TsumoAgari", ResultType::�����վ�)
		.value("IntervalRyuuKyoku", ResultType::��;����)
		.value("NoTileRyuuKyoku", ResultType::��������)
		.value("RyuuKyokuMangan", ResultType::��������)
		;

	py::class_<Result>(m, "Result")
		.def_readonly("result_type", &Result::result_type)
		.def_readonly("results", &Result::results)
		.def_readonly("score", &Result::score)
		;		

	py::enum_<Table::_Phase_>(m, "_Phase_")
		.value("GAME_OVER", Table::_Phase_::GAME_OVER)
		.value("P1_ACTION", Table::_Phase_::P1_ACTION)
		.value("P2_ACTION", Table::_Phase_::P2_ACTION)
		.value("P3_ACTION", Table::_Phase_::P3_ACTION)
		.value("P4_ACTION", Table::_Phase_::P4_ACTION)

		.value("P1_RESPONSE", Table::_Phase_::P1_RESPONSE)
		.value("P2_RESPONSE", Table::_Phase_::P2_RESPONSE)
		.value("P3_RESPONSE", Table::_Phase_::P3_RESPONSE)
		.value("P4_RESPONSE", Table::_Phase_::P4_RESPONSE)
		
		.value("P1_chankan", Table::_Phase_::P1_����RESPONSE)
		.value("P2_chankan", Table::_Phase_::P2_����RESPONSE)
		.value("P3_chankan", Table::_Phase_::P3_����RESPONSE)
		.value("P4_chankan", Table::_Phase_::P4_����RESPONSE)
		
		.value("P1_chanankan", Table::_Phase_::P1_������RESPONSE)
		.value("P2_chanankan", Table::_Phase_::P2_������RESPONSE)
		.value("P3_chanankan", Table::_Phase_::P3_������RESPONSE)
		.value("P4_chanankan", Table::_Phase_::P4_������RESPONSE)
		;

}

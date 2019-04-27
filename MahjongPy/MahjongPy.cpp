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
	
	py::class_<Table>(m, "Table");

	py::enum_<Table::_Phase_>(m, "_Phase_")
		.value("GAME_OVER", Table::_Phase_::GAME_OVER)
		;

}

#include <type_traits>
#include <typeinfo>
#include "EncodingPy.h"

using namespace std;

namespace_mahjong

namespace TrainingDataEncoding {
	namespace v1
	{
		void py_encode_table(const Table& table, int pid, bool use_oracle, pybind11::array_t<dtype> arr)
		{
			dtype* data = arr.mutable_data();
			encode_table(table, pid, use_oracle, data);
		}

		void py_encode_table_riichi_step2(const Table& table, int riichi_tile, pybind11::array_t<dtype> arr)
		{
			dtype* data = arr.mutable_data();
			encode_table_riichi_step2(table, (BaseTile)riichi_tile, data);
		}

		void py_encode_action(const Table& table, int pid, pybind11::array_t<dtype> arr)
		{
			dtype* data = arr.mutable_data();
			encode_actions_vector(table, pid, data);
		}

		void py_encode_action_riichi_step2(pybind11::array_t<dtype> arr)
		{
			dtype* data = arr.mutable_data();
			encode_actions_vector_riichi_step2(data);
		}

		std::vector<BaseTile> py_get_riichi_tiles(const Table& table)
		{
			return get_riichi_tiles(table);
		}
	}
}

namespace_mahjong_end

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

	namespace v4
	{
		pybind11::array_t<bool> py_events(const v4::HandTrackEncoder& enc)
		{
			const auto& events = enc.events();
			size_t n = events.size();
			auto arr = pybind11::array_t<bool>({n, v4::EVENT_DIM});
			auto buf = arr.mutable_unchecked<2>();
			for (size_t i = 0; i < n; ++i) {
				for (size_t j = 0; j < v4::EVENT_DIM; ++j) {
					buf(i, j) = events[i].bits.test(j);
				}
			}
			return arr;
		}

		pybind11::list py_decide_points(const v4::HandTrackEncoder& enc)
		{
			pybind11::list result;
			for (const auto& dp : enc.decide_points()) {
				pybind11::dict d;
				d["track_pos"] = dp.track_pos;
				d["action_label"] = dp.action_label;

				auto mask_arr = pybind11::array_t<uint8_t>(v4::N_ACTION_DIM);
				auto mask_buf = mask_arr.mutable_unchecked<1>();
				for (size_t i = 0; i < v4::N_ACTION_DIM; ++i)
					mask_buf(i) = dp.action_mask[i];
				d["action_mask"] = mask_arr;

				result.append(d);
			}
			return result;
		}
	}
}

namespace_mahjong_end

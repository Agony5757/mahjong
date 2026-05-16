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

	namespace v3
	{
		pybind11::dict py_encode(v3::TableTokenizer& enc, int current_player, bool riichi_stage2)
		{
			auto obs = enc.encode(current_player, riichi_stage2);

			// tokens: (MAX_SEQ_LEN, TOKEN_FEATURES) uint8
			auto tokens_arr = pybind11::array_t<uint8_t>(
				{v3::MAX_SEQ_LEN, v3::TOKEN_FEATURES});
			auto tok_buf = tokens_arr.mutable_unchecked<2>();
			for (int i = 0; i < v3::MAX_SEQ_LEN; ++i)
				for (int j = 0; j < v3::TOKEN_FEATURES; ++j)
					tok_buf(i, j) = obs.tokens[i][j];

			// scalars: (MAX_SEQ_LEN, SCALAR_DIM) float32
			auto scalars_arr = pybind11::array_t<float>(
				{v3::MAX_SEQ_LEN, v3::SCALAR_DIM});
			auto sc_buf = scalars_arr.mutable_unchecked<2>();
			for (int i = 0; i < v3::MAX_SEQ_LEN; ++i)
				for (int j = 0; j < v3::SCALAR_DIM; ++j)
					sc_buf(i, j) = obs.scalars[i][j];

			// attention_mask: (MAX_SEQ_LEN,) bool
			auto mask_arr = pybind11::array_t<bool>({v3::MAX_SEQ_LEN});
			auto mask_buf = mask_arr.mutable_unchecked<1>();
			for (int i = 0; i < v3::MAX_SEQ_LEN; ++i)
				mask_buf(i) = obs.attention_mask[i];

			// action_mask: (ACTION_DIM,) bool
			auto amask_arr = pybind11::array_t<bool>({v3::ACTION_DIM});
			auto amask_buf = amask_arr.mutable_unchecked<1>();
			for (int i = 0; i < v3::ACTION_DIM; ++i)
				amask_buf(i) = obs.action_mask[i];

			pybind11::dict d;
			d["tokens"] = tokens_arr;
			d["scalars"] = scalars_arr;
			d["attention_mask"] = mask_arr;
			d["action_mask"] = amask_arr;
			d["seq_len"] = obs.seq_len;
			d["current_player"] = obs.current_player;
			d["phase"] = obs.phase;
			return d;
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

#ifndef ENCODINGPY_H
#define ENCODINGPY_H

#include "Encoding/TrainingDataEncodingV1.h"
#include "Encoding/TrainingDataEncodingV2.h"
#include "Encoding/TrainingDataEncodingV3.h"
#include "Encoding/TrainingDataEncodingV4.h"
#include "pybind11/numpy.h"
#include "Table.h"

namespace_mahjong
namespace TrainingDataEncoding {
	namespace v1
	{
		void py_encode_table(const mahjong::Table& table, int pid, bool use_oracle, pybind11::array_t<dtype> arr);

		void py_encode_table_riichi_step2(const mahjong::Table& table, int riichi_tile, pybind11::array_t<dtype> arr);

		void py_encode_action(const mahjong::Table& table, int pid, pybind11::array_t<dtype> arr);

		void py_encode_action_riichi_step2(pybind11::array_t<dtype> arr);

		std::vector<BaseTile> py_get_riichi_tiles(const Table& table);
	}

	namespace v3
	{
		pybind11::dict py_encode(v3::TableTokenizer& enc, int current_player, bool riichi_stage2);
	}

	namespace v4
	{
		pybind11::array_t<bool> py_events(const v4::HandTrackEncoder& enc);
		pybind11::list py_decide_points(const v4::HandTrackEncoder& enc);
	}
}

namespace_mahjong_end
#endif
#ifndef TRAINING_DATA_ENCODING_H
#define TRAINING_DATA_ENCODING_H

#include "pybind11/numpy.h"
#include <vector>
#include "Table.h"

using dtype = int8_t;

namespace TrainingDataEncoding {

	constexpr size_t size_player = 4, 
		col_hand = 0,
		size_hand = 6,
		col_fulu = col_hand + size_hand,
		size_fulu = 6,		
		col_river = col_fulu + size_fulu * size_player,
		size_river = 10,
		col_field = col_river + size_river * size_player,
		size_field = 10,
		col_last = col_field + size_field,
		size_last = 1;

	constexpr size_t n_tile_types = 9 + 9 + 9 + 7;
	constexpr size_t n_col = size_hand + size_fulu * size_player + size_river * size_player + size_field + size_last;
	constexpr size_t n_row = n_tile_types;

	constexpr int red_dora_flag = 1 << 6;
	constexpr int field_wind_flag = 1 << 6;
	constexpr int self_wind_flag = 1 << 7;
	constexpr int riichi_flag = 1 << 7;
	constexpr int naki_flag = 1 << 8;
	constexpr int number_mask = 0b000111;
	constexpr int fromhand_mask = 0b111000;
	constexpr int dora_indicator_mask = 0b000111;
	constexpr int dora_mask = 0b111000;

	void encode_table(const Table& table, int pid, pybind11::array_t<dtype> arr);
	void encode_action();
};

#endif
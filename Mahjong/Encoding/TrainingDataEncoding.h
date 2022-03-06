#ifndef TRAINING_DATA_ENCODING_H
#define TRAINING_DATA_ENCODING_H

#include <vector>
#include "Table.h"

namespace TrainingDataEncoding {

	using dtype = int8_t;
	constexpr size_t size_player = 4,
		row_hand = 0,
		size_hand = 6,
		row_CallGroup = row_hand + size_hand,
		size_CallGroup = 6,
		row_river = row_CallGroup + size_CallGroup * size_player,
		size_river = 10,
		row_field = row_river + size_river * size_player,
		size_field = 10,
		row_last = row_field + size_field,
		size_last = 1,
		row_action = row_last + size_last,
		size_action = 12,
		row_oracle = row_action + size_action
		;

	constexpr int row_discard = 0,
		row_chi_left = 1,
		row_chi_middle = 2,
		row_chi_right = 3,
		row_pon = 4,
		row_ankan = 5,
		row_kan = 6,
		row_kakan = 7,
		row_riichi = 8,
		row_ron = 9,
		row_tsumo = 10;

	constexpr size_t n_tile_types = 9 + 9 + 9 + 7;
	constexpr size_t n_row = size_hand + size_CallGroup * size_player + size_river * size_player + size_field + size_last;
	constexpr size_t n_col = n_tile_types;

	void encode_table(const Table& table, int pid, bool use_oracle, dtype* data);
	void encode_actions_vector(const Table& table, int pid, dtype* data);
};

#endif
#ifndef TRAINING_DATA_ENCODING_H
#define TRAINING_DATA_ENCODING_H

#include <vector>
#include "Table.h"

namespace TrainingDataEncoding {

	using dtype = int8_t;
	constexpr size_t size_player = 4,
		row_hand = 0,
		size_hand = 6,
		row_fulu = row_hand + size_hand,
		size_fulu = 6,
		row_river = row_fulu + size_fulu * size_player,
		size_river = 10,
		row_field = row_river + size_river * size_player,
		size_field = 10,
		row_last = row_field + size_field,
		size_last = 1,
		row_action = row_last + size_last,
		size_action = 12,
		row_oracle = row_action + size_action
		;

	constexpr size_t n_tile_types = 9 + 9 + 9 + 7;
	constexpr size_t n_row = size_hand + size_fulu * size_player + size_river * size_player + size_field + size_last;
	constexpr size_t n_col = n_tile_types;

	void encode_table(const Table& table, int pid, bool use_oracle, dtype* data);
	void encode_actions_vector(const Table& table, int pid, dtype* data);
};

#endif
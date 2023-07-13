#ifndef TRAINING_DATA_ENCODING_V1_H
#define TRAINING_DATA_ENCODING_V1_H

#include <vector>
#include "Table.h"

namespace_mahjong

namespace TrainingDataEncoding {
	namespace v1 {
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

		constexpr int row_discard = 0 + row_action,
			row_chi_left = 1 + row_action,
			row_chi_middle = 2 + row_action,
			row_chi_right = 3 + row_action,
			row_pon = 4 + row_action,
			row_ankan = 5 + row_action,
			row_kan = 6 + row_action,
			row_kakan = 7 + row_action,
			row_riichi = 8 + row_action,
			row_ron = 9 + row_action,
			row_tsumo = 10 + row_action,
			row_kyushukyuhai = 11 + row_action;

		constexpr size_t n_tile_types = 9 + 9 + 9 + 7;
		constexpr size_t n_row = size_hand + size_fulu * size_player + size_river * size_player + size_field + size_last + size_action + size_hand * (size_player - 1);
		constexpr size_t n_col = n_tile_types;

		constexpr size_t n_actions = 47;

		void encode_table(const Table& table, int pid, bool use_oracle, dtype* data);
		void encode_table_riichi_step2(const Table& table, BaseTile riichi_tile, dtype* data);
		void encode_actions_vector(const Table& table, int pid, dtype* data);
		void encode_actions_vector_riichi_step2(dtype* data);

		std::vector<BaseTile> get_riichi_tiles(const Table& table);
	}
};

namespace_mahjong_end
#endif
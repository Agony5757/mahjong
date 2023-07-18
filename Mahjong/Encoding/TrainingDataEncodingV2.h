#ifndef TRAINING_DATA_ENCODING_V2_H
#define TRAINING_DATA_ENCODING_V2_H

#include <vector>
#include "Table.h"

namespace_mahjong

namespace TrainingDataEncoding {
	namespace v2
	{
		constexpr size_t n_tile_types = 9 + 9 + 9 + 7;
		constexpr size_t n_row = n_tile_types;

		struct SelfInformation
		{
			enum EnumSelfInformation
			{
				pos_hand_1,
				pos_hand_2,
				pos_hand_3,
				pos_hand_4,
				pos_dora_1,
				pos_dora_2,
				pos_dora_3,
				pos_dora_4,
				pos_dora_indicator_1,
				pos_dora_indicator_2,
				pos_dora_indicator_3,
				pos_dora_indicator_4,
				pos_aka_dora,
				pos_game_wind,
				pos_self_wind,
				pos_tsumo_tile,
				pos_discarded_by_player_1,
				pos_discarded_by_player_2,
				pos_discarded_by_player_3,
				pos_discarded_by_player_4,
				n_self_information
			};
			std::array<int8_t, n_self_information * n_tile_types> self_info;

		};

		constexpr size_t n_tile_types_include_aka = n_tile_types + 3;
		constexpr size_t n_actions = 12;
		constexpr size_t n_players = 4;
		constexpr size_t n_step_actions = n_tile_types_include_aka + n_actions + n_players;
		constexpr size_t offset_tile = 0;
		constexpr size_t offset_action = offset_tile + n_tile_types_include_aka;
		constexpr size_t offset_player = offset_action + n_actions;

		// a record structure for encoding
		struct GamePlayRecord
		{
			std::array<int8_t, n_step_actions> records;
		};

		struct GlobalInformation
		{
			enum EnumGlobalInformation
			{
				pos_game_number,
				pos_game_size,
				pos_honba,
				pos_kyoutaku,
				pos_self_wind,
				pos_game_wind,
				pos_player_0_point, // self
				pos_player_1_point, // next
				pos_player_2_point, // opposite
				pos_player_3_point, // previous
				pos_player_0_ippatsu, // self
				pos_player_1_ippatsu, // next
				pos_player_2_ippatsu, // opposite
				pos_player_3_ippatsu, // previous
				pos_remaining_tiles,
				n_global_information
			};
			std::array<int8_t, n_global_information> global_information;
		};

		struct TableEncoder
		{
			Player* player;
			Table* table;

			GlobalInformation global_info;
		};

	}
}

namespace_mahjong_end
#endif
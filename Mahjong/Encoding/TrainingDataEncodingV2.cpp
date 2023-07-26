#include "TrainingDataEncodingV2.h"
#include "fmt/core.h"

namespace_mahjong
namespace TrainingDataEncoding {
	namespace v2 {

		bool TableEncoder::_require_update()
		{
			return record_count < table->gamelog.logsize();
		}

		void TableEncoder::init()
		{
			// After initializing Table, oya is ready to play (with 14 tiles in hand)

			// Set visible_tiles
			//   Initial dora is visible and will always be updated when "DoraReveal" is logged
			Tile* dora_indicator = table->dora_indicator[0];
			if (dora_indicator->red_dora)
			{
				visible_tiles[locate_attribute(3, dora_indicator->tile)] = 1;
			}
			else
			{
				visible_tiles[locate_attribute(0, dora_indicator->tile)] = 1;
				visible_tiles_count[dora_indicator->tile]++;
			}

			size_t pos;
			// Init static self information
			
			pos = (size_t)EnumSelfInformation::pos_dora_indicator_1;			
			self_infos[0][locate_attribute(pos, dora_indicator->tile)]++;
			self_infos[1][locate_attribute(pos, dora_indicator->tile)]++;
			self_infos[2][locate_attribute(pos, dora_indicator->tile)]++;
			self_infos[3][locate_attribute(pos, dora_indicator->tile)]++;
			
			pos = (size_t)EnumSelfInformation::pos_dora_1;
			self_infos[0][locate_attribute(pos, get_dora_next(dora_indicator->tile))]++;
			self_infos[1][locate_attribute(pos, get_dora_next(dora_indicator->tile))]++;
			self_infos[2][locate_attribute(pos, get_dora_next(dora_indicator->tile))]++;
			self_infos[3][locate_attribute(pos, get_dora_next(dora_indicator->tile))]++;

			pos = (size_t)EnumSelfInformation::pos_self_wind;
			global_infos[0][pos] = (table->players[0].wind - Wind::East) + BaseTile::_1z;
			global_infos[1][pos] = (table->players[1].wind - Wind::East) + BaseTile::_1z;
			global_infos[2][pos] = (table->players[2].wind - Wind::East) + BaseTile::_1z;
			global_infos[3][pos] = (table->players[3].wind - Wind::East) + BaseTile::_1z;

			pos = (size_t)EnumSelfInformation::pos_game_wind;
			global_infos[0][pos] =
			global_infos[1][pos] =
			global_infos[2][pos] =
			global_infos[3][pos] = (table->game_wind - Wind::East) + BaseTile::_1z;
			
			// Init static global information
			pos = (size_t)EnumGlobalInformation::pos_game_number;
			global_infos[0][pos] =
			global_infos[1][pos] =
			global_infos[2][pos] =
			global_infos[3][pos] = (table->game_wind - Wind::East) * 4 + (table->oya);

			pos = (size_t)EnumGlobalInformation::pos_game_size;
			global_infos[0][pos] =
			global_infos[1][pos] =
			global_infos[2][pos] =
			global_infos[3][pos] = 7;

			pos = (size_t)EnumGlobalInformation::pos_honba;
			global_infos[0][pos] =
			global_infos[1][pos] =
			global_infos[2][pos] =
			global_infos[3][pos] = table->honba;

			pos = (size_t)EnumGlobalInformation::pos_kyoutaku;
			global_infos[0][pos] =
			global_infos[1][pos] =
			global_infos[2][pos] =
			global_infos[3][pos] = table->kyoutaku;

			pos = (size_t)EnumGlobalInformation::pos_self_wind;
			global_infos[0][pos] = table->players[0].wind;
			global_infos[1][pos] = table->players[1].wind;
			global_infos[2][pos] = table->players[2].wind;
			global_infos[3][pos] = table->players[3].wind;

			pos = (size_t)EnumGlobalInformation::pos_game_wind;
			global_infos[0][pos] =
			global_infos[1][pos] =
			global_infos[2][pos] =
			global_infos[3][pos] = table->game_wind - Wind::East;

			pos = (size_t)EnumGlobalInformation::pos_player_0_point;
			global_infos[0][pos] = table->players[0].score / 100;
			global_infos[1][pos] = table->players[1].score / 100;
			global_infos[2][pos] = table->players[2].score / 100;
			global_infos[3][pos] = table->players[3].score / 100;

			pos = (size_t)EnumGlobalInformation::pos_player_1_point;
			global_infos[0][pos] = table->players[3].score / 100;
			global_infos[1][pos] = table->players[0].score / 100;
			global_infos[2][pos] = table->players[1].score / 100;
			global_infos[3][pos] = table->players[2].score / 100;

			pos = (size_t)EnumGlobalInformation::pos_player_2_point;
			global_infos[0][pos] = table->players[2].score / 100;
			global_infos[1][pos] = table->players[3].score / 100;
			global_infos[2][pos] = table->players[0].score / 100;
			global_infos[3][pos] = table->players[1].score / 100;

			pos = (size_t)EnumGlobalInformation::pos_player_3_point;
			global_infos[0][pos] = table->players[1].score / 100;
			global_infos[1][pos] = table->players[2].score / 100;
			global_infos[2][pos] = table->players[3].score / 100;
			global_infos[3][pos] = table->players[0].score / 100;

			pos = (size_t)EnumGlobalInformation::pos_remaining_tiles;
			global_infos[0][pos] = 
			global_infos[1][pos] = 
			global_infos[2][pos] = 
			global_infos[3][pos] = table->get_remain_tile();
			

			_update_hand(0);
			_update_hand(1);
			_update_hand(2);
			_update_hand(3);
			_update_visible_tiles();

			// The first record shouldn't be taken into account.
			record_count = table->gamelog.logsize();
		}

		void TableEncoder::_update_from_ankan(const BaseGameLog& log)
		{
			// update visible tiles
			auto tile = log.call_tiles[0]->tile;
			visible_tiles[locate_attribute(0, tile)] = 1;
			visible_tiles[locate_attribute(1, tile)] = 1;
			visible_tiles[locate_attribute(2, tile)] = 1;
			visible_tiles[locate_attribute(3, tile)] = 1; 
			visible_tiles_count[tile] = 4;

			// update the corresponding self_info
			int player = log.player;
			_update_hand(player);
			_update_visible_tiles();
		}

		void TableEncoder::_update_from_call(const BaseGameLog& log)
		{
			// update visible tiles
			for (auto tile : log.call_tiles)
			{
				auto basetile = tile->tile;
				if (tile->red_dora)
					visible_tiles[locate_attribute(3, basetile)] = 1;
				else
				{
					visible_tiles[locate_attribute(visible_tiles_count[basetile]++, basetile)] = 1;
				}
			}

			// update the corresponding self_info
			int player = log.player;
			_update_hand(player);
			_update_visible_tiles();
		}

		void TableEncoder::_update_from_kakan(const BaseGameLog& log)
		{
			// update visible tiles
			auto tile = log.tile->tile;
			visible_tiles[locate_attribute(0, tile)] = 1;
			visible_tiles[locate_attribute(1, tile)] = 1;
			visible_tiles[locate_attribute(2, tile)] = 1;
			visible_tiles[locate_attribute(3, tile)] = 1;
			visible_tiles_count[tile] = 4;

			// update the corresponding self_info
			int player = log.player;
			_update_hand(player);
			_update_visible_tiles();
		}

		void TableEncoder::_update_from_discard(const BaseGameLog& log, bool fromhand)
		{
			auto tile = log.tile;
			auto basetile = tile->tile;
			int player = log.player;
			if (tile->red_dora)
				visible_tiles[locate_attribute(3, basetile)] = 1;
			else
			{
				visible_tiles[locate_attribute(visible_tiles_count[basetile]++, basetile)] = 1;
			}

			// set furiten area
			for (int i = 0; i < 4; ++i)
			{
				int p = (log.player + i) % 4;
				size_t pos_discarded_by = p + (size_t)EnumSelfInformation::pos_discarded_by_player_1;
				self_infos[i][locate_attribute(pos_discarded_by, basetile)] = 1;
			}

			_update_hand(player);
			_update_visible_tiles();
		}

		void TableEncoder::_update_from_riichi(const BaseGameLog& log, bool fromhand)
		{
			auto tile = log.tile;
			auto basetile = tile->tile;
			int player = log.player;
			if (tile->red_dora)
				visible_tiles[locate_attribute(3, basetile)] = 1;
			else
			{
				visible_tiles[locate_attribute(visible_tiles_count[basetile]++, basetile)] = 1;
			}

			// set furiten area
			for (int i = 0; i < 4; ++i)
			{
				int p = (log.player + i) % 4;
				size_t pos_discarded_by = p + (size_t)EnumSelfInformation::pos_discarded_by_player_1;
				self_infos[i][locate_attribute(pos_discarded_by, basetile)] = 1;
			}

			_update_hand(player);
			_update_visible_tiles();
		}

		void TableEncoder::_update_from_riichi_success(const BaseGameLog& log)
		{
			int player = log.player;
			size_t pos_kyoutaku = (size_t)EnumGlobalInformation::pos_kyoutaku;
			for (int i = 0; i < 3; ++i)
			{
				int p = (player + i) % 4;
				size_t pos_player = (size_t)EnumGlobalInformation::pos_player_0_point + p;
				global_infos[i][pos_player] -= 10;
			}
			global_infos[0][pos_kyoutaku] += 1;
			global_infos[1][pos_kyoutaku] += 1;
			global_infos[2][pos_kyoutaku] += 1;
			global_infos[3][pos_kyoutaku] += 1;
		}

		void TableEncoder::_update_hand(int player)
		{
			std::array<int, n_tile_types> ntiles = { 0 };
			std::array<dtype, 4 * n_col_self_info> hand_cols = { 0 };
			auto& hand = table->players[player].hand;
			constexpr size_t offset_tile = (size_t)EnumSelfInformation::pos_hand_1;
			constexpr size_t offset_akadora = (size_t)EnumSelfInformation::pos_aka_dora;

			for (size_t i = 0; i < hand.size(); ++i) {
				int tile_type = (hand[i]->tile);
				hand_cols[locate_attribute(ntiles[tile_type] + offset_tile, tile_type)] = 1;
				++ntiles[tile_type];

				if (hand[i]->red_dora)
				{
					hand_cols[locate_attribute(offset_akadora, tile_type)] = 1;
				}
			}

			auto& self_info = self_infos[player];
			// overwrite self_info with hand_cols
			memcpy(self_info.data(), hand_cols.data(), sizeof(hand_cols));
		}

		void TableEncoder::_update_from_draw(const BaseGameLog& log, bool from_rinshan)
		{
			int player = log.player;
			auto& self_info = self_infos[player];
			_update_hand(player);

			constexpr size_t offset_tsumo = (size_t)EnumSelfInformation::pos_tsumo_tile;
			auto hand = table->players[player].hand;
			if (hand.size() % 3 == 2)
			{
				int tile_type = hand.back()->tile;
				self_info[locate_attribute(offset_tsumo, tile_type)] = 1;
			}
			else
			{
				for (int tile_type = 0; tile_type < n_tile_types; ++tile_type)
				{
					self_info[locate_attribute(offset_tsumo, tile_type)] = 0;
				}
			}

			global_infos[0].back()--;
			global_infos[1].back()--;
			global_infos[2].back()--;
			global_infos[3].back()--;
		}

		void TableEncoder::_update_from_dora_reveal(const BaseGameLog& log)
		{
			auto tile = log.tile;
			auto dora_indicator = tile->tile;
			if (tile->red_dora)
				visible_tiles[locate_attribute(3, dora_indicator)] = 1;
			else
			{
				visible_tiles[locate_attribute(visible_tiles_count[dora_indicator]++, dora_indicator)] = 1;
			}
			_update_visible_tiles();

			constexpr size_t offset_dora_indicator = (size_t)EnumSelfInformation::pos_dora_indicator_1;
			constexpr size_t offset_dora = (size_t)EnumSelfInformation::pos_dora_indicator_1;
			auto dora = get_dora_next(dora_indicator);
			for (auto& self_info : self_infos)
			{
				self_info[locate_attribute(offset_dora_indicator, dora_indicator)]++;
				self_info[locate_attribute(offset_dora, dora)]++;
			}
		}

		void TableEncoder::_update_visible_tiles()
		{			
			constexpr size_t offset = (size_t)EnumSelfInformation::pos_discarded_number_1 * n_col_self_info;
			constexpr size_t szbytes = 4 * n_col_self_info * sizeof(decltype(visible_tiles[0]));
			memcpy(self_infos[0].data() + offset, visible_tiles.data(), szbytes);
			memcpy(self_infos[1].data() + offset, visible_tiles.data(), szbytes);
			memcpy(self_infos[2].data() + offset, visible_tiles.data(), szbytes);
			memcpy(self_infos[3].data() + offset, visible_tiles.data(), szbytes);
		}

		void TableEncoder::_update_record(const BaseGameLog& log)
		{
			game_record_t record = { 0 };
			
			static auto tile2idx = [](Tile* tile) -> size_t
			{
				if (tile->red_dora)
				{
					switch (tile->tile)
					{
					case _5m:
						return n_tile_types;
					case _5p:
						return n_tile_types + 1;
					case _5s:
						return n_tile_types + 2;
					default:
						throw std::runtime_error("Bad tile.");
					}
				}
				else
					return (size_t)(tile->tile);
			};

			int player = log.player;
			if (log.call_tiles.size() != 0)
			{
				for (auto tile : log.call_tiles)
				{
					record[tile2idx(tile)] = 0;
				}
			}

			if (log.action == LogAction::DrawNormal || log.action == LogAction::DrawRinshan)
			{
				for (int i = 0; i < 4; ++i)
				{
					if (i == player)
					{
						record[tile2idx(log.tile)] = 1;
					}
				}
			}
			else if (log.action != LogAction::Chi && log.tile)
			{
				record[tile2idx(log.tile)] = 1;
			}

			switch (log.action)
			{
			case LogAction::DrawNormal:
				record[(size_t)EnumGameRecordAction::DrawNormal] = 1;
				break;
			case LogAction::DrawRinshan:
				record[(size_t)EnumGameRecordAction::DrawRinshan] = 1;
				break;
			case LogAction::DiscardFromHand:
				record[(size_t)EnumGameRecordAction::DiscardFromHand] = 1;
				break;
			case LogAction::DiscardFromTsumo:
				record[(size_t)EnumGameRecordAction::DiscardFromTsumo] = 1;
				break;
			case LogAction::Chi: {
					int chitile = log.tile->tile;
					int handtile1 = log.call_tiles[0]->tile;
					int handtile2 = log.call_tiles[1]->tile;

					if (handtile2 < handtile1)
					{
						std::swap(handtile1, handtile2); 
						throw std::runtime_error("An abnormal LogAction object.");
					}

					if (chitile < handtile1)
						record[(size_t)EnumGameRecordAction::ChiLeft] = 1;
					else if (chitile > handtile2)
						record[(size_t)EnumGameRecordAction::ChiRight] = 1;
					else
						record[(size_t)EnumGameRecordAction::ChiMiddle] = 1;
					break;
			    }
			case LogAction::Pon:
				record[(size_t)EnumGameRecordAction::Pon] = 1;
				break;
			case LogAction::Kan:
				record[(size_t)EnumGameRecordAction::Kan] = 1;
				break;
			case LogAction::KaKan:
				record[(size_t)EnumGameRecordAction::Kakan] = 1;
				break;
			case LogAction::AnKan:
				record[(size_t)EnumGameRecordAction::Ankan] = 1;
				break;
			case LogAction::RiichiDiscardFromHand:
				record[(size_t)EnumGameRecordAction::RiichiFromHand] = 1;
				break;
			case LogAction::RiichiDiscardFromTsumo:
				record[(size_t)EnumGameRecordAction::RiichiFromTsumo] = 1;
				break;
			case LogAction::RiichiSuccess:
				record[(size_t)EnumGameRecordAction::RiichiSuccess] = 1;
				break;
			case LogAction::DoraReveal:
				// this does not involve record update.
				break;
			default:
				throw std::runtime_error("Bad LogAction (not handled in the _update_record).");
			}

			records[0].push_back(record);
			records[1].push_back(record);
			records[2].push_back(record);
			records[3].push_back(record);
			for (int i = 0; i < 4; ++i)
			{
				int p = (player + i) % 4;
				records[i].back()[offset_player + p] = 0;
			}
		}

		void TableEncoder::_update_ippatsu()
		{
			for (int player = 0; player < 4; ++player) {
				for (int i = 0; i < 4; ++i)
				{
					int p = (player + i) % 4;
					size_t pos_ippatsu = p + (size_t)EnumGlobalInformation::pos_player_0_ippatsu;
					global_infos[i][pos_ippatsu] = table->players[player].ippatsu ? 1 : 0;
				}
			}

		}

		void TableEncoder::update()
		{
			while (_require_update())
			{
				auto& log = table->gamelog[record_count];
				switch (log.action)
				{
				case LogAction::AnKan:
					_update_from_ankan(log);
					break;
				case LogAction::Pon:
				case LogAction::Chi:
				case LogAction::Kan:
					_update_from_call(log);
					break;
				case LogAction::KaKan:
					_update_from_kakan(log);
					break;
				case LogAction::DiscardFromHand:
					_update_from_discard(log, DiscardFromHand);
					break;
				case LogAction::DiscardFromTsumo:
					_update_from_discard(log, DiscardFromTsumo);
					break;
				case LogAction::RiichiDiscardFromHand:
					_update_from_riichi(log, DiscardFromHand);
					break;
				case LogAction::RiichiDiscardFromTsumo:
					_update_from_riichi(log, DiscardFromTsumo);
					break;
				case LogAction::RiichiSuccess:
					_update_from_riichi_success(log);
					break;
				case LogAction::DrawNormal:
					_update_from_draw(log, DrawNormally);
					break;
				case LogAction::DrawRinshan:
					_update_from_draw(log, DrawFromRinshan);
					break;
				case LogAction::DoraReveal:
					_update_from_dora_reveal(log);
					break;
				case LogAction::Kyushukyuhai:
				case LogAction::Ron:
				case LogAction::Tsumo:
					// Actually do nothing
					break;
				default:
					throw std::runtime_error("Bad LogAction.");					
				}
				
				_update_record(log);
				_update_ippatsu();

				++record_count;
			}
		}
	}
}
namespace_mahjong_end

#include "TrainingDataEncodingV2.h"
#include "fmt/core.h"

namespace_mahjong
namespace TrainingDataEncoding {
	namespace v2 {

		bool TableEncoder::_require_update()
		{
			return records[3].size() < table->gamelog.logsize();
		}

		void TableEncoder::init()
		{
			// After initializing Table, oya is ready to play (with 14 tiles in hand)

			// Set visible_tiles
			//   Initial dora is visible and will always be updated when "DoraReveal" is logged
			Tile* dora = table->dora_indicator[0];
			if (dora->red_dora)
			{
				visible_tiles[locate_attribute(3, dora->tile)] = 1;
			}
			else
			{
				visible_tiles[locate_attribute(0, dora->tile)] = 1;
			}

			// Init static global information
			size_t pos;
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

		}

		void TableEncoder::_update_from_ankan(const BaseGameLog& log)
		{
			// update visible tiles
			auto tile = log.call_tiles[0]->tile;
			visible_tiles[locate_attribute(0, tile)] = 1;
			visible_tiles[locate_attribute(1, tile)] = 1;
			visible_tiles[locate_attribute(2, tile)] = 1;
			visible_tiles[locate_attribute(3, tile)] = 1;

			// update the corresponding self_info
			int player = log.player;
			_update_hand(player);
			_update_visible_tiles();

			// update the game_record

			// update the global information
			// 
			// (no need)
		}

		void TableEncoder::_update_hand(int player)
		{
			std::array<int, n_tile_types> ntiles = { 0 };
			auto& hand = table->players[player].hand;
			auto& self_info = self_infos[player];
			constexpr size_t offset_tile = (size_t)EnumSelfInformation::pos_hand_1;
			constexpr size_t offset_akadora = (size_t)EnumSelfInformation::pos_aka_dora;

			for (size_t i = 0; i < hand.size(); ++i) {
				int tile_type = (hand[i]->tile);
				self_info[locate_attribute(ntiles[tile_type] + offset_tile, tile_type)] = 1;
				++ntiles[tile_type];

				if (hand[i]->red_dora)
				{
					self_info[locate_attribute(offset_akadora, tile_type)] = 1;
				}
			}
		}

		void TableEncoder::_update_visible_tiles()
		{
			size_t offset = EnumSelfInformation::pos_discarded_number_1
			memcpy(self_infos[0].data() + )
		}

		void TableEncoder::update()
		{
			while (_require_update())
			{
				auto& log = table->gamelog[records[0].size()];
				switch (log.action)
				{
				case LogAction::AnKan:
					_update_from_ankan(log);
					return;
				case LogAction::Pon:
				case LogAction::Chi:
				case LogAction::Kan:
					_update_from_call(log);
					return;
				case LogAction::KaKan:
					_update_from_kakan(log);
					return;
				case LogAction::DiscardFromHand:
					_update_from_discard(log, DiscardFromHand);
					return;
				case LogAction::DiscardFromTsumo:
					_update_from_discard(log, DiscardFromTsumo);
					return;
				case LogAction::RiichiDiscardFromHand:
					_update_from_riichi(log, DiscardFromHand);
					return;
				case LogAction::RiichiDiscardFromTsumo:
					_update_from_riichi(log, DiscardFromTsumo);
					return;
				case LogAction::RiichiSuccess:
					_update_from_riichi_success(log);
				case LogAction::DrawNormal:
					_update_from_draw(log, DrawNormally);
					return;
				case LogAction::DrawRinshan:
					_update_from_draw(log, DrawFromRinshan);
					return;
				case LogAction::DoraReveal:
					_update_from_dora_reveal(log);
				case LogAction::Kyushukyuhai:
				case LogAction::Ron:
				case LogAction::Tsumo:
					// Actually do nothing
					return;
				default:
					throw std::runtime_error("Bad LogAction.");
				}
			}
		}
	}
}
namespace_mahjong_end

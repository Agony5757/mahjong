#include "TrainingDataEncoding.h"

using namespace std;

namespace TrainingDataEncoding {

	/* For obs encoding */
	constexpr inline size_t locate(size_t row, size_t col)
	{
		return n_col * row + col;
	}

	constexpr inline dtype& get(dtype* data, size_t row, size_t col)
	{
		return data[locate(row, col)];
	}

	void encode_hand(const vector<Tile*> hand, int hand_offset, bool can_kyushukyuhai, dtype* data)
	{
		array<dtype, n_tile_types> ntiles = { 0 };

		for (size_t i = 0; i < hand.size(); ++i) {
			auto id = char(hand[i]->tile);
			get(data, hand_offset + ntiles[id], id) = 1;
			++ntiles[id];

			if (hand[i]->red_dora) {
				get(data, hand_offset + 5, id) = 1;
			}
			
			if (can_kyushukyuhai && is_幺九牌(hand[i]->tile)) {
				get(data, row_action + 11, id) = 1;
			}
		}		
	}

	void encode_river(const vector<RiverTile>& tiles, int pid, int hand_offset, dtype* data)
	{
		array<dtype, n_tile_types> ntiles = { 0 };
		array<dtype, n_tile_types> nfromhand = { 0 };

		for (auto t : tiles) {
			auto id = char(t.tile->tile);
			if (hand_offset >= 0) {
				get(data, hand_offset + 4, id) = 1;
			}
			int pos = row_river + pid * size_river;
			get(data, pos + ntiles[id], id) = 1;

			if (t.fromhand) {
				get(data, pos + 4 + ntiles[id], id) = 1; 
			}

			++ntiles[id];
			if (t.tile->red_dora) 
				get(data, pos + 8, id) = 1; 
			
			if (t.riichi) 
				get(data, pos + 9, id) = 1; 			
		}
	}

	void encode_fulu(const vector<Fulu>& fulus, dtype* data, size_t pid)
	{
		array<dtype, n_tile_types> ntiles = { 0 };
		for (const auto& f : fulus) {
			for (int i = 0; i < f.tiles.size(); ++i) {
				auto& t = f.tiles[i];
				auto id = char(t->tile);
				size_t pos = row_fulu + pid * size_fulu;
				get(data, pos + ntiles[id], id) = 1;
				++ntiles[id];

				if (i == f.take)
					get(data, pos + 4, id) = 1;

				if (t->red_dora)
					get(data, pos + 5, id) = 1;
			}
		}
	}

	void encode_field(const Table& table, const Player& player, dtype* data)
	{
		array<dtype, n_tile_types> dora_ind_count = { 0 };
		array<dtype, n_tile_types> dora_count = { 0 };

		for (size_t i = 0; i < table.dora_spec; ++i) {
			auto dora_indicator_id = char(table.宝牌指示牌[i]->tile);
			auto dora_id = char(get_dora_next(table.宝牌指示牌[i]->tile));

			get(data, row_field + dora_ind_count[dora_indicator_id], dora_indicator_id) = 1;
			dora_ind_count[dora_indicator_id]++;
			get(data, row_field + 4 + dora_count[dora_indicator_id], dora_id) = 1;
			dora_count[dora_id]++;
		}
		get(data, row_field + 8, table.场风 + BaseTile::_1z) = 1;
		get(data, row_field + 9, player.wind + BaseTile::_1z) = 1;
	}

	void encode_last(int action_tile, dtype* data)
	{		
		if (action_tile >= 0) get(data, row_last, action_tile) = 1;
	}
	
	void encode_self_actions_matrix(const vector<SelfAction> &self_actions, int action_tile, bool &can_kyushukyuhai, dtype* data)
	{
		can_kyushukyuhai = false;
		array<dtype, n_tile_types> row_discard{0};
		for (auto sa : self_actions) {
			int row_offset = -1;
			array<dtype, n_tile_types> row_data{0}; 
			switch (sa.action) {
			case BaseAction::出牌:
				row_discard[sa.correspond_tiles[0]->tile] = 1;
				break;
			case BaseAction::暗杠:
				row_data[sa.correspond_tiles[0]->tile] = 1;
				row_offset = 5;
				break;
			case BaseAction::加杠:
				row_data[sa.correspond_tiles[0]->tile] = 1;
				row_offset = 7;
				break;
			case BaseAction::立直:
				row_data[sa.correspond_tiles[0]->tile] = 1;
				row_offset = 8;
				break;
			case BaseAction::自摸:
				row_data[action_tile] = 1;
				row_offset = 10;
				break;
			case BaseAction::九种九牌:
				can_kyushukyuhai = true;
				break;
			default:
				throw runtime_error("Bad SelfAction (while encoding).");
			}
			if (row_offset >= 0) memcpy(data + locate(row_action + row_offset, 0), row_data.data(), sizeof(dtype) * n_col);
		}
		memcpy(data + locate(row_action, 0), row_discard.data(), sizeof(dtype) * n_col);
	}

	void encode_response_actions_matrix(const vector<ResponseAction> &response_actions, int action_tile, dtype *data)
	{		
		for (auto ra : response_actions) {
			int row_offset = -1;
			array<dtype, n_tile_types> row_data{0}; 
			switch (ra.action) {				
			case BaseAction::pass:
				break;
			case BaseAction::吃:
				row_data[action_tile] = 1;
				if (action_tile > ra.correspond_tiles[0]->tile)
					if (action_tile < ra.correspond_tiles[1]->tile) row_offset = 2; // middle							
					else row_offset = 3; // right						
				else row_offset = 1; // left
				break;
			case BaseAction::碰:
				row_data[ra.correspond_tiles[0]->tile] = 1;
				row_offset = 4;
				break;
			case BaseAction::杠:
				row_data[ra.correspond_tiles[0]->tile] = 1;
				row_offset = 6;
				break;
			case BaseAction::荣和:
			case BaseAction::抢杠:
			case BaseAction::抢暗杠:
				row_data[action_tile] = 1;
				row_offset = 9;
				break;
			default:			
				throw runtime_error("Bad ResponseAction (while encoding).");
			}
			memcpy(data + locate(row_action + row_offset, 0), row_data.data(), sizeof(dtype) * n_col);
		}
	}
	
	void encode_action_matrix(const Table& table, int action_tile, bool &can_kyushukyuhai, dtype* data)
	{
		if (table.get_phase() <= Table::PhaseEnum::P4_ACTION) 
		{
		    auto &&actions = table.get_self_actions();
			encode_self_actions_matrix(actions, action_tile, can_kyushukyuhai, data);
		}
		else if (table.get_phase() < Table::PhaseEnum::GAME_OVER)
		{
		    auto &&actions = table.get_response_actions();
			encode_response_actions_matrix(actions, action_tile, data);
		}
	}

	void encode_table(const Table& table, int pid, bool use_oracle, dtype* data)
	{
		const auto& ps = table.players;
		const auto& hand = ps[pid].hand;

		int action_tile = -1;
		if (table.get_phase() <= int(Table::PhaseEnum::P4_ACTION)) {
			if (pid == table.get_phase()) {
				action_tile = hand.back()->tile;
			}
			else {
				throw runtime_error("Pid does not match Table::Phase.");
			}
		}
		else {
			auto& ct = table.selected_action.correspond_tiles;
			if (ct.size() > 0) {
				action_tile = ct[0]->tile;
			}
			else {
				throw runtime_error("Bad corresponding tile (while encoding).");
			}
		}
		printf("**** Encode Last. %d *****\n", action_tile);
		encode_last(action_tile, data);
		bool can_kyushukyuhai = false;
		/* if kyushukyuhai is available, then Kyuhais are extra recorded (row=92). */
		encode_action_matrix(table, action_tile, can_kyushukyuhai, data);

		encode_hand(hand, row_hand, can_kyushukyuhai, data);		

		for (int i = 0; i < 4; ++i) {				
			int hand_offset = 0;
			int encode_pid = (i + pid) % 4;
			if (i != 0) 
				if (use_oracle) hand_offset = row_oracle + size_hand * (i - 1);				
				else hand_offset = -1;
			else hand_offset = row_hand;
			encode_river(ps[encode_pid].river.river, i, hand_offset, data);
			encode_fulu(ps[encode_pid].副露s, data, i);
		}

		encode_field(table, ps[pid], data);

		if (use_oracle) {
			for (int i = 1; i < 4; ++i) {
				int other_pid = (pid + i) % 4;
				encode_hand(ps[other_pid].hand, row_oracle + size_hand * (i - 1), false, data);
			}
		}
	}
	/* obs encoding over */

	/* For action encoding */

	void encode_self_actions_vector(const vector<SelfAction>& actions, dtype* data)
	{
		bool riichi_able = false;
		for (auto sa : actions) {
			switch (sa.action) {
			case BaseAction::出牌:
				data[int(sa.correspond_tiles[0]->tile)] = 1;
				break;
			case BaseAction::暗杠:
				data[38] = 1;
				break;
			case BaseAction::加杠:
				data[40] = 1;
				break;
			case BaseAction::立直:
				data[41] = 1;
				riichi_able = true;
				break;
			case BaseAction::自摸:
				data[43] = 1;
				break;
			case BaseAction::九种九牌:
				data[44] = 1;
				break;
			default:
				throw runtime_error("Bad SelfAction (while encoding).");
			}
		}
		if (riichi_able) data[45] = 1;
	}
	
	void encode_response_actions_vector(const vector<SelfAction>& actions, int action_tile, dtype* data)
	{
		for (auto ra : actions) {
			switch (ra.action) {
			case BaseAction::pass:
				data[46] = 1;
				break;
			case BaseAction::吃:
				if (action_tile > ra.correspond_tiles[0]->tile)
					if (action_tile < ra.correspond_tiles[1]->tile) data[35] = 1; // middle							
					else data[36] = 1; // right						
				else data[34] = 1; // left
				break;
			case BaseAction::碰:
				data[37] = 1;
				break;
			case BaseAction::杠:
				data[39] = 1;
				break;
			case BaseAction::荣和:
			case BaseAction::抢杠:
			case BaseAction::抢暗杠:
				data[42] = 1;
				break;
			default:			
				throw runtime_error("Bad ResponseAction (while encoding).");
			}
		}
	}

	void encode_actions_vector(const Table& table, int pid, dtype* data)
	{
		const auto& ps = table.players;
		const auto& hand = ps[pid].hand;
		
		switch (table.get_phase()) {
		case Table::PhaseEnum::P1_ACTION:
		case Table::PhaseEnum::P2_ACTION:
		case Table::PhaseEnum::P3_ACTION:
		case Table::PhaseEnum::P4_ACTION:
			if (pid == table.get_phase()) {
				vector<SelfAction>&& actions = table.get_self_actions();
				encode_self_actions_vector(actions, data);
			}
			break;
		default: {	
			int action_tile = -1;
			auto& ct = table.selected_action.correspond_tiles;
			if (ct.size() > 0) {
				action_tile = ct[0]->tile;
			}		
			if (pid == table.get_phase() % 4) {
				vector<ResponseAction>&& actions = table.get_response_actions();
				encode_response_actions_matrix(actions, action_tile, data);
			}
		}
		}
	}
}
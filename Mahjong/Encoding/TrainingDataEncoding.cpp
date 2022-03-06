#include "TrainingDataEncoding.h"
#include "fmt/core.h"

using namespace std;

namespace TrainingDataEncoding {

	/* For obs encoding */
	constexpr inline size_t locate(size_t row, size_t col)
	{
		if (row >= n_row || col >= n_col)
		{
			throw runtime_error(fmt::format("Bad access to [{},{}]", row, col));
		}
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
				get(data, row_kyushukyuhai, id) = 1;
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
		
		for (auto sa : self_actions) {
			switch (sa.action) {
			case BaseAction::出牌:
				get(data, row_discard, sa.correspond_tiles[0]->tile) = 1;
				break;
			case BaseAction::暗杠:
				get(data, row_ankan, sa.correspond_tiles[0]->tile) = 1;
				break;
			case BaseAction::加杠:
				get(data, row_kakan, sa.correspond_tiles[0]->tile) = 1;
				break;
			case BaseAction::立直:
				get(data, row_riichi, sa.correspond_tiles[0]->tile) = 1;
				break;
			case BaseAction::自摸:
				get(data, row_tsumo, action_tile) = 1;
				break;
			case BaseAction::九种九牌:
				can_kyushukyuhai = true;
				break;
			default:
				throw runtime_error("Bad SelfAction (while encoding).");
			}
		}
	}

	void encode_response_actions_matrix(const vector<ResponseAction> &response_actions, int action_tile, dtype *data)
	{		
		for (auto ra : response_actions) {
			int row_chi = 0;
			switch (ra.action) {				
			case BaseAction::pass:
				break;
			case BaseAction::吃:
				if (action_tile > ra.correspond_tiles[0]->tile)
					if (action_tile < ra.correspond_tiles[1]->tile) row_chi = row_chi_middle; // middle							
					else row_chi = row_chi_right; // right						
				else row_chi = row_chi_left; // left

				get(data, row_chi, action_tile) = 1;
				break;
			case BaseAction::碰:
				get(data, row_pon, ra.correspond_tiles[0]->tile) = 1;
				break;
			case BaseAction::杠:
				get(data, row_kan, ra.correspond_tiles[0]->tile) = 1;
				break;
			case BaseAction::荣和:
			case BaseAction::抢杠:
			case BaseAction::抢暗杠:
				get(data, row_ron, ra.correspond_tiles[0]->tile) = 1;
				break;
			default:			
				throw runtime_error("Bad ResponseAction (while encoding).");
			}
		}
	}
	
	void encode_action_matrix(const Table& table, int action_tile, bool &can_kyushukyuhai, dtype* data)
	{
		if (table.get_phase() <= Table::PhaseEnum::P4_ACTION) 
		{
		    const auto &actions = table.get_self_actions();
			encode_self_actions_matrix(actions, action_tile, can_kyushukyuhai, data);
		}
		else if (table.get_phase() < Table::PhaseEnum::GAME_OVER)
		{
		    const auto &actions = table.get_response_actions();
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
		}
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
				int encode_pid = (pid + i) % 4;
				encode_hand(ps[encode_pid].hand, row_oracle + size_hand * (i - 1), false, data);
			}
		}
	}

	void encode_table_riichi_step2(const Table& table, BaseTile riichi_tile, dtype *data)
	{
		const auto &actions = table.get_self_actions();
		auto iter = find_if(actions.begin(), actions.end(), 
		    [riichi_tile](SelfAction sa) 
			{ return sa.action == BaseAction::立直 && sa.correspond_tiles[0]->tile == riichi_tile; });
		if (iter == actions.end()) 
		    throw runtime_error(fmt::format("Cannot riichi with {}", riichi_tile));

		get(data, row_hand + 4, riichi_tile) = 1;
		array<dtype, size_action * n_col> buffer;
		get(buffer.data(), row_riichi - row_discard, riichi_tile) = 1;
		memcpy(data + locate(row_action, 0), buffer.data(), buffer.size());
	}

	/* obs encoding over */

	/* For action encoding */

	void encode_self_actions_vector(const vector<SelfAction>& actions, dtype* data)
	{
		for (auto &sa : actions) {
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
				data[46] = 1;
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
	}
	
	void encode_response_actions_vector(const vector<ResponseAction>& actions, int action_tile, dtype* data)
	{
		for (auto &ra : actions) {
			switch (ra.action) {
			case BaseAction::pass:
				data[45] = 1;
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
				const auto &actions = table.get_self_actions();
				encode_self_actions_vector(actions, data);
			}
			break;
		default: {	
			int action_tile = -1;
			const auto& ct = table.selected_action.correspond_tiles;
			if (ct.size() > 0) {
				action_tile = ct[0]->tile;
			}		
			if (pid == table.get_phase() % 4) {
				const auto &actions = table.get_response_actions();
				encode_response_actions_vector(actions, action_tile, data);
			}
		}
		}
	}

	void encode_actions_vector_riichi_step2(dtype* data)
	{
		array<dtype, n_actions> buffer = { 0 };
		buffer[41] = 1;
		buffer[46] = 1;
		memcpy(data, buffer.data(), buffer.size());
	}

	/* action encoding over */
	
	std::vector<BaseTile> get_riichi_tiles(const Table& table)
	{
		std::vector<BaseTile> bt;
		for (const auto &sa : table.get_self_actions()){
			if (sa.action == BaseAction::立直) {
				bt.push_back(sa.correspond_tiles[0]->tile);
			}
		}
		return bt;
	}
}
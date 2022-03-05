#include "TrainingDataEncoding.h"

using namespace std;

namespace TrainingDataEncoding {
	constexpr size_t locate(size_t n_col, size_t row, size_t col)
	{
		return n_col * row + col;
	}
	const static dtype m0[] = { 0,0,0,0 };
	const static dtype m1[] = { 1,0,0,0 };
	const static dtype m2[] = { 1,1,0,0 };
	const static dtype m3[] = { 1,1,1,0 };
	const static dtype m4[] = { 1,1,1,1 };
	const static dtype* m[] = { m0,m1,m2,m3,m4 };

	/* tile counter
	 鸣  立  红   手切   张数
	0~1 0~1 0~1   0~4   0~4
	 8   7   6    5~3   2~0
	*/

	void encode_river(const vector<RiverTile>& tiles, int pid,
		array<dtype, n_tile_types>& ntiles, dtype* data)
	{
		ntiles.fill(0);
		array<dtype, n_tile_types> nfromhand = { 0 };

		for (auto t : tiles) {
			auto id = char(t.tile->tile);

			size_t pos = locate(n_col, id, col_river + pid * size_river);
			data[pos + ntiles[id]] = 1;

			ntiles[id]++;
			if (t.fromhand) {
				data[pos + 4 + nfromhand[id]] = 1;
				nfromhand[id]++;
			}
			if (t.tile->red_dora) {
				data[pos + 8] = 1;
			}
			if (t.riichi) {
				data[pos + 9] = 1;
			}
		}
	}

	//void encode_hand_tiles(const vector<Tile*>& tiles, array<dtype, n_tile_types>& ntiles)
	//{
	//	ntiles.fill(0);
	//	for (auto t : tiles) {
	//		auto id = char(t->tile);
	//		ntiles[id]++;
	//		if (t->red_dora) ntiles[id] |= red_dora_flag;
	//	}
	//}

	void encode_hand(const vector<Tile*> hand, const array<dtype, n_tile_types>& river, dtype* data)
	{
		array<dtype, n_tile_types> ntiles = { 0 };

		for (size_t i = 0; i < hand.size(); ++i) {

			auto id = char(hand[i]->tile);
			size_t pos = locate(n_col, id, col_hand);
			data[pos + ntiles[id]] = 1;
			ntiles[id]++;

			if (river[id] > 0) {
				data[pos + 4] = 1;
			}

			if (hand[i]->red_dora) {
				data[pos + 5] = 1;
			}
		}
	}

	void encode_fulu(const vector<Fulu>& fulus, dtype* data, size_t pid)
	{
		array<dtype, n_tile_types> ntiles = { 0 };
		for (const auto& f : fulus) {
			for (int i = 0; i < f.tiles.size(); ++i) {
				auto& t = f.tiles[i];
				auto id = char(t->tile);
				size_t pos = locate(n_col, id, col_fulu + pid * size_fulu);
				data[pos + ntiles[id]] = 1;
				ntiles[id]++;

				if (t->red_dora)
					data[pos + 5] = 1;

				if (i == f.take)
					data[pos + 6] = 1;

			}
		}
	}


	//void encode_river(const array<dtype, n_tile_types>& ntiles, dtype* data, int pid)
	//{
	//	for (size_t i = 0; i < n_tile_types; ++i) {
	//		size_t pos = locate(n_col, i, col_river + pid * size_river);

	//		memcpy(data + pos, m[ntiles[i] & number_mask], sizeof(dtype) * 4);
	//		memcpy(data + pos + 4, m[(ntiles[i] & fromhand_mask) >> 3], sizeof(dtype) * 4);

	//		data[pos + 8] = (ntiles[i] & red_dora_flag) ? 1 : 0;
	//		data[pos + 9] = (ntiles[i] & riichi_flag) ? 1 : 0;
	//	}
	//}

	void count_field(const Table& table, const Player& player, array<dtype, n_tile_types>& ntiles)
	{
		ntiles.fill(0);
		auto& dora_indicator = table.宝牌指示牌;
		for (auto i = 0; i < table.dora_spec; ++i) {
			Tile* t = dora_indicator[i];
			ntiles[char(get_dora_next(t->tile))] += (1 << 3);
			ntiles[char(t->tile)]++;
		}
		for (int t = 0; t <= 4; ++t) {
			if (t == table.场风) ntiles[t + BaseTile::_1z] |= field_wind_flag;
			if (t == player.wind) ntiles[t + BaseTile::_1z] |= self_wind_flag;
		}
	}

	void encode_field(const Table& table, const Player& player, dtype* data)
	{
		array<dtype, n_tile_types> dora_ind_count = { 0 };
		array<dtype, n_tile_types> dora_count = { 0 };

		for (size_t i = 0; i < table.dora_spec; ++i) {
			auto dora_indicator_id = char(table.宝牌指示牌[i]->tile);
			auto dora_id = char(get_dora_next(table.宝牌指示牌[i]->tile));

			size_t pos = locate(n_col, dora_indicator_id, col_field);
			data[pos + dora_ind_count[dora_indicator_id]] = 1;
			dora_ind_count[dora_indicator_id]++;
			data[pos + dora_count[dora_id]] = 1;
			dora_count[dora_id]++;
		}
		data[locate(n_col, table.场风 + BaseTile::_1z, col_field + 8)] = 1;
		data[locate(n_col, player.wind + BaseTile::_1z, col_field + 9)] = 1;
	}

	void encode_last(const Table& table, int pid, dtype* data)
	{
		char id = -1;
		switch (table.get_phase()) {
		case Table::PhaseEnum::P1_ACTION:
		case Table::PhaseEnum::P2_ACTION:
		case Table::PhaseEnum::P3_ACTION:
		case Table::PhaseEnum::P4_ACTION:
			if (pid == int(table.get_phase())) {
				char id = table.players[pid].hand.back()->tile;
				// data[locate(n_col, id, col_last)] = 1;
			}
		default: {
			auto& ct = table.selected_action.correspond_tiles;
			if (ct.size() > 0) {
				char id = ct[0]->tile;
				// data[locate(n_col, id, col_last)] = 1;
			}
		}
		}
		for (char i = _1m; i < _7z; ++i) {
			data[locate(n_col, i, col_last)] = (i == id ? 1 : 0);
		}
	}

	void encode_table(const Table& table, int pid, dtype* data)
	{
		array<dtype, n_tile_types> buf;

		/* counting */
		const auto& ps = table.players;
		const auto& hand = ps[pid].hand;

		for (int i = 1; i <= 4; ++i) {
			encode_river(table.players[(i + pid)%4].river.river, pid, buf, data);
		}

		encode_hand(hand, buf, data);
		for (int i = 0; i < 4; ++i) {
			encode_fulu(ps[(i + pid) % 4].副露s, data, (i + pid) % 4);
		}
		encode_field(table, ps[pid], data);
		encode_last(table, pid, data);
	}
}
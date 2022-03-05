#include "TrainingDataEncoding.h"
#include <type_traits>
#include <typeinfo>
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

	void count_hand_tiles(const vector<Tile*>& tiles, array<dtype, n_tile_types>& ntiles)
	{
		ntiles.fill(0);
		for (auto t : tiles) {
			auto id = char(t->tile);
			ntiles[id]++;
			if (t->red_dora) ntiles[id] ^= red_dora_flag; 
		}
	}

	void encode_hand(const array<dtype, n_tile_types>& hand, const array<dtype, n_tile_types>& river, dtype* data)
	{
		for (size_t i = 0; i < n_tile_types; ++i) {
			size_t pos = locate(n_col, i, col_hand);
			memcpy(data + pos, m[hand[i] & number_mask], sizeof(dtype) * 4);
			data[pos + 4] = (river[i] > 0) ? 1 : 0;
			data[pos + 5] = (hand[i] & red_dora_flag) ? 1 : 0;
		}
	}

	void count_fulu(const vector<Fulu>& fulus, array<dtype, n_tile_types>& ntiles)
	{
		ntiles.fill(0);
		for (auto f : fulus) {
			for (auto t : f.tiles) {
				auto id = char(t->tile);
				ntiles[id]++;
				if (t->red_dora) ntiles[id] ^= red_dora_flag;
			}
			switch (f.type) {
			case Fulu::Chi:
			case Fulu::Pon:
			case Fulu::加杠:
			case Fulu::大明杠:
				ntiles[f.tiles[f.take]->tile] ^= naki_flag;
			default:
				break;
			}
		}
	}

	void encode_fulu(const array<dtype, n_tile_types>& ntiles, dtype* data, size_t pid)
	{
		for (size_t i = 0; i < n_tile_types; ++i) {
			size_t pos = locate(n_col, i, col_fulu + pid * size_fulu);
			memcpy(data + pos, m[ntiles[i] & number_mask], sizeof(dtype) * 4);
			data[pos + 4] = (ntiles[i] & naki_flag) ? 1 : 0;
			data[pos + 5] = (ntiles[i] & red_dora_flag) ? 1 : 0;
		}
	}

	void count_river_tiles(const vector<RiverTile>& tiles, array<dtype, n_tile_types>& ntiles)
	{
		ntiles.fill(0);
		for (auto t : tiles) {
			auto id = char(t.tile->tile);
			ntiles[id]++;
			if (t.tile->red_dora) ntiles[id] ^= red_dora_flag;
			if (t.fromhand) ntiles[id] += (1 << 3);
			if (t.riichi) ntiles[id] ^= riichi_flag;
		}
	}

	void encode_river(const array<dtype, n_tile_types>& ntiles, dtype* data, int pid)
	{
		for (size_t i = 0; i < n_tile_types; ++i) {
			size_t pos = locate(n_col, i, col_river + pid * size_river);

			memcpy(data + pos, m[ntiles[i] & number_mask], sizeof(dtype) * 4);
			memcpy(data + pos + 4, m[(ntiles[i] & fromhand_mask) >> 3], sizeof(dtype) * 4);

			data[pos + 8] = (ntiles[i] & red_dora_flag) ? 1 : 0;
			data[pos + 9] = (ntiles[i] & riichi_flag) ? 1 : 0;
		}
	}

	void count_field(const Table& table, const Player& player, array<dtype, n_tile_types> &ntiles)
	{
		ntiles.fill(0);
		auto& dora_indicator = table.宝牌指示牌;
		for (auto i = 0; i < table.dora_spec; ++i) {
			Tile* t = dora_indicator[i];
			ntiles[char(get_dora_next(t->tile))] += (1 << 3);
			ntiles[char(t->tile)]++;
		}
		for (int t = 0; t <= 4; ++t) {
			if (t == table.场风) ntiles[t + BaseTile::_1z] ^= field_wind_flag;
			if (t == player.wind) ntiles[t + BaseTile::_1z] ^= self_wind_flag;
		}
	}

	void encode_field(const Table& table, const Player& player, const array<dtype, n_tile_types>& ntiles, dtype *data)
	{
		for (size_t i = 0; i < n_tile_types; ++i) {
			size_t pos = locate(n_col, i, col_field);

			memcpy(data + pos, m[ntiles[i] & dora_indicator_mask], sizeof(dtype) * 4);
			memcpy(data + pos + 4, m[(ntiles[i] & dora_mask) >> 3], sizeof(dtype) * 4);

			data[pos + 8] = (ntiles[i] & field_wind_flag) ? 1 : 0;
			data[pos + 9] = (ntiles[i] & self_wind_flag) ? 1 : 0;
		}
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

	void encode_table(const Table& table, int pid, pybind11::array_t<dtype> arr)
	{
		dtype* data = arr.mutable_data();
		array<dtype, n_tile_types> hand, fulu[4], river[4], field;

		/* counting */
		const Player& p = table.players[pid];
		count_hand_tiles(p.hand, hand);
		for (int i = 0; i < 4; ++i) {
			count_fulu(table.players[i].副露s, fulu[i]);
			count_river_tiles(table.players[i].river.river, river[i]);
		}
		count_field(table, p, field);

		/* encoding */
		encode_hand(hand, river[pid], data);
		for (int i = 0; i < 4; ++i) {
			encode_fulu(fulu[(i + pid) % 4], data, (i + pid) % 4);
			encode_river(river[(i + pid) % 4], data, (i + pid) % 4);
		}
		encode_field(table, p, field, data);
		encode_last(table, pid, data);
	}
}

#include "TrainingDataEncoding.h"
#include <type_traits>
#include <typeinfo>
using namespace std;


namespace TrainingDataEncoding {

	constexpr size_t locate(size_t n_col, size_t row, size_t col)
	{
		return n_col * row + col;
	}

	/* tile counter
	 鸣  立  红   手切    张数
	0~1 0~1 0~1 000~100 000~100
	 8   7   6    5~3     2~0
	*/

	void count_hand_tiles(const vector<Tile*>& tiles, array<dtype, n_tile_types>& ntiles)
	{
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
			switch (hand[i] & number_mask) {
			case 4:	data[pos + 3] = 1;
			case 3: data[pos + 2] = 1;
			case 2: data[pos + 1] = 1;
			case 1: data[pos + 0] = 1;
			}
			if (river[i] > 0) data[pos + 4] = 1;
			if (hand[i] & red_dora_flag) data[pos + 5] = 1;
		}
	}

	void count_fulu(const vector<Fulu>& fulus, array<dtype, n_tile_types>& ntiles)
	{
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
				ntiles[char(f.tiles[f.take]->tile)] ^= naki_flag;
			}
		}
	}

	void encode_fulu(const array<dtype, n_tile_types>& ntiles, dtype* data, size_t pid)
	{
		for (size_t i = 0; i < n_tile_types; ++i) {
			size_t pos = locate(n_col, i, col_fulu + pid * size_fulu);
			switch (ntiles[i] & number_mask) {
			case 4:	data[pos + 3] = 1;
			case 3: data[pos + 2] = 1;
			case 2: data[pos + 1] = 1;
			case 1: data[pos + 0] = 1;
			}
			if (ntiles[i] & naki_flag) data[pos + 4] = 1;
			if (ntiles[i] & red_dora_flag) data[pos + 5] = 1;
		}
	}

	void count_river_tiles(const vector<RiverTile>& tiles, array<dtype, n_tile_types>& ntiles)
	{
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
			switch (ntiles[i] & number_mask) {
			case 4:	data[pos + 3] = 1;
			case 3: data[pos + 2] = 1;
			case 2: data[pos + 1] = 1;
			case 1: data[pos + 0] = 1;
			}
			switch (ntiles[i] & hand_mask) {
			case 4 << 3: data[pos + 7] = 1;
			case 3 << 3: data[pos + 6] = 1;
			case 2 << 3: data[pos + 5] = 1;
			case 1 << 3: data[pos + 4] = 1;
			}
			if (ntiles[i] & red_dora_flag) data[pos + 8] = 1;
			if (ntiles[i] & riichi_flag) data[pos + 9] = 1;
		}
	}

	void count_field(const Table& table, const Player& player, array<dtype, n_tile_types> &ntiles)
	{
		for (auto t : table.宝牌指示牌) {
			ntiles[char(get_dora_next(t->tile))] += (1 << 3);
			ntiles[char(t->tile)]++;
		}
	}

	void encode_field(const Table& table, const Player& player, const array<dtype, n_tile_types>& ntiles, dtype *data)
	{
		for (size_t i = 0; i < n_tile_types; ++i) {
			size_t pos = locate(n_col, i, col_field);
			switch (ntiles[i] & dora_indicator_mask) {
			case 4:	data[pos + 3] = 1;
			case 3: data[pos + 2] = 1;
			case 2: data[pos + 1] = 1;
			case 1: data[pos + 0] = 1;
			}
			switch (ntiles[i] & dora_mask) {
			case 4 << 3: data[pos + 7] = 1;
			case 3 << 3: data[pos + 6] = 1;
			case 2 << 3: data[pos + 5] = 1;
			case 1 << 3: data[pos + 4] = 1;
			}
		}
		data[char(table.场风 + BaseTile::_1z)] = 1;
		data[char(player.wind + BaseTile::_1z)] = 1;
	}

	void encode_last(const Table& table, int pid, dtype* data)
	{
		switch (table.get_phase()) {
		case Table::PhaseEnum::P1_ACTION:
		case Table::PhaseEnum::P2_ACTION:
		case Table::PhaseEnum::P3_ACTION:
		case Table::PhaseEnum::P4_ACTION:
			if (pid == int(table.get_phase())) {
				char id = table.players[pid].hand.back()->tile;
				data[locate(n_col, id, col_last)] = 1;
			}
		default: {
			auto& ct = table.selected_action.correspond_tiles;
			if (ct.size() > 0) {
				char id = ct[0]->tile;
				data[locate(n_col, id, col_last)] = 1;
			}
		}
		}
	}

	void encode_table(const Table& table, int pid, pybind11::array_t<dtype> arr)
	{
		dtype* data = arr.mutable_data();
		array<dtype, n_tile_types> hand{ 0 }, fulu[4]{0}, river[4]{0}, field;

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

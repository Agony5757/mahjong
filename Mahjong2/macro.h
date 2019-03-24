#pragma once

#include <vector>
#include <algorithm>
#include <type_traits>
#include "../和牌判断器/Yaku.h"

#define VERBOSE if (verbose)
#define SORT(player) player.sort_hand();
#define SORT_TILES(hand) std::sort(hand.begin(), hand.end(), tile_comparator);
#define ALLSORT player[0].sort_hand();player[1].sort_hand();player[2].sort_hand();player[3].sort_hand();

#define TEST_EQ_VERBOSE(value, expected) if (value == expected) cout<<"PASS"<<endl; else cout<<"FAIL"<<endl;

template<typename T>
bool is_in(std::vector<T> vec, const T &elem){
	if (find(vec.begin(), vec.end(), elem) != vec.end()) {
		return true;
	}
	else return false;
}

template<typename T>
std::vector<T> erase_many(std::vector<T> vec, std::vector<T> to_erase) {
	std::remove_if(vec.begin(), vec.end(), 
		[to_erase](T& elem) {is_in(to_erase, elem); });
	return vec;
}

inline std::vector<mahjong::Tile> convert_tiles_to_extern_tiles(std::vector<Tile*> tiles) {
	std::vector<mahjong::Tile> newtiles;
	for (auto tile : tiles) {
		BaseTile t = tile->tile;
		int type = (int)t / 9;
		int data = (t % 9 + 1);
		mahjong::TileType mt;
		switch (type) {
		case 0: 
			mt = mahjong::TileType::Manzu;
			newtiles.push_back(mahjong::Tile(mt, data, false));
			continue;
		case 1:
			mt = mahjong::TileType::Souzu;
			newtiles.push_back(mahjong::Tile(mt, data, false));
			continue;
		case 2:
			mt = mahjong::TileType::Ponzu;
			newtiles.push_back(mahjong::Tile(mt, data, false));
			continue;
		case 3:
			mt = mahjong::TileType::Special;
			newtiles.push_back(mahjong::Tile(mt, data, false));
			continue;
		default:
			throw std::runtime_error("??");
		}
	}
	return newtiles;
}

inline std::vector<BaseTile> convert_extern_tiles_to_basetiles(std::vector<mahjong::Tile> tiles) {
	std::vector<BaseTile> newtiles;
	for (auto tile : tiles) {
		int type;
		int number = tile.getTileNumber();
		switch (tile.getTileType()) {
		case mahjong::TileType::Manzu:
			type = 0; break;
		case mahjong::TileType::Souzu:
			type = 1; break;
		case mahjong::TileType::Ponzu:
			type = 2; break;
		case mahjong::TileType::Special:
			type = 3; break;
		default:
			throw std::runtime_error("??");
		}
		auto basetile_number = type * 9 + number;
		BaseTile t = static_cast<BaseTile>(basetile_number);
		newtiles.push_back(t);
	}
	return newtiles;
}
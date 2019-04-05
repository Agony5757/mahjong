#ifndef MACRO_H
#define MACRO_H

#include <vector>
#include <algorithm>
#include <type_traits>
#include "MahjongAlgorithm/Yaku.h"
#include "Tile.h"

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
		[&to_erase](T& elem) {is_in(to_erase, elem); });
	return vec;
}

template<class _InIt,
	class _Fn> inline
	_Fn for_all(_InIt &_Capacitor, _Fn _Func)
{	
	return for_each(_Capacitor.begin(), _Capacitor.end(), _Func);
}

inline std::vector<BaseTile> convert_tiles_to_base_tiles(std::vector<Tile*> tile) {
	std::vector<BaseTile> bts;
	for_each(tile.begin(), tile.end(), [&bts](Tile* t) {bts.push_back(t->tile); });
	return bts;
}

inline std::vector<mahjong::Tile> convert_basetiles_to_extern_tiles(std::vector<BaseTile> tiles) {
	std::vector<mahjong::Tile> newtiles;
	for (auto t : tiles) {
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

inline BaseTile convert_extern_tile_to_basetile(mahjong::Tile tile) {
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
	auto basetile_number = type * 9 + number - 1;
	BaseTile t = static_cast<BaseTile>(basetile_number);
	return t;
}

inline std::vector<BaseTile> convert_extern_tiles_to_basetiles(std::vector<mahjong::Tile> tiles) {
	std::vector<BaseTile> newtiles;
	for (auto tile : tiles) {
		newtiles.push_back(convert_extern_tile_to_basetile(tile));
	}
	return newtiles;
}

template<typename T>
bool is_same_capacitor(T a, T b) {
	if (a.size() != b.size()) {
		return false;
	}
	for (size_t i = 0; i < a.size(); ++i) {
		if (a[i] != b[i])
			return false;
	}
	return true;
}

inline std::vector<Tile*>::iterator
find_match_tile(std::vector<Tile*> tiles, BaseTile t) {
	for (auto iter = tiles.begin();
		iter != tiles.end();
		++iter) {
		if ((*iter)->tile == t) {
			return iter;
		}
	}	
	return tiles.end();
}

inline std::vector<Tile*>::iterator
find_match_tile(std::vector<Tile*> tiles, Tile* t) {
	for (auto iter = tiles.begin();
		iter != tiles.end();
		++iter) {
		if ((*iter) == t) {
			return iter;
		}
	}
	return tiles.end();
}

// 找手牌中是不是有t的重复n张牌
inline std::vector<Tile*> get_duplicate(
	std::vector<Tile*> tiles,
	BaseTile t,
	int n) {

	std::vector<Tile*> duplicate_tiles;

	int duplicates = 0;
	for (auto tile : tiles) {
		if (tile->tile == t)
			duplicates++;
	}
	if (duplicates == n) {
		for (auto tile : tiles) {
			if (tile->tile == t) {
				duplicates--;
				duplicate_tiles.push_back(tile);
			}
			if (duplicates == 0) return duplicate_tiles;
		}
	}
	else return duplicate_tiles;
}

template<typename T>
void merge_into(std::vector<T> &to, const std::vector<T> &from) {
	to.insert(to.end(), from.begin(), from.end());
}

#endif
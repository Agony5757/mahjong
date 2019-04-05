#ifndef RULE_H
#define RULE_H

#include "Tile.h"
#include "macro.h"

/* Converter & TileGroup Data Structure */

struct TileGroup {
	enum Type {
		Toitsu,
		Shuntsu,
		Koutsu,
	};
	Type type;
	std::vector<BaseTile> tiles;
	inline std::string to_string() {
		std::stringstream ss;
		ss << "[";
		for (auto tile : tiles) {
			ss << basetile_to_string(tile);
		}
		ss << "]";
		return ss.str();
	}
};

struct CompletedTiles {
	TileGroup head;
	std::vector<TileGroup> body;
	inline std::string to_string() {
		std::stringstream ss;
		ss << head.to_string() << " ";
		for_each(body.begin(), body.end(),
			[&ss](TileGroup &group) {ss << group.to_string() << " "; });
		ss << std::endl;
		return ss.str();
	}
};

// 和牌型包括了无役的情况，这是必要不充分条件，并且不需要满足有14张的条件
// 这是去掉副露，留下手牌的判断

std::vector<CompletedTiles> getCompletedTiles(std::vector<BaseTile> tiles);

TileGroup convert_extern_tilegroup_to_internal(mahjong::TileGroup tilegroup);

CompletedTiles convert_extern_completed_tiles_to_internal(
	mahjong::CompletedTiles completed_tiles);

std::vector<CompletedTiles> convert_extern_completed_tiles_to_internal(
	std::vector<mahjong::CompletedTiles> completed_tiles);

/* 判断和牌状态 */

bool isCommon和牌型(std::vector<BaseTile> tiles);

std::vector<BaseTile> isCommon听牌型(std::vector<BaseTile> tiles);

/* 特殊役 */

bool is七对和牌型(std::vector<BaseTile> tiles);

std::vector<BaseTile> is七对听牌型(std::vector<BaseTile> tiles);

bool is国士无双和牌型(std::vector<BaseTile> tiles);

std::vector<BaseTile> is国士无双听牌型(std::vector<BaseTile> tiles);

// 不考虑无役的听牌情况
std::vector<BaseTile> is听牌(std::vector<BaseTile> tiles);



#endif
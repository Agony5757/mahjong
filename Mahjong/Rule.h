#ifndef RULE_H
#define RULE_H

#include "Tile.h"
#include "macro.h"
#include "Yaku.h"
#include <functional>

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

bool operator<(const TileGroup& g1, const TileGroup& g2);

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
	inline void sort_body() {
		std::sort(body.begin(), body.end());
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
std::vector<BaseTile> get听牌(std::vector<BaseTile> tiles);
bool is和牌(std::vector<BaseTile> tiles);

std::vector<BaseTile> is_riichi_able(std::vector<Tile*> hands, bool 门清);

bool can_ron(std::vector<Tile*> hands, Tile* get_tile);
bool can_tsumo(std::vector<Tile*> hands);

std::vector<Yaku> get_立直_双立直(bool double_riichi, bool riichi, bool 一发);

std::vector<Yaku> get_平和(CompletedTiles complete_tiles, bool 门清, BaseTile);
std::vector<Yaku> get_门前自摸(bool 门清, bool 自摸);

std::vector<Yaku> get_四暗刻_三暗刻(CompletedTiles complete_tiles);

/* Forwar Decl */
class Player;

std::vector<Yaku> get_yaku_tsumo(Player *player);
std::vector<Yaku> get_yaku_ron(Player *player, Tile* get_tile);

#endif
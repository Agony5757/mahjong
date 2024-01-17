#ifndef RULE_H
#define RULE_H

#include "Tile.h"
#include "macro.h"
#include "Yaku.h"


namespace_mahjong

/* Converter & TileGroup Data Structure */

struct TileGroup {
	enum Type {
		Toitsu,
		Shuntsu,
		Koutsu,
	};
	Type type;
	std::vector<BaseTile> tiles;
	inline std::string to_string() const {
		std::stringstream ss;
		ss << "[";
		for (auto tile : tiles) {
			ss << basetile_to_string(tile);
		}
		ss << "]";
		return ss.str();
	}
	inline BaseTile* find(BaseTile basetile) {
		for (auto &iter : tiles) {
			if (iter == basetile)
				return &iter;
		}
		return nullptr;
	}
	inline void sort_tiles() {
		std::sort(tiles.begin(), tiles.end());
	}
	inline void set_tiles(std::vector<BaseTile> ts) {
		tiles = ts;		
		sort_tiles();
	}
};


inline bool operator<(const TileGroup &g1, const TileGroup &g2)
{
	if (g1.type < g2.type) { return true; }
	if (g1.type > g2.type) { return false; }
	
	return g1.tiles[0] < g2.tiles[0];
}

inline bool operator==(const TileGroup &g1, const TileGroup &g2) {
	if (g1.tiles.size() != g2.tiles.size()) {
		return false;
	}
	for (int i = 0; i < g1.tiles.size(); ++i) {
		if (g1.tiles != g2.tiles) return false;
	}
	return true;
}

inline bool operator!=(const TileGroup &g1, const TileGroup &g2) {
	if (g1 == g2) return false;
	return true;
}

struct CompletedTiles {
	TileGroup head;
	std::vector<TileGroup> body;
	inline std::string to_string() {
		std::stringstream ss;
		ss << head.to_string() << " ";
		std::for_each(body.begin(), body.end(),
			[&ss](TileGroup &group) {ss << group.to_string() << " "; });
		ss << std::endl;
		return ss.str();
	}
	inline void sort_body() {
		for (auto& g : body) { g.sort_tiles(); }
		std::sort(body.begin(), body.end());
	}
};

inline bool operator<(CompletedTiles c1, CompletedTiles c2) {
	if (c1.head < c2.head) return true;
	if (c2.head < c1.head) return false;

	if (c1.body.size() > c2.body.size()) return false;
	if (c1.body.size() < c2.body.size()) return true;
	
	for (int i = 0; i < c1.body.size(); i++) {
		if (c1.body[i] < c2.body[i]) return true;
		if (c2.body[i] < c1.body[i]) return false;
	}
	
	return false;
}

inline bool operator==(CompletedTiles c1, CompletedTiles c2) {
	if (c1.head != c2.head) return false;
	if (c1.body.size() != c2.body.size()) return false;
	for (int i = 0; i < c1.body.size(); ++i) {
		if (c1.body[i] != c2.body[i]) return false;
	}
	return true;
}

inline bool operator!=(const CompletedTiles& c1, const CompletedTiles& c2) {
	if (c1 == c2) return false;
	return false;
}

class TileSplitter
{
public:
	static TileSplitter& GetInstance();
	void reset();

	//std::vector<CompletedTiles> testGetYaku(const Player& p, const Tile& agariTile, bool isTsumo);

	std::vector<CompletedTiles> get_all_completed_tiles(const std::vector<BaseTile>& curTiles);
	bool has_one_completed_tiles(const std::vector<BaseTile>& curTiles);

private:
	TileSplitter() = default;
	TileSplitter(const TileSplitter& other) = delete;
	~TileSplitter() = default;

	CompletedTiles completed_tiles;
	bool has_head = false;
};

// 和牌型包括了无役的情况，这是必要不充分条件，并且不需要满足有14张的条件
// 这是去掉副露，留下手牌的判断

std::vector<CompletedTiles> get_completed_tiles(std::vector<BaseTile> tiles);
bool has_completed_tiles(std::vector<BaseTile> tiles);
//TileGroup convert_extern_tilegroup_to_internal(mahjong_algorithm::TileGroup tilegroup);
//
//CompletedTiles convert_extern_completed_tiles_to_internal(
//	mahjong_algorithm::CompletedTiles completed_tiles);
//
//std::vector<CompletedTiles> convert_extern_completed_tiles_to_internal(
//	std::vector<mahjong_algorithm::CompletedTiles> completed_tiles);

/* 判断和牌状态 */

bool is_ordinary_shape(std::vector<BaseTile> tiles);

std::vector<BaseTile> get_ordinary_atari_hai(std::vector<BaseTile> tiles);

/* 特殊役 */

bool is_7toitsu_shape(std::vector<BaseTile> tiles);
std::vector<BaseTile> get_7toitsu_atari_hai(std::vector<BaseTile> tiles);
bool is_kokushi_shape(std::vector<BaseTile> tiles);
std::vector<BaseTile> get_kokushi_atari_hai(std::vector<BaseTile> tiles);

/* 判断九莲牌型 （因为不属于特殊役，因此只需要从get_ordinary_atari_hai里面获取听牌 */
bool is_churen_9_shape(std::vector<BaseTile> tiles);
bool is_churen_shape(std::vector<BaseTile> tiles);

// 不考虑无役的听牌情况
std::vector<BaseTile> get_atari_hai(std::vector<BaseTile> tiles, const std::vector<BaseTile> &except_tiles);
bool is_tenpai(std::vector<BaseTile> tiles, const std::vector<BaseTile> &except_tiles);
bool is_agari_shape(std::vector<BaseTile> tiles);

std::vector<Tile*> is_riichi_able(const std::vector<Tile*> &hands, 
	const std::vector<BaseTile>& basetiles, bool Menzen);

bool can_ron(const std::vector<Tile*> &hands, Tile* get_tile);
bool can_tsumo(const std::vector<Tile*> &hands);

namespace_mahjong_end

#endif
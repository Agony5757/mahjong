#ifndef PLAYER_H
#define PLAYER_H

#include "Action.h"
#include "Tile.h"
#include "macro.h"
#include "Rule.h"
#include "RoundToWin.h"

namespace_mahjong

// Forward Decl
class Table;

class RiverTile {
public:
	Tile* tile;

	// 第几张牌丢下去的
	int number;

	// 是不是立直后弃牌
	bool riichi;

	// 这张牌明面上还在不在河里
	bool remain;

	// true为手切，false为摸切
	bool fromhand;
};

class River {
	// 记录所有的弃牌，而不是仅仅在河里的牌
public:
	std::vector<RiverTile> river;
	inline std::vector<BaseTile> to_basetile() {
		std::vector<BaseTile> basetiles;
		for (auto &tile : river) {
			basetiles.push_back(tile.tile->tile);
		}
		return basetiles;
	}
	inline std::string to_string() const {
		std::stringstream ss;

		for (auto tile : river) {
			ss << tile.tile->to_string() << tile.number;
			if (tile.fromhand)
				ss << "h";
			if (tile.riichi)
				ss << "r";
			if (!tile.remain)
				ss << "-";
			ss << " ";
		}
		return ss.str();
	}

	inline RiverTile& operator[](size_t n) {
		return river[n];
	}

	inline const RiverTile& operator[](size_t n) const {
		return river[n];
	}

	inline size_t size() const {
		return river.size();
	}

	inline void push_back(RiverTile rt) {
		river.push_back(rt);
	}

	inline void set_not_remain() {
		river.back().remain = false;
	}
};

class Player {
public:
	bool double_riichi = false;
	bool riichi = false;
	bool menzen = true;
	Wind wind;
	bool oya;
	bool furiten_round = false;
	bool furiten_river = false;
	bool furiten_riichi = false;
	int score = 25000;
	std::vector<Tile*> hand;
	River river;
	std::vector<CallGroup> call_groups;
	std::vector<BaseTile> atari_tiles;

	bool ippatsu = false;
	bool first_round = true;

	Player();
	Player(int init_score);
	inline bool is_riichi() const { return riichi || double_riichi; }
	inline bool is_furiten()  const { return furiten_round || furiten_river || furiten_riichi; }
	inline std::vector<CallGroup> get_fuuros() { return call_groups; }
	inline bool is_menzen() { return menzen; }
	inline bool is_tenpai() { return atari_tiles.size() > 0; }

	inline River get_river() { return river; }
	std::string hand_to_string() const;
	std::string river_to_string() const;
	std::string to_string() const;
	std::string tenpai_to_string() const;

	void update_atari_tiles();
	void update_furiten_river();
	void remove_atari_tiles(BaseTile t);

	inline void minogashi() {
		if (riichi) furiten_riichi = true;
		else furiten_round = true;
	}
	int get_normal向胡数() const;
	// Generate SelfAction
	std::vector<SelfAction> get_kakan() const; // 能否杠的过滤统一交给Table
	std::vector<SelfAction> get_ankan() const; // 能否杠的过滤统一交给Table
	std::vector<SelfAction> get_discard(bool after_chipon) const;
	std::vector<SelfAction> get_tsumo(const Table* table) const;
	std::vector<SelfAction> get_riichi() const;
	std::vector<SelfAction> get_kyushukyuhai() const;

	// Generate ResponseAction
	std::vector<ResponseAction> get_ron(Table*, Tile* tile);
	std::vector<ResponseAction> get_chi(Tile* tile);
	std::vector<ResponseAction> get_pon(Tile* tile);
	std::vector<ResponseAction> get_kan(Tile* tile); // 大明杠

	// Generate ResponseAction (Chan An Kan)
	std::vector<ResponseAction> get_chanankan(Tile* tile);

	// Generate ResponseAction (Chan Kan)
	std::vector<ResponseAction> get_chankan(Tile* tile);

	// Generate SelfAction after riichi
	std::vector<SelfAction> riichi_get_ankan();
	std::vector<SelfAction> riichi_get_discard();

	void execute_naki(std::vector<Tile*> tiles, Tile* tile, int relative_position);
	void remove_from_hand(Tile* tile);
	void execute_ankan(BaseTile tile);
	void execute_kakan(Tile* tile);

	/* 假听牌 */
	std::vector<BaseTile> get_false_atari_hai() const;

	/* execute discard whenever it is called by others. */
	void execute_discard(Tile* tile, int& number, bool on_riichi, bool fromhand);

	inline void set_not_remained() {
		/* 将打出的牌设置为“不存在了” */
		river.set_not_remain();
	}

	void sort_hand();
};

namespace_mahjong_end

#endif
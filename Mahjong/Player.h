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

	bool 门清 = true;
	Wind wind;
	bool 亲家;
	bool 同巡振听 = false;
	bool 舍牌振听 = false;
	bool 立直振听 = false;
	int score = 25000;
	std::vector<Tile*> hand;
	River river;
	std::vector<Fulu> 副露s;
	std::vector<BaseTile> 听牌;

	bool 一发 = false;
	bool first_round = true;

	Player();
	Player(int init_score);
	inline bool is_riichi() { return riichi || double_riichi; }
	inline bool is振听() { return 同巡振听 || 舍牌振听 || 立直振听; }
	inline std::vector<Fulu> get_fuuros() { return 副露s; }
	inline River get_river() { return river; }
	std::string hand_to_string() const;
	std::string river_to_string() const;
	std::string to_string() const;
	std::string tenpai_to_string() const;

	void update_听牌();
	void update_舍牌振听();
	void remove_听牌(BaseTile t);

	inline void 见逃() {
		if (riichi) 立直振听 = true;
		else 同巡振听 = true;
	}
	int get_normal向胡数() const;
	// Generate SelfAction
	std::vector<SelfAction> get_加杠() const ; // 能否杠的过滤统一交给Table
	std::vector<SelfAction> get_暗杠() const ; // 能否杠的过滤统一交给Table
	std::vector<SelfAction> get_打牌(bool after_chipon) const;
	std::vector<SelfAction> get_自摸(const Table* table) const ;
	std::vector<SelfAction> get_立直() const;
	std::vector<SelfAction> get_九种九牌() const;

	// Generate ResponseAction
	std::vector<ResponseAction> get_荣和(Table*, Tile* tile);
	std::vector<ResponseAction> get_Chi(Tile* tile);
	std::vector<ResponseAction> get_Pon(Tile* tile);
	std::vector<ResponseAction> get_Kan(Tile* tile); // 大明杠

	// Generate ResponseAction (抢暗杠)
	std::vector<ResponseAction> get_抢暗杠(Tile* tile);

	// Generate ResponseAction (抢杠)
	std::vector<ResponseAction> get_抢杠(Tile* tile);

	// Generate 立直后 SelfAction
	std::vector<SelfAction> riichi_get_暗杠();
	std::vector<SelfAction> riichi_get_打牌();

	void move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile, int relative_position);
	void remove_from_hand(Tile* tile);

	// 将所有的BaseTile值为tile的四个牌移动到副露区
	void play_暗杠(BaseTile tile);

	// 移动tile到副露中和它basetile相同的刻子中
	void play_加杠(Tile* tile);

	// 将牌移动到牌河（一定没有人吃碰杠）
	// remain指这张牌是不是明面上还在牌河
	void move_from_hand_to_river(Tile* tile, int& number, bool on_riichi, bool fromhand);

	inline void set_not_remained() {
		river.set_not_remain();
	}

	/*inline void move_from_hand_to_river_really(Tile* tile, int& number, bool fromhand) {
		return move_from_hand_to_river(tile, number, true, fromhand);
	}*/

	void sort_hand();
	void test_show_hand();
};

namespace_mahjong_end

#endif
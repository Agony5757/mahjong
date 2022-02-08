#ifndef PLAYER_H
#define PLAYER_H

#include "Action.h"
#include "Tile.h"

class Player {
public:
	Player();
	bool double_riichi = false;
	bool riichi = false;

	inline bool is_riichi() { return riichi || double_riichi; }

	bool 门清 = true;
	Wind wind;
	bool 亲家;
	bool 振听 = false;
	bool 立直振听 = false;

	bool is振听() { return 振听 || 立直振听; }

	int score;
	std::vector<Tile*> hand;
	River river;
	std::vector<Fulu> 副露s;
	std::string hand_to_string() const;
	std::string river_to_string() const;

	std::string to_string() const;

	bool 一发;
	bool first_round = true;

	// SelfAction
	std::vector<SelfAction> get_加杠();
	std::vector<SelfAction> get_暗杠();
	std::vector<SelfAction> get_打牌(bool after_chipon);
	std::vector<SelfAction> get_自摸(Table*);
	std::vector<SelfAction> get_立直();
	std::vector<SelfAction> get_九种九牌();

	// Response Action
	std::vector<ResponseAction> get_荣和(Table*, Tile* tile);
	std::vector<ResponseAction> get_Chi(Tile* tile);
	std::vector<ResponseAction> get_Pon(Tile* tile);
	std::vector<ResponseAction> get_Kan(Tile* tile); // 大明杠

	// Response Action (抢暗杠)
	std::vector<ResponseAction> get_抢暗杠(Tile* tile);

	// Response Action (抢杠)
	std::vector<ResponseAction> get_抢杠(Tile* tile);

	// 立直后
	std::vector<SelfAction> riichi_get_暗杠(Table* table);
	std::vector<SelfAction> riichi_get_打牌();

	void move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile);
	void remove_from_hand(Tile* tile);

	// 将所有的BaseTile值为tile的四个牌移动到副露区
	void play_暗杠(BaseTile tile);

	// 移动tile到副露中和它basetile相同的刻子中
	void play_加杠(Tile* tile);

	// 将牌移动到牌河（一定没有人吃碰杠）
	// remain指这张牌是不是明面上还在牌河
	void move_from_hand_to_river(Tile* tile, int& number, bool remain, bool fromhand);

	inline void move_from_hand_to_river_log_only(Tile* tile, int& number, bool fromhand) {
		return move_from_hand_to_river(tile, number, false, fromhand);
	}

	inline void move_from_hand_to_river_really(Tile* tile, int& number, bool fromhand) {
		return move_from_hand_to_river(tile, number, true, fromhand);
	}

	void sort_hand();
	void test_show_hand();
};

#endif
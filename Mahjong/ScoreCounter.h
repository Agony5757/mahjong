#ifndef SCORE_COUNTER_H
#define SCORE_COUNTER_H

#include <tuple>
#include <vector>
#include <sstream>
#include "Yaku.h"
#include "Tile.h"
#include "Player.h"

namespace_mahjong

struct CounterResult {
	std::vector<Yaku> yakus;
	
	// 分数的cases
	int score1 = 0;
	int score2 = 0; // 自摸时用。score1=亲，score2=子

	void calculate_score(bool 亲, bool 自摸);
	
	int fan = 0;
	int fu = 0;
};

class Table;
class Tile;

// turn 判定役的玩家
// correspond_tile (自摸为nullptr，荣和为荣和牌）
CounterResult yaku_counter(Table *table, Player &player, Tile* correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风);

//CounterResult yaku_counter_v2(Table *table, Player &player, Tile* correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风);

namespace_mahjong_end

#endif
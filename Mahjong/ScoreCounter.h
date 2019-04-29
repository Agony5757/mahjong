#ifndef SCORE_COUNTER_H
#define SCORE_COUNTER_H

#include <tuple>
#include "Yaku.h"
#include <vector>
#include "Tile.h"
#include <sstream>

struct CounterResult {
	std::vector<Yaku> yakus;
	
	// 分数的cases
	int score1;
	int score2; // 自摸时用。score1=亲，score2=子

	void calculate_score(bool 亲, bool 自摸);
	
	int fan;
	int fu;
};

class Table;
class Tile;

// turn 判定役的玩家
// correspond_tile (自摸为nullptr，荣和为荣和牌）
CounterResult yaku_counter(Table *table, int turn, Tile* correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风);

#endif
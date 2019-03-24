#pragma once

#include "Table.h"

bool is听牌(std::vector<Tile*> hand);
bool is振听(std::vector<Tile*> hand);

bool is七对(std::vector<Tile*> hand, Tile*);

bool is国士无双(std::vector<Tile*> hand, Tile*);

// 和牌型包括了无役的情况，这是必要不充分条件，并且不需要满足有14张的条件
// 这是去掉副露，留下手牌的判断
bool isCommon和牌型(std::vector<Tile*>);

// 国士无双和牌型只判断是否满足，不判断double役满的情况
bool is国士无双和牌型(std::vector<Tile*>);

bool is七对和牌型(std::vector<Tile*>);

bool can和牌(std::vector<Tile*> hand,
	std::unordered_map<Tile*, std::vector<Tile*>> fulus,
	std::vector<Tile*> river,
	Tile* newtile, // 用自摸牌(nullptr)
	bool isHaidi);
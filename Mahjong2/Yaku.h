#pragma once

#include "Tile.h"

class Yaku
{
public:
	Yaku();
	virtual bool test(std::vector<Tile*> 手牌,
		std::unordered_map<Tile*, std::vector<Tile*>> 副露s,
		std::vector<Tile*> 牌河,
	    Tile* 等待牌) = 0;
};


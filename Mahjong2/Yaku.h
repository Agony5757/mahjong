#pragma once

#include "Tile.h"

class Yaku
{
public:
	Yaku();
	virtual bool test(std::vector<Tile*> ����,
		std::unordered_map<Tile*, std::vector<Tile*>> ��¶s,
		std::vector<Tile*> �ƺ�,
	    Tile* �ȴ���) = 0;
};


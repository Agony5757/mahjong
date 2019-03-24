#pragma once
#include "Yaku.h"

class 七对 : public Yaku
{
public:
	七对(); 
	
	bool test(std::vector<Tile*> 手牌,
		std::unordered_map<Tile*, std::vector<Tile*>> 副露s,
		std::vector<Tile*> 牌河,
		Tile* 等待牌) override;

	~七对();
};


#pragma once
#include "Yaku.h"

class �߶� : public Yaku
{
public:
	�߶�(); 
	
	bool test(std::vector<Tile*> ����,
		std::unordered_map<Tile*, std::vector<Tile*>> ��¶s,
		std::vector<Tile*> �ƺ�,
		Tile* �ȴ���) override;

	~�߶�();
};


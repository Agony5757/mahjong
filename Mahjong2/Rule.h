#pragma once

#include "Table.h"

bool is����(std::vector<Tile*> hand);
bool is����(std::vector<Tile*> hand);

bool is�߶�(std::vector<Tile*> hand, Tile*);

bool is��ʿ��˫(std::vector<Tile*> hand, Tile*);

// �����Ͱ��������۵���������Ǳ�Ҫ��������������Ҳ���Ҫ������14�ŵ�����
// ����ȥ����¶���������Ƶ��ж�
bool isCommon������(std::vector<Tile*>);

// ��ʿ��˫������ֻ�ж��Ƿ����㣬���ж�double���������
bool is��ʿ��˫������(std::vector<Tile*>);

bool is�߶Ժ�����(std::vector<Tile*>);

bool can����(std::vector<Tile*> hand,
	std::unordered_map<Tile*, std::vector<Tile*>> fulus,
	std::vector<Tile*> river,
	Tile* newtile, // ��������(nullptr)
	bool isHaidi);
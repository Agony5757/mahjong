#pragma once
#include <iostream>
#include <vector>
#include <unordered_map>
#include <sstream>
using namespace std;

enum BasicTile {
	_1m, _2m, _3m, _4m, _5m, _6m, _7m, _8m, _9m,
	_1s, _2s, _3s, _4s, _5s, _6s, _7s, _8s, _9s,
	_1p, _2p, _3p, _4p, _5p, _6p, _7p, _8p, _9p,
	east, south, west, north,
	��, ��, ��
};

enum class Belong : uint8_t {
	p1��, p1��,
	p2��, p2��,
	p3��, p3��,
	p4��, p4��,
	yama,
};

struct Tile {
	BasicTile id;
	bool red_dora;
	Belong belongs;
};

enum Wind {
	East = 1, South, West, North
};

typedef bool RiichiStat;

struct BaseGameResult {
public:
	bool ����;
	int ��;
	int ��;
	int ����;
	int score;
	bool �ٺ�;
	bool ����;
};

struct GameResult {
public:
	vector<BaseGameResult> results;
};

enum class BasePlayChoice : uint8_t {
	���� = 1 << 0,
	�Ӹ� = 1 << 1,
	���� = 1 << 2,
	���� = 1 << 3,
	��ֱ = 1 << 4,
	���� = 1 << 5,
};

struct PlayChoice {
	BasePlayChoice choice;
	vector<unique_ptr<Tile>> regard_tile;
};

enum class BaseResponseChoice : uint8_t {
	none = 1 << 0,
	�� = 1 << 1,
	�� = 1 << 2,
	�� = 1 << 3,
	�ٺ� = 1 << 4,
	�����ٺ� = 1 << 5,
};

struct ResponseChoice {
	BasePlayChoice choice;
	vector<unique_ptr<Tile>> regard_tile;
};

typedef vector<unique_ptr<Tile>> ��ɽ;
typedef vector<unique_ptr<Tile>> �ƺ�;
typedef vector<unique_ptr<Tile>> ����;
typedef vector<unique_ptr<Tile>> ��¶;
typedef unordered_map<��¶, unique_ptr<Tile>*> ��¶s;
typedef vector<unique_ptr<Tile>> ����ָʾ��;

stringstream& operator<<(stringstream& out, vector<unique_ptr<Tile>>);
stringstream& operator<<(stringstream& out, ��¶s);

void ����һ����(��ɽ& yama, int &tiles_count);
void ϴ��(��ɽ& yama, int &tiles_count);
void ����(��ɽ& yama, ���� hand, int dist_tiles_count, int& remain_valid_tiles);
void Get����ָʾ��(����ָʾ��&, const ��ɽ&);

bool �ܳ�(��¶s &fulu, ����&, Tile*);
void ��(��¶s &fulu, ����&, unique_ptr<Tile>);

bool ����(��¶s &fulu, ����&, Tile*);
void ��(��¶s &fulu, ����&, unique_ptr<Tile>);

bool �ܸ�(��¶s &fulu, ����&, Tile*);
void ��(��¶s &fulu, ����&, unique_ptr<Tile>);

bool ���ٺ�(��¶s &fulu, ����&, Tile*); // remember check furiten
void �ٺ�(��¶s &fulu, ����&, unique_ptr<Tile>);

bool ������(��¶s &fulu, ����&);
void ����(��¶s &fulu, ����&);

bool �ܰ���(��¶s &fulu, ����&);
void ����(��¶s &fulu, ����&);

void ��������(��ɽ&, ��¶s &fulu, ����&, unique_ptr<Tile>);

bool �ܼӸ�(��¶s &fulu, ����&, Tile*);
void �Ӹ�(��¶s &fulu, ����&, unique_ptr<Tile>);

bool ������(��¶s &fulu, ����&, Tile*);
void ����(��¶s &fulu, ����&, unique_ptr<Tile>);

bool ��������(��¶s &fulu, ����&, Tile*);
void ������(��¶s &fulu, ����&, unique_ptr<Tile>);

bool ����ֱ(��¶s &fulu, ����&, RiichiStat&, int score);
void ��ֱ(����&, RiichiStat&);

vector<PlayChoice> FindPlayChoice(��¶s& fulu, ����&, �ƺ�&, int score);
ResponseChoice FindResponseChoice(��¶s& fulu, ����&, �ƺ�&, int score);

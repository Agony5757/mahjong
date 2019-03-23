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
	白, 发, 中
};

enum class Belong : uint8_t {
	p1手, p1河,
	p2手, p2河,
	p3手, p3河,
	p4手, p4河,
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
	bool 流局;
	int 符;
	int 番;
	int 役满;
	int score;
	bool 荣和;
	bool 自摸;
};

struct GameResult {
public:
	vector<BaseGameResult> results;
};

enum class BasePlayChoice : uint8_t {
	暗杠 = 1 << 0,
	加杠 = 1 << 1,
	弃牌 = 1 << 2,
	自摸 = 1 << 3,
	立直 = 1 << 4,
	流局 = 1 << 5,
};

struct PlayChoice {
	BasePlayChoice choice;
	vector<unique_ptr<Tile>> regard_tile;
};

enum class BaseResponseChoice : uint8_t {
	none = 1 << 0,
	吃 = 1 << 1,
	碰 = 1 << 2,
	杠 = 1 << 3,
	荣和 = 1 << 4,
	抢杠荣和 = 1 << 5,
};

struct ResponseChoice {
	BasePlayChoice choice;
	vector<unique_ptr<Tile>> regard_tile;
};

typedef vector<unique_ptr<Tile>> 牌山;
typedef vector<unique_ptr<Tile>> 牌河;
typedef vector<unique_ptr<Tile>> 手牌;
typedef vector<unique_ptr<Tile>> 副露;
typedef unordered_map<副露, unique_ptr<Tile>*> 副露s;
typedef vector<unique_ptr<Tile>> 宝牌指示牌;

stringstream& operator<<(stringstream& out, vector<unique_ptr<Tile>>);
stringstream& operator<<(stringstream& out, 副露s);

void 创建一副牌(牌山& yama, int &tiles_count);
void 洗牌(牌山& yama, int &tiles_count);
void 发牌(牌山& yama, 手牌 hand, int dist_tiles_count, int& remain_valid_tiles);
void Get宝牌指示牌(宝牌指示牌&, const 牌山&);

bool 能吃(副露s &fulu, 手牌&, Tile*);
void 吃(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能碰(副露s &fulu, 手牌&, Tile*);
void 碰(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能杠(副露s &fulu, 手牌&, Tile*);
void 杠(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能荣和(副露s &fulu, 手牌&, Tile*); // remember check furiten
void 荣和(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能自摸(副露s &fulu, 手牌&);
void 自摸(副露s &fulu, 手牌&);

bool 能暗杠(副露s &fulu, 手牌&);
void 暗杠(副露s &fulu, 手牌&);

void 摸岭上牌(牌山&, 副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能加杠(副露s &fulu, 手牌&, Tile*);
void 加杠(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能抢杠(副露s &fulu, 手牌&, Tile*);
void 抢杠(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能抢暗杠(副露s &fulu, 手牌&, Tile*);
void 抢暗杠(副露s &fulu, 手牌&, unique_ptr<Tile>);

bool 能立直(副露s &fulu, 手牌&, RiichiStat&, int score);
void 立直(手牌&, RiichiStat&);

vector<PlayChoice> FindPlayChoice(副露s& fulu, 手牌&, 牌河&, int score);
ResponseChoice FindResponseChoice(副露s& fulu, 手牌&, 牌河&, int score);

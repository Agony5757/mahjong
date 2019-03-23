#include <iostream>
#include <vector>
#include <unordered_map>
#include <sstream>
using namespace std;

#define OUTPUT_OPEN_MESSAGE(PLAYER) \
	gameLog << "p"<<##PLAYER<<"T|";	\
	gameLog << p##PLAYER##Throw;	\
	gameLog << "p"<<##PLAYER<<"F|";	\
	gameLog << p##PLAYER##Fulus		\
		    << endl;

enum BasicTile {
	_1m, _2m, _3m, _4m, _5m, _6m, _7m, _8m, _9m,
	_1s, _2s, _3s, _4s, _5s, _6s, _7s, _8s, _9s,
	_1p, _2p, _3p, _4p, _5p, _6p, _7p, _8p, _9p,
	east, south, west, north,
	zhong, fa, bai
};

enum class Belong : uint8_t {
	p1h, p1t,
	p2h, p2t,
	p3h, p3t,
	p4h, p4t,
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

struct GameResult {
public:
	bool nagare;
	int fu;
	int fan;
	int yakuman;
	int score;
	bool ron;
	bool tsumo;
};

enum PlayChoice {
	ankan = 1 << 0,
	kakan = 1 << 1,
	throwaway = 1 << 2,
	tsumo = 1 << 3,
	riichi = 1 << 4,
	nagare = 1 << 5,
};

enum ResponseChoice {
	none = 1 << 0,
	chi = 1 << 1,
	pon = 1 << 2,
	kan = 1 << 3,
	ron = 1 << 4,
};

typedef vector<Tile> Yama;
typedef vector<Tile> Throw;
typedef vector<Tile> Hand;
typedef vector<Tile> Fulu;
typedef unordered_map<Fulu, Tile*> Fulus;
typedef vector<Tile> DoraSpec;

stringstream& operator<<(stringstream& out, vector<Tile>);
stringstream& operator<<(stringstream& out, Fulus);

void InitGenerateYamaRandom(Yama& yama, int &tiles_count);
void DistributeTiles(Yama& yama, Hand hand, int dist_tiles_count, int& remain_valid_tiles);
void GetDoraSpec(DoraSpec&, const Yama&);
void CanChi(Fulus &fulu, Hand&, Throw&);
void CallChi(Fulus &fulu, Hand&, Throw&);
void CanPon(Fulus &fulu, Hand&, Throw&);
void CallPon(Fulus &fulu, Hand&, Throw&);
void CanKan(Fulus &fulu, Hand&, Throw&);
void CallKan(Fulus &fulu, Hand&, Throw&);
void CanRon(Fulus &fulu, Hand&, Throw&); // remember check furiten
void CallRon(Fulus &fulu, Hand&, Throw&);
void CanTsumo(Fulus &fulu, Hand&);
void CallTsumo(Fulus &fulu, Hand&);
void CanRiichi(Fulus &fulu, Hand&, RiichiStat&, int);
void CallRiichi(Hand&, RiichiStat&);

PlayChoice FindPlayChoice(Fulus& fulu, Hand&, Throw&, int score);
ResponseChoice FindResponseChoice(Fulus& fulu, Hand&, Throw&, int score);

BasicTile GetNextBasicTile(BasicTile);

GameResult one_game_process(int oya, Wind game, 
	int p1score, int p2score, int p3score, int p4score,
	ostream& p1ostream, istream& p1istream,
	ostream& p2ostream, istream& p2istream,
	ostream& p3ostream, istream& p3istream,
	ostream& p4ostream, istream& p4istream
	) {
	// init game
init:
	Yama yama;
	int remain_tile = 136;
	InitGenerateYamaRandom(yama, remain_tile);
	GameResult result;
	DoraSpec spec;
	Hand p1Hand, p2Hand, p3Hand, p4Hand;
	Fulus p1Fulus, p2Fulus, p3Fulus, p4Fulus;
	Throw p1Throw, p2Throw, p3Throw, p4Throw;
	RiichiStat p1riichi = false, p2riichi = false, p3riichi = false, p4riichi = false;
	int playerturn;
	stringstream gameLog;

	GetDoraSpec(spec, yama);
	DistributeTiles(yama, p1Hand, 13, remain_tile);
	DistributeTiles(yama, p2Hand, 13, remain_tile);
	DistributeTiles(yama, p3Hand, 13, remain_tile);
	DistributeTiles(yama, p4Hand, 13, remain_tile);
	switch (oya) {
	case 1:
		goto givep1;
	case 2:
		goto givep2;
	case 3:
		goto givep3;
	case 4:
		goto givep4;
	default:
		throw invalid_argument("argument 'oya' invalid range");
	}
givep1: {
	playerturn = 1;
	auto choice = FindPlayChoice(p1Fulus, p1Hand, p1Throw, p1score);
	OUTPUT_OPEN_MESSAGE(1);
	OUTPUT_OPEN_MESSAGE(2);
	OUTPUT_OPEN_MESSAGE(3);
	OUTPUT_OPEN_MESSAGE(4);

	

	p1ostream << "CHOICE|" << choice << endl;
	int thischoice;
	p1istream >> thischoice;
}
p1play:
givep2:
p2play:
givep3:
p3play:
givep4:
p4play:
p1response:
p2response:
p3response:
p4response:
after_response:
nagare:
end:
	return result;
}
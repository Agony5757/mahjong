#ifndef GAME_RESULT_H
#define GAME_RESULT_H

#include <vector>
#include <sstream>

enum ResultType {
	荣和终局,
	自摸终局,
	无人听牌流局,
	一人听牌流局,
	两人听牌流局,
	三人听牌流局,
	四人听牌流局,
	两家荣和,
	三家荣和,

	流局满贯,

	九种九牌流局,
	四风连打,
	四杠流局,
	四家立直,
};

struct Result {
	ResultType result_type;

	int score[4];
	int fan[4];
	int fu[4];
	int 役满倍数[4];

	int n立直棒;
	int n本场;

	bool 连庄;

	inline std::string to_string() {
		using namespace std;
		stringstream ss;
		ss << "Score:" << endl;
		for (int i = 0; i < 4; ++i) {
			ss << "Player " << i << ":" << score[i] << endl;
		}
		return ss.str();
	}
	
	std::vector<int> winner;
	std::vector<int> loser;
};

// Forward Decl
class Table;
class Tile;

Result 九种九牌流局结算(Table* table);

Result 四风连打流局结算(Table* table);

Result 四立直流局结算(Table* table);
Result 四杠流局结算(Table* table);

Result 荒牌流局结算(Table* table);

Result 自摸结算(Table* table);
Result 荣和结算(Table* table, Tile* ,std::vector<int> response_player);

Result 抢暗杠结算(Table* table, Tile*, std::vector<int> response_player);
Result 抢杠结算(Table* table, Tile*, std::vector<int> response_player);

#endif
#ifndef GAME_RESULT_H
#define GAME_RESULT_H

#include <vector>
#include <sstream>
#include <unordered_map>
#include "ScoreCounter.h"
#include <array>

enum ResultType {
	荣和终局,
	自摸终局,
	荒牌流局,
	流局满贯,
	中途流局,
};

struct Result {
	ResultType result_type;
	std::unordered_map<int, CounterResult> results;

	std::array<int, 4> score;
	int 役满倍数[4];
	int n立直棒;
	int n本场;
	bool 连庄;

	inline std::string to_string() const {
		using namespace std;
		stringstream ss;
		switch (result_type) {
		case ResultType::荒牌流局:
			ss << "荒牌流局" << endl;
			break;
		case ResultType::流局满贯:
			ss << "流局满贯" << endl;
			break;
		case ResultType::荣和终局:
			ss << "荣和终局" << endl;
			break;
		case ResultType::中途流局:
			ss << "中途流局" << endl;
			break;
		case ResultType::自摸终局:
			ss << "自摸终局" << endl;
			break;
		default:
			throw STD_RUNTIME_ERROR_WITH_FILE_LINE_FUNCTION("ResultType Unknown.");
		}
		ss << "Score:" << endl;
		for (int i = 0; i < 4; ++i) {
			ss << "Player " << i << ":" << score[i] << endl;
		}
		for (auto result : results) {
			ss << "Player" << result.first << ":" << yakus_to_string(result.second.yakus)
				<< "|" << result.second.fan << "番" << result.second.fu << "符"
				<< endl;
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
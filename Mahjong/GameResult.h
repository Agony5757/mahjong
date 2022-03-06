#ifndef GAME_RESULT_H
#define GAME_RESULT_H

#include <vector>
#include <sstream>
#include <unordered_map>
#include "ScoreCounter.h"
#include <array>

enum class ResultType {
	Error = -1,
	RonAgari,
	TsumoAgari,
	Ryukyouku_Notile,
	NagashiMangan,
	Ryukyouku_Interval,
};

inline const char* result_type_str(ResultType type)
{
	static const char* result_type_strs[] =
	{
		"RonAgari",
		"TsumoAgari",
		"Ryukyouku_Notile",
		"NagashiMangan",
		"Ryukyouku_Interval",
	};
	constexpr size_t len = sizeof(result_type_strs) / sizeof(result_type_strs[0]);
	return (int(type) >= len || int(type) < 0) ? 
		"Error type" : result_type_strs[(int)type];
}

struct Result {
	ResultType result_type = ResultType::Error;
	std::unordered_map<int, CounterResult> results;

	std::vector<int> winner;
	std::vector<int> loser;
	std::array<int, 4> score;
	int n_yakuman[4];
	int n_riichibo;
	int n_honba;
	bool renchan; // 連荘

	inline std::string to_string() const {
		std::string result_str;
		for (auto result : results) {
			result_str += fmt::format("Player {} : {} | {} fan - {} fu\n",
				result.first, yakus_to_string(result.second.yakus)
				, result.second.fan, result.second.fu);
		}
		return fmt::format("{} Score: {} \n{}",
			result_type_str(result_type),
			score_to_string(score),
			result_str);
	}
};

// Forward Decl
class Table;
class Tile;

Result generate_result_9hai(Table* table);
Result generate_result_4wind(Table* table);
Result generate_result_4riichi(Table* table);
Result generate_result_4kan(Table* table);
Result generate_result_notile(Table* table);
Result generate_result_tsumo(Table* table);
Result generate_result_ron(Table* table, Tile* ,std::vector<int> response_player, bool chankan = false, bool chanankan = false);
Result generate_result_chanankan(Table* table, Tile*, std::vector<int> response_player);
Result generate_result_chankan(Table* table, Tile*, std::vector<int> response_player);

#endif
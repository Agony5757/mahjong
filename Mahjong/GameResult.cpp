#include "GameResult.h"
#include "Table.h"
#include "ScoreCounter.h"
#include "macro.h"
#include "Rule.h"

namespace_mahjong
using namespace std;

static Result 中途流局结算(Table *table) {
	Result result;
	result.result_type = ResultType::中途流局;
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->players[i].score;

	result.连庄 = true;
	result.n本场 = table->n本场 + 1;
	result.n立直棒 = table->n立直棒;

	return result;
}

Result 九种九牌流局结算(Table *table)
{
	return 中途流局结算(table);
}

Result 四风连打流局结算(Table *table)
{
	return 中途流局结算(table);
}

Result 四立直流局结算(Table *table)
{
	return 中途流局结算(table);
}

Result 四杠流局结算(Table *table)
{
	return 中途流局结算(table);
}

bool is流局满贯(River r) {
	return all_of(r.river.begin(), r.river.end(), [](RiverTile& tile){
		if (is_幺九牌(tile.tile->tile) && tile.remain) {
			// remain 表示还在河里
			// 然后全是幺九牌
			return true;
		}
		return false;
	});
}

Result 荒牌流局结算(Table * table)
{
	//cout << "Warning: 罚符 is not considered" << endl;
	//cout << "Warning: 流局满贯 is not considered" << endl;

	Result result;
	
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->players[i].score;

	int 流局满贯人数 = 0;
	bool 流局满贯[4] = { false,false,false,false };
	// 统计流局满贯的人数
	for (int i = 0; i < 4; ++i) {
		if (is流局满贯(table->players[i].river)) {
			流局满贯[i] = true;
			流局满贯人数++;
		}
	}
	
	if (流局满贯人数 > 0) {
		result.result_type = ResultType::流局满贯;
		if (流局满贯[table->庄家])
			result.连庄 = true;
		else 
			result.连庄 = false;

		result.n本场 = table->n本场 + 1;
		result.n立直棒 = table->n立直棒;
		if (流局满贯人数 == 4) {
			// 不涉及到分数支付
		}
		else if (流局满贯人数 == 3) {
			if (流局满贯[table->庄家])
			{
				result.score[table->庄家] += 2000;
				for (int i = 0; i < 4; ++i) {
					if (流局满贯[i])
						result.score[i] += 2000;
					else
						result.score[i] -= 8000;
				}
			}
			else
			{
				for (int i = 0; i < 4; ++i) {
					if (流局满贯[i])
						result.score[i] += 4000;
					else
						result.score[i] -= 8000;
				}
			}
		}
		else if (流局满贯人数 == 2){
			if (流局满贯[table->庄家])
			{
				result.score[table->庄家] += 4000;
				for (int i = 0; i < 4; ++i) {
					if (流局满贯[i])
						result.score[i] += 4000;
					else
						result.score[i] -= 6000;
				}
			}
			else
			{
				result.score[table->庄家] -= 4000;
				for (int i = 0; i < 4; ++i) {
					if (流局满贯[i])
						result.score[i] += 6000;
					else
						result.score[i] -= 4000;
				}
			}
		}
		else if (流局满贯人数 == 1) {
			if (流局满贯[table->庄家])
			{
				for (int i = 0; i < 4; ++i) {
					if (流局满贯[i])
						result.score[i] += 12000;
					else
						result.score[i] -= 4000;
				}
			}
			else
			{
				result.score[table->庄家] -= 2000;
				for (int i = 0; i < 4; ++i) {
					if (流局满贯[i])
						result.score[i] += 8000;
					else
						result.score[i] -= 2000;
				}
			}
		}
	}
	else {
		result.result_type = ResultType::荒牌流局;
		// 统计罚符
		// 开始统计四人听牌的状态	
		int 听牌人数 = 0;
		bool 听牌[4] = {false, false, false, false};

		for (int i = 0; i < 4; ++i) {
			if (get听牌(convert_tiles_to_basetiles(table->players[i].hand)).size() > 0) {
				听牌[i] = true;
				听牌人数++;
			}
			else {
				听牌[i] = false;
			}
		}
		// cout << "Warning: 空听 is not considered" << endl;

		result.n本场 = table->n本场 + 1;
		result.n立直棒 = table->n立直棒;
		if (听牌[table->庄家])
			result.连庄 = true;
		else
			result.连庄 = false;

		if (听牌人数 == 4) {	}
		else if (听牌人数 == 0) { }
		else if (听牌人数 == 1) {
			for (int i = 0; i < 4; ++i) {
				if (听牌[i])
					result.score[i] += 3000;
				else
					result.score[i] -= 1000;
			}
		}
		else if (听牌人数 == 2) {
			for (int i = 0; i < 4; ++i) {
				if (听牌[i])
					result.score[i] += 1500;
				else
					result.score[i] -= 1500;
			}
		}
		else if (听牌人数 == 3) {
			for (int i = 0; i < 4; ++i) {
				if (听牌[i])
					result.score[i] += 1000;
				else
					result.score[i] -= 3000;
			}
		}		
	}
	
	return result;
}

Result 自摸结算(Table * table)
{
	Result result;
	result.result_type = ResultType::自摸终局;
	int winner = table->turn;
	// 一人赢
	result.winner.push_back(winner);

	// 三人输
	for (int i = 0; i < 4; ++i) if (i != winner) result.loser.push_back(i);

	auto yakus = yaku_counter(table, table->players[winner], nullptr, false, false, table->players[winner].wind, table->场风);
	bool is亲 = false;
	if (table->turn == table->庄家)
		is亲 = true;
	yakus.calculate_score(is亲, true);

	for (int i = 0; i < 4; ++i) {
		result.score[i] = table->players[i].score;
	}

	if (is亲) {
		for (int i = 0; i < 4; ++i) {
			if (i == winner) {
				result.score[i] += (yakus.score1 * 3);
				result.score[i] += (table->n立直棒 * 1000);
				result.score[i] += (table->n本场 * 300);
			}
			else {
				result.score[i] -= (yakus.score1);
				result.score[i] -= (table->n本场 * 100);
			}
		}
	}
	else {
		for (int i = 0; i < 4; ++i) {
			if (i == winner) {
				result.score[i] += yakus.score1;
				result.score[i] += yakus.score2;
				result.score[i] += yakus.score2;
				result.score[i] += (table->n立直棒 * 1000);
				result.score[i] += (table->n本场 * 300);
			}
			else if (i == table->庄家) {
				result.score[i] -= (yakus.score1);
				result.score[i] -= (table->n本场 * 100);
			}
			else {
				result.score[i] -= (yakus.score2);
				result.score[i] -= (table->n本场 * 100);
			}
		}
	}
	result.result_type = ResultType::自摸终局;
	
	if (winner == table->庄家)
	{
		result.n本场 = table->n本场 + 1;
		result.连庄 = true;
	}
	else
	{
		result.连庄 = false;
		result.n本场 = 0;
	}
	result.n立直棒 = 0;
	result.results.insert({ winner, yakus });
	return result;
}

Result 荣和结算(Table *table, Tile *agari_tile, std::vector<int> response_player, bool 抢杠, bool 抢暗杠)
{
	Result result;
	result.result_type = ResultType::荣和终局;

	result.loser.push_back(table->turn); // 当回合的玩家是loser
	result.winner.assign(response_player.begin(), response_player.end());

	for (int i = 0; i < 4; ++i) {
		result.score[i] = table->players[i].score;
	}

	for (auto winner : response_player) {
		auto yaku = yaku_counter(table, table->players[winner], agari_tile, 抢杠, 抢暗杠, table->players[winner].wind, table->场风);
		yaku.calculate_score(winner == table->庄家, false);

		result.results.insert({ winner, yaku });

		result.score[winner] += yaku.score1;
		result.score[table->turn] -= yaku.score1;			
	}

	// riichi 结算
	// response_player中离loser最近的那个
	int loser = table->turn;
	auto iter = min_element(response_player.begin(), response_player.end(), 
		[loser](int x1, int x2) {
		return get_distance(loser, x1) < get_distance(loser, x2);
	});
	result.score[*iter] += (table->n立直棒 * 1000);
	result.score[*iter] += table->n本场 * 300;
	result.score[table->turn] -= table->n本场 * 300;

	if (is_in(response_player, table->庄家))
	{
		result.n本场 = table->n本场 + 1;
		result.连庄 = true;
	}
	else
	{
		result.连庄 = false;
		result.n本场 = 0;
	}
	result.n立直棒 = 0;
	return result;
}

Result 抢暗杠结算(Table * table, Tile* agari_tile, std::vector<int> response_player)
{
	return 荣和结算(table, agari_tile, response_player, false, true);
}

Result 抢杠结算(Table * table, Tile* agari_tile, std::vector<int> response_player)
{
	return 荣和结算(table, agari_tile, response_player, true, false);
}

namespace_mahjong_end

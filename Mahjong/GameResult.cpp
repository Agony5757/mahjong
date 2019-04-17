#include "GameResult.h"
#include "Table.h"
#include "ScoreCounter.h"
#include "macro.h"

using namespace std;

Result 九种九牌流局结算(Table * table)
{
	// 对于这种流局，所有人的分数都是0，也既不是winner也不是loser
	Result result;
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->player[i].score;
	return result;
}

Result 四风连打流局结算(Table * table)
{
	// 对于这种流局，所有人的分数都是0，也既不是winner也不是loser
	Result result;
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->player[i].score;
	return result;
}

Result 四立直流局结算(Table * table)
{
	// 对于这种流局，所有人的分数都是0，也既不是winner也不是loser
	Result result;
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->player[i].score;
	return result;
}

Result 四杠流局结算(Table * table)
{
	// 对于这种流局，所有人的分数都是0，也既不是winner也不是loser
	Result result;
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->player[i].score;
	return result;
}

Result 荒牌流局结算(Table * table)
{
	cout << "Warning: 罚符 is not considered" << endl;
	cout << "Warning: 流局满贯 is not considered" << endl;

	// 对于这种流局，所有人的分数都是0，也既不是winner也不是loser
	Result result;
	for (int i = 0; i < 4; ++i)
		result.score[i] = table->player[i].score;
	return result;
}

Result 自摸结算(Table * table)
{
	Result result;
	int winner;
	// 先通过table的状态看看谁要和牌
	for (int i = 0; i < 4; ++i) {
		if (table->player[i].hand.size() % 3 == 2) {
			// 放心，肯定有且仅有一个手牌=3n+2的玩家，肯定是他
			// 宣告胜利
			winner = i;
			break;
		}
	}
	// 一人赢
	result.winner.push_back(winner);

	// 三人输
	for (int i = 0; i < 4; ++i) if (i != winner) result.loser.push_back(i);

	auto yakus = yaku_counter(table, table->turn, nullptr, false, false);
	bool is亲 = false;
	if (table->turn == table->庄家)
		is亲 = true;
	yakus.calculate_score(is亲, true);

	for (int i = 0; i < 4; ++i) {
		result.score[i] = table->player[i].score;
	}

	if (is亲) {
		for (int i = 0; i < 4; ++i) {
			if (i == winner) {
				result.score[i] += yakus.score1;
				result.score[i] += (table->n立直棒 * 1000);
				result.score[i] += (table->n本场 * 300);
			}
			else {
				result.score[i] -= (yakus.score1 / 3);
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

	return result;
}



Result 荣和结算(Table * table, Tile* agari_tile, std::vector<int> response_player)
{
	Result result;
	result.loser.push_back(table->turn); // 当回合的玩家是loser
	result.winner.assign(response_player.begin(), response_player.end());

	for (int i = 0; i < 4; ++i) {
		result.score[i] = table->player[i].score;
	}

	for (auto winner : response_player) {
		auto yaku = yaku_counter(table, winner, agari_tile, false, false);
		yaku.calculate_score(winner == table->庄家, false);
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

	Result result;
	result.loser.push_back(table->turn); // 当回合的玩家是loser
	result.winner.assign(response_player.begin(), response_player.end());

	for (int i = 0; i < 4; ++i) {
		result.score[i] = table->player[i].score;
	}

	for (auto winner : response_player) {
		auto yaku = yaku_counter(table, winner, agari_tile, false, true);
		yaku.calculate_score(winner == table->庄家, false);
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

Result 抢杠结算(Table * table, Tile* agari_tile, std::vector<int> response_player)
{
	Result result;
	result.loser.push_back(table->turn); // 当回合的玩家是loser
	result.winner.assign(response_player.begin(), response_player.end());

	for (int i = 0; i < 4; ++i) {
		result.score[i] = table->player[i].score;
	}

	for (auto winner : response_player) {
		auto yaku = yaku_counter(table, winner, agari_tile, true, false);
		yaku.calculate_score(winner == table->庄家, false);
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

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

	auto yakus = yaku_counter(table, table->turn, nullptr);
	

	return result;
}

Result 荣和结算(Table * table, std::vector<int> response_player)
{
	return Result();
}

Result 抢暗杠结算(Table * table, std::vector<int> response_player)
{
	return Result();
}

Result 抢杠结算(Table * table, std::vector<int> response_player)
{
	return Result();
}

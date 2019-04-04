#include "GameResult.h"
#include "Table.h"

Result 九种九牌流局结算(Table * table)
{
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

	// 因为是自摸，根据玩家是不是庄家，打点有所不同
	if (winner == table->庄家) {

	}
	else {

	}
	return result;
}

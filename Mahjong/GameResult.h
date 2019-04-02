#ifndef GAME_RESULT_H
#define GAME_RESULT_H

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

	// 自摸，一家荣和的情况
	int score;
	int fan;
	int fu;
	int 役满倍数;

	// 两家荣和的情况
	int score2;
	int fan2;
	int fu2;
	int 役满倍数2;

	// 三家荣和的情况
	int score3;
	int fan3;
	int fu3;
	int 役满倍数3;

	std::vector<int> winner;
	std::vector<int> loser;
};

Result 九种九牌流局结算() {
	return Result();
	// 对于这种流局，所有人的分数都是0，也既不是winner也不是loser
}

#endif
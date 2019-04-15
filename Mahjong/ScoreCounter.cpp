#include "ScoreCounter.h"
#include "Table.h"

#define REGISTER_SCORE(亲, 自摸, score_铳亲, score_亲自摸_all, score_铳子, score_子自摸_亲, score_子自摸_子) \
if (亲) {if (自摸){score1=score_亲自摸_all;} else{score1=score_铳亲;}} \
else {if (自摸) {score1=score_子自摸_亲; score2=score_子自摸_子;} else{score1=score_铳子;}}

CounterResult yaku_counter(Table * table, int turn, Tile * correspond_tile)
{
	return CounterResult();
}

void CounterResult::calculate_score(bool 亲, bool 自摸)
{
	if (fan >= 13) {
		REGISTER_SCORE(亲, 自摸, 48000, 16000, 32000, 16000, 8000);
	}
	else if (fan >= 11) {
		REGISTER_SCORE(亲, 自摸, 36000, 12000, 24000, 12000, 6000);
	}
	else if (fan >= 8) {
		REGISTER_SCORE(亲, 自摸, 24000, 8000 , 16000, 8000, 4000);
	}
	else if (fan >= 6) {
		REGISTER_SCORE(亲, 自摸, 18000, 6000 , 12000, 6000, 3000);
	}
	else if (fan >= 5) {
		REGISTER_SCORE(亲, 自摸, 12000, 4000 , 8000, 4000, 2000);
	}
	else if (fan >= 4) {
		// 32符 即 40符
		if (fu >= 32) {
			REGISTER_SCORE(亲, 自摸, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 25) {
			REGISTER_SCORE(亲, 自摸, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 20) {
			REGISTER_SCORE(亲, 自摸, 7700, 2600, 5200, 2600, 1300);
		}
		else if (fu >= 22) {
			REGISTER_SCORE(亲, 自摸, 11600, 3600, 7700, 3900, 2000);
		}
	}
}

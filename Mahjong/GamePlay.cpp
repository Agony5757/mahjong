#include "GamePlay.h"
#include "macro.h"

using namespace std;

std::array<int, 4> 东风局(array<Agent *, 4> agents, stringstream &ss)
{
	return FullGame(Wind::East, agents, ss);
}

std::array<int, 4> 南风局(array<Agent *, 4> agents, stringstream &ss) {
	return FullGame(Wind::South, agents, ss);
}


std::array<int, 4> FullGame(Wind 局风, std::array<Agent*, 4> agents, std::stringstream &ss)
{
	std::array<int, 4> score = { 25000,25000,25000,25000 };

	Wind 场风 = Wind::East;
	int n立直棒 = 0;
	int n本场 = 0;
	int 局 = 1; // 从东1局开始
	while (none_of(begin(score), end(score), [](int& s) {return s < 0; })) {
		ss << wind_to_string(场风) << 局 << "局" << endl;

		Table t(局 - 1, agents[0], agents[1], agents[2], agents[3]);
		t.n立直棒 = n立直棒;
		t.n本场 = n本场;
		for (int i = 0; i < 4; ++i) {
			t.player[i].score = score[i];
		}

		ss << n本场 << "本场;" << n立直棒 << "立直棒" << endl;
		Result s = t.GameProcess(false);
		ss << s.to_string();
		for (int i = 0; i < 4; ++i)
			score[i] = s.score[i];

		if (!s.连庄)
			局++; //没有连庄则流转

		n立直棒 = s.n立直棒;
		n本场 = s.n本场;

		if (场风 == next_wind(局风)) {
			// 已经西入
			if (any_of(begin(score), end(score), [](int &s) {return s > 30000; })) {
				break;
			}
		}

		if (局 == 5) {
			if (场风 == next_wind(局风)) {
				break;
				//已经南/西入，则不再入
			}
			if (any_of(begin(score), end(score), [](int &s) {return s > 30000; })) {
				break;
				// 有人30000以上，不南入
			}
			else {
				局 = 1;
				场风 = (Wind)((int)场风 + 1);
				// 下一种风开始
			}
		}

	}
	return score;
}

#include "mahjong.h"
#include "macro.h"

GameResult one_game_process(int ׯ��, Wind game, 
	int p1score, int p2score, int p3score, int p4score,
	ostream& p1ostream, istream& p1istream,
	ostream& p2ostream, istream& p2istream,
	ostream& p3ostream, istream& p3istream,
	ostream& p4ostream, istream& p4istream,
	ostream& gamelogger
	) {
	// init game
init:
	��ɽ yama;
	int remain_tile = 136;
	GameResult result;

	ϴ��(yama, remain_tile);
	
	����ָʾ�� spec;
	Get����ָʾ��(spec, yama);

	���� p1����, p2����, p3����, p4����;
	��¶s p1��¶s, p2��¶s, p3��¶s, p4��¶s;
	�ƺ� p1�ƺ�, p2�ƺ�, p3�ƺ�, p4�ƺ�;
	RiichiStat p1riichi = false, p2riichi = false, p3riichi = false, p4riichi = false;
	int playerturn;
	stringstream gameLog;

	����(yama, p1����, 13, remain_tile);
	����(yama, p2����, 13, remain_tile);
	����(yama, p3����, 13, remain_tile);
	����(yama, p4����, 13, remain_tile);
	switch (ׯ��) {
	case 1:
		goto givep1;
	case 2:
		goto givep2;
	case 3:
		goto givep3;
	case 4:
		goto givep4;
	default:
		throw invalid_argument("argument 'oya' invalid range");
	}
givep1: {
	playerturn = 1;
	OUTPUT_OPEN_MESSAGE(1);
	OUTPUT_OPEN_MESSAGE(2);
	OUTPUT_OPEN_MESSAGE(3);
	OUTPUT_OPEN_MESSAGE(4);

	auto choices = FindPlayChoice(p1��¶s, p1����, p1�ƺ�, p1score);
	p1ostream << "CHOICE|" << OUTPUT_PLAY_CHOICES(choices) << endl;
	int thischoice;
	p1istream >> thischoice;

	PlayChoice c = choices[thischoice];
	switch (c.choice) {
	case BasePlayChoice::����: {
	}
	}
	}
p1play:
givep2:
p2play:
givep3:
p3play:
givep4:
p4play:
p1response:
p2response:
p3response:
p4response:
after_response:
����label:

	������: {

}

end:
	return result;
}
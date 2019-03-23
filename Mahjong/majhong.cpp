#include "mahjong.h"
#include "macro.h"

GameResult one_game_process(int 庄家, Wind game, 
	int p1score, int p2score, int p3score, int p4score,
	ostream& p1ostream, istream& p1istream,
	ostream& p2ostream, istream& p2istream,
	ostream& p3ostream, istream& p3istream,
	ostream& p4ostream, istream& p4istream,
	ostream& gamelogger
	) {
	// init game
init:
	牌山 yama;
	int remain_tile = 136;
	GameResult result;

	洗牌(yama, remain_tile);
	
	宝牌指示牌 spec;
	Get宝牌指示牌(spec, yama);

	手牌 p1手牌, p2手牌, p3手牌, p4手牌;
	副露s p1副露s, p2副露s, p3副露s, p4副露s;
	牌河 p1牌河, p2牌河, p3牌河, p4牌河;
	RiichiStat p1riichi = false, p2riichi = false, p3riichi = false, p4riichi = false;
	int playerturn;
	stringstream gameLog;

	发牌(yama, p1手牌, 13, remain_tile);
	发牌(yama, p2手牌, 13, remain_tile);
	发牌(yama, p3手牌, 13, remain_tile);
	发牌(yama, p4手牌, 13, remain_tile);
	switch (庄家) {
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

	auto choices = FindPlayChoice(p1副露s, p1手牌, p1牌河, p1score);
	p1ostream << "CHOICE|" << OUTPUT_PLAY_CHOICES(choices) << endl;
	int thischoice;
	p1istream >> thischoice;

	PlayChoice c = choices[thischoice];
	switch (c.choice) {
	case BasePlayChoice::暗杠: {
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
流局label:

	抢暗杠: {

}

end:
	return result;
}
#include <fstream>
#include <chrono>
#include <random>
#include <iostream>
#include "Table.h"
#include "Rule.h"
#include "macro.h"
#include "GamePlay.h"
#include "tenhou.h"
#include "Encoding/TrainingDataEncoding.h"

using namespace std;
using_mahjong;

void test_tenhou_yama() {
	// void tenhou_yama_from_seed(char *MTseed_b64, BYTE yama[136]);
	const char* mtseed = "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";
	auto tenhou = TenhouShuffle::instance();
	tenhou.init(mtseed);
	vector<int> yama = tenhou.generate_yama();
	vector<int> check = {22,91,36,115,56,19,60,16,124,35,59,43,107,9,5,11,57,73,18,41,42,20,25,30,103,100,126,130,77,109,17,15,67,46,72,65,131,118,102,61,113,123,89,122,92,3,129,81,97,28,24,76,37,69,31,26,66,78,51,54,112,64,94,38,88,128,13,133,87,21,27,114,105,50,10,29,1,4,48,70,32,14,86,33,23,84,93,12,117,47,75,96,44,111,95,62,74,39,116,63,53,6,2,58,79,71,108,68,121,8,49,55,34,135,82,125,90,98,83,45,132,106,0,101,134,40,7,85,110,99,52,80,120,104,119,127};
	printf("\n--generate--\n");
	for (int i = 0; i < 136; ++i) {
		if (i != 0) printf(",");
		printf("%d", yama[i]);
	}
	printf("\n--standard--\n");
	bool match = true;
	for (int i = 0; i < 136; ++i) {
		if (i != 0) printf(",");
		printf("%d", check[i]);
		if (check[i] != yama[i])
			match = false;
	}
	printf("\n");
	if (match) printf("Correct!\n");
	else printf("Incorrect!\n");
}

void test_tenhou_game()
{
	Table table;
	table.game_init_for_replay({ 79,85,87,9,128,76,24,69,127,26,27,71,68,98,77,18,4,122,89,114,34,20,112,65,111,103,23,49,73,100,7,52,58,80,115,21,15,39,104,82,5,64,131,0,107,129,63,51,48,120,57,2,86,22,97,96,46,56,105,28,118,29,41,88,47,117,40,125,50,32,90,66,91,16,61,109,132,83,6,11,53,3,10,95,133,12,78,42,102,93,8,130,45,54,106,74,60,99,67,35,70,84,19,101,94,108,31,116,134,110,37,17,14,38,75,55,43,121,72,25,30,1,81,113,62,119,126,123,33,13,135,59,124,44,92,36, }, { 23100,23100,26000,27800, }, 0, 0, 0, 1);

	table.make_selection(7);
	table.make_selection(0);
	table.make_selection(0);
	table.make_selection(0);
	table.make_selection(0);
	table.make_selection(13);
	table.make_selection(0);
	table.make_selection(0);
	table.make_selection(0);
	table.make_selection(0);
	table.make_selection(14);
	cout << table.get_phase() << endl;
}

void test_random_play(int games = 1000)
{
	std::default_random_engine reng;
	std::uniform_real_distribution<float> ud(0, 1);

	static auto random_action = [&reng, &ud](auto actions) {
		return size_t(ud(reng) * actions.size());
	};
	timer t;
	for (int i = 0; i < games; ++i) {
		Table t;
		t.game_init();
		do {
			int selection;
			if (t.is_self_acting()) {
				auto& actions = t.get_self_actions();
				selection = random_action(actions);
			}
			else {
				auto& actions = t.get_response_actions();
				selection = random_action(actions);
			}
			t.make_selection(selection);
		} while (!t.is_over());
	}
	double time = t.get(sec);
	fmt::print("{} random plays passed, duration = {:3f} s ({:3f} s avg.)", games, time, time / games);
	fmt::print("{}", profiler::get_all_profiles_v2());
}

int main() {	
	test_random_play();
	// test_tenhou_yama();
	// test_tenhou_game();
	return 0;
}

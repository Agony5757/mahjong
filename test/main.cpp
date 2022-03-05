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

void test和牌状态1() {
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[1], yama[2], yama[3], yama[3] };

	TEST_EQ_VERBOSE(true, isCommon和牌型(convert_tiles_to_base_tiles(tiles)));
}

void test和牌状态2() {
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[0], yama[2], yama[3], yama[3] };

	TEST_EQ_VERBOSE(false, isCommon和牌型(convert_tiles_to_base_tiles(tiles)));
}

void test和牌状态3() {
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[0], yama[0], yama[1], yama[2], yama[3], yama[4],
							yama[5], yama[6], yama[7], yama[8], yama[8], yama[8] };

	for (int i = 0; i < 9; ++i) {
		tiles.push_back(yama[i]);
		// SORT_TILES(tiles);
		TEST_EQ_VERBOSE(true, isCommon和牌型(convert_tiles_to_base_tiles(tiles)));
		tiles.pop_back();
	}
}

void test和牌状态4() {
	vector<BaseTile> tiles1 = { _4m, _5m, _5m, _5m, _6m, 
	_3s, _4s, _4s,_5s,_6s,
	_6z,_6z,_5s,_5m
	};
	vector<BaseTile> tiles2 = { _4m, _5m, _5m, _5m, _6m, 
	_3s, _4s, _4s,_5s,_6s,
	_6z,_6z,_5s,_6z
	};

	vector<BaseTile> tiles3 = { _4m, _5m, _5m, _5m, _6m, 
	_3s, _4s, _4s,_5s,_6s,
	_6z,_6z,_5s
	};

	auto ten_tiles = get听牌(tiles3);
	for (auto ten_tile : ten_tiles){
		printf("%s ", basetile_to_string_simple(ten_tile).c_str());
	}

	TEST_EQ_VERBOSE(true, isCommon和牌型(tiles1));
	TEST_EQ_VERBOSE(true, isCommon和牌型(tiles2));
}

void testCompletedTiles1() {
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[0], yama[0], yama[1], yama[2], yama[3], yama[4],
							yama[5], yama[6], yama[7], yama[8], yama[8], yama[8] };

	for (int i = 0; i < 9; ++i) {
		tiles.push_back(yama[i]);
		// SORT_TILES(tiles);
		auto completed_tiles = get_completed_tiles(convert_tiles_to_base_tiles(tiles));
		for_all(completed_tiles, [](CompletedTiles ct) {cout << ct.to_string(); });
		tiles.pop_back();
	}
}

void testCompletedTiles2() {
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<BaseTile> tiles = { _1m, _1m, _1m, _2m, _2m, _2m, _3m, _3m, _3m, _4m, _4m};

	auto completed_tiles = get_completed_tiles(tiles);
	for_all(completed_tiles, [](CompletedTiles ct) {cout << ct.to_string(); });	
}

void resume_from_seed_and_yama(long long seed, string yama) {
	std::default_random_engine generator(seed);
	Table table;
	table.game_init_with_metadata({ {string("yama"), yama} });
	while (table.get_phase() != Table::GAME_OVER) {
		if (table.get_phase() <= Table::P4_ACTION) {
			std::uniform_int_distribution<size_t> distribution(0, table.get_self_actions().size() - 1);
			size_t dice_roll = distribution(generator);  // generates number in the range 1..6 

			for (int i = 0; i < table.get_self_actions().size(); ++i) {
				if (table.get_self_actions()[i].action == BaseAction::自摸) {
					dice_roll = i; break;
				}
				if (table.get_self_actions()[i].action == BaseAction::立直) {
					dice_roll = i; break;
				}
				if (table.get_self_actions()[i].action == BaseAction::九种九牌) {
					dice_roll = i; break;
				}
			}
			table.make_selection((int)dice_roll);
		}
		else {
			size_t dice_roll = 0;
			if (table.get_response_actions().size() > 1) {
				std::uniform_int_distribution<size_t> distribution(0, table.get_response_actions().size() - 1);
				dice_roll = distribution(generator);  // generates number in the range 1..6

				for (int i = 0; i < table.get_response_actions().size(); ++i) {
					if (table.get_response_actions()[i].action == BaseAction::荣和) {
						dice_roll = i;
						break;
					}
				}
			}
			table.make_selection((int)dice_roll);
		}
	}
}

void test_passive_table_auto(size_t max_plays) {
	FunctionProfiler;
	size_t i = 0;
	long long seed;
	string yama;
	auto timenow = std::chrono::system_clock::now();
	for (size_t i = 0; i < max_plays; ++i) {
		try {
			seed = std::chrono::system_clock::now().time_since_epoch().count();
			std::default_random_engine generator(seed);
			Table table;
			table.game_init();
			// table.game_init_with_metadata({ {"oya","0"}, { "wind","east"} });
			// yama = table.export_yama();
			while (table.get_phase() != Table::GAME_OVER) {
				if (table.get_phase() <= Table::P4_ACTION) {
					std::uniform_int_distribution<size_t> distribution(0, table.get_self_actions().size() - 1);
					size_t dice_roll = distribution(generator);
					table.make_selection((int)dice_roll);
				}
				else {
					size_t dice_roll = 0;
					if (table.get_response_actions().size() > 1) {
						std::uniform_int_distribution<size_t> distribution(0, table.get_response_actions().size() - 1);
						dice_roll = distribution(generator);
					}
					table.make_selection((int)dice_roll);

				}
			}
		}
		catch (exception& e) {
			cout << e.what() << endl;
			cout << "Seed" << seed << endl;
			cout << "Yama" << yama << endl;
			getchar();
		}
	}
	auto duration = std::chrono::system_clock::now() - timenow;
	double duration_time  = chrono::duration_cast<chrono::milliseconds>(duration).count() * 1.0 ;
	
	cout << "Test play time: " << max_plays << endl;
	cout << "Duration: " << duration_time / 1000 << " s" << endl;
	cout << "Time per play (avg.): " << duration_time / max_plays << " ms" << endl;
}

void test_encoding(size_t max_plays) {
	FunctionProfiler;
	size_t i = 0;
	long long seed;
	string yama;
	auto timenow = std::chrono::system_clock::now();
	for (size_t i = 0; i < max_plays; ++i) {
		try {
			seed = std::chrono::system_clock::now().time_since_epoch().count();
			std::default_random_engine generator(seed);
			Table table;
			table.game_init();
			while (table.get_phase() != Table::GAME_OVER) {
				if (table.get_phase() <= Table::P4_ACTION) {
					std::uniform_int_distribution<size_t> distribution(0, table.get_self_actions().size() - 1);
					size_t dice_roll = distribution(generator);
					if (table.get_phase() == 0) {
						namespace enc = TrainingDataEncoding;
						using dtype = enc::dtype;
						dtype data[enc::n_row * enc::n_col];
						enc::encode_table(table, 0, data);
					}
					table.make_selection((int)dice_roll);
				}
				else {
					size_t dice_roll = 0;
					if (table.get_response_actions().size() > 1) {
						std::uniform_int_distribution<size_t> distribution(0, table.get_response_actions().size() - 1);
						dice_roll = distribution(generator);
					}
					table.make_selection((int)dice_roll);

				}
			}
		}
		catch (exception& e) {
			cout << e.what() << endl;
			cout << "Seed" << seed << endl;
			cout << "Yama" << yama << endl;
			getchar();
		}
	}
	auto duration = std::chrono::system_clock::now() - timenow;
	double duration_time = chrono::duration_cast<chrono::milliseconds>(duration).count() * 1.0;

	cout << "Test play time: " << max_plays << endl;
	cout << "Duration: " << duration_time / 1000 << " s" << endl;
	cout << "Time per play (avg.): " << duration_time / max_plays << " ms" << endl;
}


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
	table.game_init_for_replay({ 102,119,98,135,114,14,116,28,110,21,83,19,23,121,131,24,11,81,100,71,64,63,58,10,85,20,73,105,96,0,76,51,18,99,50,132,95,13,101,2,134,124,80,133,43,46,8,9,52,87,26,78,97,17,5,61,3,104,42,94,77,7,72,44,66,53,55,59,47,39,25,117,74,33,118,129,122,106,92,69,56,65,112,120,128,41,6,60,62,4,108,45,15,103,111,1,40,125,57,27,109,32,31,88,91,86,79,36,34,68,115,30,126,90,107,37,130,123,84,67,127,82,113,70,29,12,75,93,89,22,38,16,48,49,54,35, }, { 27100,32500,21400,19000, }, 0, 0, 1, 0);
	table.make_selection(12);

	cout << table.get_phase() << endl;
}

int main() {	
	// size_t max_plays = 10000000;
	// test_passive_table_auto(max_plays);
	// profiler::print_profiles();
	test_encoding(100);
	// test_tenhou_yama();
	// test_tenhou_game();
	return 0;
}

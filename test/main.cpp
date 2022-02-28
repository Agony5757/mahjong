#include <fstream>
#include <chrono>
#include <random>
#include <iostream>
#include "Table.h"
#include "Rule.h"
#include "macro.h"
#include "Agent.h"
#include "GamePlay.h"
#include "tenhou.h"

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

void testGameProcess() {
	RealPlayer p0(0), p1(1), p2(2), p3(3);
	Table t(1, &p0, &p1, &p2, &p3);
	auto s = t.GameProcess(true);
	cout << s.to_string();
	getchar();
}

void testGameProcess2() {
	RealPlayer p0(0), p1(1), p2(2), p3(3);
	Table t(1, &p0, &p1, &p2, &p3);
	Result s = t.GameProcess(true, "EwAVAA8AGAAJACEAHQAgABQABwAdABsAFwABABMACAADAAwABAACABIADQACABIAIQAAAAkAEAAfAAUAFgEfACAAAQAEAAsAGwABAAoADwAhAAMAEQALAAcAHAAKAAoAAAATAB4AGAAFAAAABgAXAAQBBgAQAAEABQAaACEAAgAVABUABwAUAA4ADwAQAAwAGQAgAAcABQAMAA0ADwAGABoAAwANAAoAEAAIABQAEgAbAAwAFgAJAAMAFwAWABEABAASABUAGAAaAAYAHAAYAA4AAAAZAB4ACQAeABEACAALAB8AHwACAA4AEwAZAA4ACAAdACAAFwAaAAsAGQAcABYAFAAbAB0ADQEeABEAHAA=");
	
}

void testGameProcess3(string filename, int games = 1000) {	
	ofstream out(filename, ios::out);
	out.close();
	auto t1 = clock();
	int game = 0;	
	for (int i = 0; i < games; ++i) {
		if (i % 1000 == 0) {
			printf("Game %d | Time:%d sec\n", i, (int)((clock() - t1) / CLOCKS_PER_SEC));
		}
		stringstream ss;
		ss << "Game " << ++game << endl;
		RandomPlayer p1(0, ss), p2(0, ss), p3(0, ss), p4(0, ss);
		Table t(1, &p1, &p2, &p3, &p4);
		try {
			auto s = t.GameProcess(false);
			
			if (s.result_type != ResultType::荒牌流局) {
				ss << "Result: " << endl << s.to_string();
				out << ss.str();
			}
		}
		catch (runtime_error &e){
			out << e.what() << endl;
		}		
	}
	printf("Finish %d Games | Time:%d sec\n", games, (int)((clock() - t1) / CLOCKS_PER_SEC));
}

void testGameProcess4(string filename) {
	ofstream out(filename, ios::out);
	out.close();
	auto t1 = clock();
	int game = 0;
	int i = 0;
	for (; ; ++i) {
		if (i % 1000 == 0) {
			printf("Game %d | Time:%d sec\n", i, (int)((clock() - t1) / CLOCKS_PER_SEC));
		}
		stringstream ss;
		ss << "Game " << ++game << endl;
		RandomPlayer p1(0, ss), p2(0, ss), p3(0, ss), p4(0, ss);
		Table t(1, &p1, &p2, &p3, &p4);
		try {
			auto s = t.GameProcess(false);

			if (s.result_type == ResultType::自摸终局) {
				for (auto result : s.results) {
					if (is_in(result.second.yakus, Yaku::天和)) {
						ofstream out(filename, ios::app);
						ss << "Result: " << endl << s.to_string();
						out << ss.str();
						out.close();
						break;
					}
				}				
			}
		}
		catch (runtime_error &e) {
			out << e.what() << endl;
		}
	}
	printf("Finish %d Games | Time:%d sec\n", i, (int)((clock() - t1) / CLOCKS_PER_SEC));	
}

void testGamePlay1(string filename, int shots = 10) {
	ofstream out(filename, ios::out);
	out.close();
	stringstream ss; 
	RandomPlayer p1(0, ss), p2(0, ss), p3(0, ss), p4(0, ss);
	array<Agent*, 4> agents = {&p1, &p2, &p3, &p4};
	for (int i = 0; i < shots; ++i)
	{
		auto scores = 东风局(agents, ss);
		ofstream out(filename, ios::app);
		out << ss.str();
		out.close();
	}	
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

void test_passive_table() {
	Table table;
	table.game_init();
	while (table.get_phase() != Table::GAME_OVER) {
		if (table.get_phase() <= Table::P4_ACTION) {
			table.test_show_all();
			cout << endl; cout << "Select:" << endl;
			int i = 0;

			for (auto action : table.get_self_actions()) {
				cout << i << " " << action.to_string() << endl;
				++i;
			}
			int selection;
			cin >> selection;
			table.make_selection(selection);
		}
		else {
			cout << endl;
			cout << "You are player " << table.who_make_selection() << "." << endl;
			cout << "Player " << table.turn;
			switch (table.get_selected_base_action()) {
			case BaseAction::立直:
				cout << " calls riichi and plays ";
				break;
			case BaseAction::出牌:
				cout << " plays ";
				break;
			case BaseAction::暗杠:
				cout << " 暗杠 ";
				break;
			case BaseAction::加杠:
				cout << " 加杠 ";
				break;
			default:
				throw runtime_error("Unknown action.");
			}
			cout << table.get_selected_action_tile()->to_string() << endl;
			cout << "Select:" << endl;			
			int selection = 0;
			if (table.get_response_actions().size() > 1) {
				int i = 0;
				for (auto action : table.get_response_actions()) {
					cout << i << " " << action.to_string() << endl;
					++i;
				}				
				cin >> selection;
			}
			table.make_selection(selection);
		}
	}
	cout << table.get_result().to_string();
	getchar();
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
table.game_init_for_replay({31,116,43,11,64,41,20,67,60,93,115,30,104,105,47,49,26,89,119,17,50,2,24,106,1,103,25,81,130,75,7,107,87,35,109,133,76,128,62,36,4,83,108,40,78,38,117,86,8,95,57,132,77,6,69,32,19,125,90,22,102,45,63,123,58,13,98,118,61,51,37,134,5,52,23,48,27,54,74,99,129,126,0,53,127,10,66,55,14,68,100,121,110,70,44,56,92,16,101,72,120,3,91,65,88,9,135,42,80,113,85,29,111,73,21,122,46,82,131,39,112,84,59,28,79,97,12,94,34,96,33,71,124,15,114,18,}, {25000,25000,25000,25000,}, 0, 0, 0, 0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(12);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(5);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(5);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(10);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(10);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(9);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(10);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(13);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(12);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(9);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(11);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(12);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(2);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(10);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(13);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(4);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(12);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(11);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(13);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(15);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(6);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(12);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(2);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(0);
table.make_selection(3);
table.make_selection(0);
table.make_selection(1);
table.make_selection(0);

}

int main() {
	
	//test和牌状态1();
	//test和牌状态2();
	//test和牌状态3();
	// test和牌状态4();
	//testGameProcess3("GameLog.txt");
	//testGamePlay1("GamePlay.txt");

	// size_t max_plays = 10000000;
	// test_passive_table_auto(max_plays);
	// profiler::print_profiles();

	// test_tenhou_yama();
	test_tenhou_game();
	// resume_from_seed_and_yama();

	// testCompletedTiles2();
	// testCompletedTiles1();
	return 0;
}

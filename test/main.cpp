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
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<BaseTile> tiles = { _1m, _1m, _1z, _2z, _3z };

	TEST_EQ_VERBOSE(true, isCommon和牌型(tiles));
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

	for (int i = 0; i < 136; ++i) {
		if (i != 0) printf(",");
		printf("%d", yama[i]);
	}
}

int main() {
	
	//test和牌状态1();
	//test和牌状态2();
	//test和牌状态3();
	//test和牌状态4();
	//testGameProcess3("GameLog.txt");
	//testGamePlay1("GamePlay.txt");

	// size_t max_plays = 10000000;
	// test_passive_table_auto(max_plays);
	// profiler::print_profiles();

	test_tenhou_yama();

	// resume_from_seed_and_yama();

	// testCompletedTiles2();
	// testCompletedTiles1();
	return 0;
}

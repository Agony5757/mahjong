#include "Table.h"
#include "Rule.h"
#include "macro.h"
#include "Agent.h"
#include <fstream>
#include <chrono>
#include "GamePlay.h"
#include <random>
#include <iostream>

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
				if (table.get_self_actions()[i].action == Action::自摸) {
					dice_roll = i; break;
				}
				if (table.get_self_actions()[i].action == Action::立直) {
					dice_roll = i; break;
				}
				if (table.get_self_actions()[i].action == Action::九种九牌) {
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
					if (table.get_response_actions()[i].action == Action::荣和) {
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
			switch (table.get_selected_action()) {
			case Action::立直:
				cout << " calls riichi and plays ";
				break;
			case Action::出牌:
				cout << " plays ";
				break;
			case Action::暗杠:
				cout << " 暗杠 ";
				break;
			case Action::加杠:
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

int main() {
	
	//test和牌状态1();
	//test和牌状态2();
	//test和牌状态3();
	//test和牌状态4();
	//testGameProcess3("GameLog.txt");
	//testGamePlay1("GamePlay.txt");
	size_t max_plays = 5000;
	test_passive_table_auto(max_plays);

	// resume_from_seed_and_yama();

	// testCompletedTiles2();
	// testCompletedTiles1();
	return 0;
}

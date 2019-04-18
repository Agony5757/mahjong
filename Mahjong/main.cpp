#include "Table.h"
#include "Rule.h"
#include "macro.h"
#include "Agent.h"
#include <fstream>
using namespace std;

#pragma region(test和牌)

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
		auto completed_tiles = getCompletedTiles(convert_tiles_to_base_tiles(tiles));
		for_all(completed_tiles, [](CompletedTiles ct) {cout << ct.to_string(); });
		tiles.pop_back();
	}
}

void testCompletedTiles2() {
	Table t;
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[0], yama[0], yama[1], yama[1], yama[1], yama[2],
							yama[2], yama[2], yama[6], yama[6]};

	auto completed_tiles = getCompletedTiles(convert_tiles_to_base_tiles(tiles));
	for_all(completed_tiles, [](CompletedTiles ct) {cout << ct.to_string(); });	
}

#pragma endregion

void testGameProcess() {
	Table t(1, new RealPlayer(0), new RealPlayer(1), new RealPlayer(2), new RealPlayer(3));
	auto s = t.GameProcess(true);
	cout << s.to_string();
	getchar();
}

void testGameProcess2() {
	Table t(1, new RealPlayer(0), new RealPlayer(1), new RealPlayer(2), new RealPlayer(3));
	Result s = t.GameProcess(true, "EwAVAA8AGAAJACEAHQAgABQABwAdABsAFwABABMACAADAAwABAACABIADQACABIAIQAAAAkAEAAfAAUAFgEfACAAAQAEAAsAGwABAAoADwAhAAMAEQALAAcAHAAKAAoAAAATAB4AGAAFAAAABgAXAAQBBgAQAAEABQAaACEAAgAVABUABwAUAA4ADwAQAAwAGQAgAAcABQAMAA0ADwAGABoAAwANAAoAEAAIABQAEgAbAAwAFgAJAAMAFwAWABEABAASABUAGAAaAAYAHAAYAA4AAAAZAB4ACQAeABEACAALAB8AHwACAA4AEwAZAA4ACAAdACAAFwAaAAsAGQAcABYAFAAbAB0ADQEeABEAHAA=");
	
}

void testGameProcess3() {	
	int game = 0;	
	for (int i=0;i<1000;++i) {
		stringstream ss;
		ss << "Game " << ++game << endl;
		Table t(1, new RandomPlayer(0, ss),
			new RandomPlayer(1, ss),
			new RandomPlayer(2, ss),
			new RandomPlayer(3, ss));
		auto s = t.GameProcess(false);
		if (s.result_type != ResultType::荒牌流局) {
			ss << "Result: " << endl << s.to_string();
			cout << ss.str();
		}
	}
}


int main() {
	
	//test和牌状态1();
	//test和牌状态2();
	//test和牌状态3();
	testGameProcess3();
	
	//testCompletedTiles2();
	//testCompletedTiles1();
	getchar();
	return 0;
}

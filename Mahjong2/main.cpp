#include "Table.h"
#include "Rule.h"
#include "macro.h"
using namespace std;

#pragma region(test和牌)

void test和牌状态1() {
	Table t(0);
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[1], yama[2], yama[3], yama[3] };

	TEST_EQ_VERBOSE(true, isCommon和牌型(tiles));
}

void test和牌状态2() {
	Table t(0);
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[0], yama[2], yama[3], yama[3] };

	TEST_EQ_VERBOSE(false, isCommon和牌型(tiles));
}

void test和牌状态3() {
	Table t(0);
	t.init_tiles();
	t.init_yama();
	auto &yama = t.牌山;
	vector<Tile*> tiles = { yama[0], yama[0], yama[0], yama[1], yama[2], yama[3], yama[4],
							yama[5], yama[6], yama[7], yama[8], yama[8], yama[8] };

	for (int i = 0; i < 9; ++i) {
		tiles.push_back(yama[i]);
		// SORT_TILES(tiles);
		TEST_EQ_VERBOSE(true, isCommon和牌型(tiles));
		tiles.pop_back();
	}
}

#pragma endregion

void testGameProcess() {
	Table t(1);
	t.GameProcess(true);
}

int main() {
	test和牌状态1();
	test和牌状态2();
	test和牌状态3();
	getchar();
	return 0;
}

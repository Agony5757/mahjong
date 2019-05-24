#pragma once

#include <vector>
#include <tuple>
#include <algorithm>

using namespace std;

#define UNABLE_SHANTIN 1000

struct IntTiles {
	vector<int> tiles1;
	vector<int> tiles2;
	vector<int> tiles3;
	vector<int> tilesZ;

	inline int get_all_number() {
		return tiles1.size() + tiles2.size() + tiles3.size() + tilesZ.size();
	}

	inline void sort_all() {
		sort(tiles1.begin(), tiles1.end());
		sort(tiles2.begin(), tiles2.end());
		sort(tiles3.begin(), tiles3.end());
		sort(tilesZ.begin(), tilesZ.end());
	}

};

int get_shantin(IntTiles tiles);

int get_对子(IntTiles tiles);
int get_对子(vector<int> tiles);
bool is_all_单张(IntTiles &tiles);
bool is_all_单张(vector<int> tiles);
bool is_all_单张Z(vector<int> tiles);
int get_七对_Shantin(IntTiles &tiles);
int get_国士_Shantin(IntTiles &tiles);
int get_幺九种类(vector<int> tiles);
int get_幺九种类Z(vector<int> tiles);
bool 幺九对子(vector<int> tiles);

int get_普通_Shantin(IntTiles &tiles);
int remove_面子(IntTiles& tiles);




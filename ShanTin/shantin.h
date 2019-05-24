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

int get_����(IntTiles tiles);
int get_����(vector<int> tiles);
bool is_all_����(IntTiles &tiles);
bool is_all_����(vector<int> tiles);
bool is_all_����Z(vector<int> tiles);
int get_�߶�_Shantin(IntTiles &tiles);
int get_��ʿ_Shantin(IntTiles &tiles);
int get_�۾�����(vector<int> tiles);
int get_�۾�����Z(vector<int> tiles);
bool �۾Ŷ���(vector<int> tiles);

int get_��ͨ_Shantin(IntTiles &tiles);
int remove_����(IntTiles& tiles);




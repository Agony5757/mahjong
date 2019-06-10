#include "shantin.h"

int get_shantin(IntTiles tiles)
{
	int a1 = get_普通_Shantin(tiles);
	int a2 = get_七对_Shantin(tiles);
	int a3 = get_国士_Shantin(tiles);
	int res = a1;
	if (a1 >= a2)
		res = a2;
	if (res >= a3)
		res = a3;
	return res;
}

int get_对子(IntTiles tiles)
{
	return get_对子(tiles.tiles1) + 
		get_对子(tiles.tiles2) + 
		get_对子(tiles.tiles3) + 
		get_对子(tiles.tilesZ);
}

int get_对子(vector<int> tiles)
{
	int res = 0;
	for (int i = 0; i < tiles.size() - 1; i++) {
		if (tiles[i] == tiles[i + 1])
			res++;
		i++;
	}
	return res;
}

bool is_all_单张(IntTiles & tiles)
{
	return is_all_单张(tiles.tiles1) &&
		is_all_单张(tiles.tiles2) && 
		is_all_单张(tiles.tiles3) && 
		is_all_单张Z(tiles.tilesZ);
}

bool is_all_单张(vector<int> tiles)
{
	for (int i = 0; i < tiles.size() - 1; i++) {
		if (tiles[i + 1] - tiles[i] < 3)
			return false;
	}
	return true;
}

bool is_all_单张Z(vector<int> tiles)
{
	for (int i = 0; i < tiles.size() - 1; i++) {
		if (tiles[i + 1] - tiles[i] == 0)
			return false;
	}
	return true;
}

int get_七对_Shantin(IntTiles & tiles)
{
	if (tiles.get_all_number() != 13)
		return UNABLE_SHANTIN;
	int toitsu = get_对子(tiles);
	return 6 - toitsu;
}

int get_国士_Shantin(IntTiles & tiles)
{
	if (tiles.get_all_number() != 13)
		return UNABLE_SHANTIN;
	int res = 13 - get_幺九种类(tiles.tiles1) - get_幺九种类(tiles.tiles2) - get_幺九种类(tiles.tiles3)
		- get_幺九种类Z(tiles.tilesZ);

	if (get_对子(tiles.tilesZ) > 0) return res - 1;
	if (幺九对子(tiles.tiles1)) return res - 1;
	if (幺九对子(tiles.tiles2)) return res - 1;
	if (幺九对子(tiles.tiles3)) return res - 1;
	return res;
}

int get_幺九种类(vector<int> tiles)
{
	int res = 0;
	if (tiles[0] == 1) res++;
	if (tiles.back() == 9) res++;
	return res;
}

int get_幺九种类Z(vector<int> tiles)
{
	return tiles.size() - get_对子(tiles);
}

bool 幺九对子(vector<int> tiles)
{
	if (tiles.size() == 1) return false;
	if (tiles[0] == tiles[1] && tiles[0] == 1) return true;
	if (tiles[tiles.size() - 1] == tiles[tiles.size() - 2] && tiles.back() == 9) return true;
	return false;
}

int get_普通_Shantin(IntTiles & tiles)
{
	return 0;
}

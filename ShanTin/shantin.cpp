#include "shantin.h"

int get_shantin(IntTiles tiles)
{
	int a1 = get_��ͨ_Shantin(tiles);
	int a2 = get_�߶�_Shantin(tiles);
	int a3 = get_��ʿ_Shantin(tiles);
	int res = a1;
	if (a1 >= a2)
		res = a2;
	if (res >= a3)
		res = a3;
	return res;
}

int get_����(IntTiles tiles)
{
	return get_����(tiles.tiles1) + 
		get_����(tiles.tiles2) + 
		get_����(tiles.tiles3) + 
		get_����(tiles.tilesZ);
}

int get_����(vector<int> tiles)
{
	int res = 0;
	for (int i = 0; i < tiles.size() - 1; i++) {
		if (tiles[i] == tiles[i + 1])
			res++;
		i++;
	}
	return res;
}

bool is_all_����(IntTiles & tiles)
{
	return is_all_����(tiles.tiles1) &&
		is_all_����(tiles.tiles2) && 
		is_all_����(tiles.tiles3) && 
		is_all_����Z(tiles.tilesZ);
}

bool is_all_����(vector<int> tiles)
{
	for (int i = 0; i < tiles.size() - 1; i++) {
		if (tiles[i + 1] - tiles[i] < 3)
			return false;
	}
	return true;
}

bool is_all_����Z(vector<int> tiles)
{
	for (int i = 0; i < tiles.size() - 1; i++) {
		if (tiles[i + 1] - tiles[i] == 0)
			return false;
	}
	return true;
}

int get_�߶�_Shantin(IntTiles & tiles)
{
	if (tiles.get_all_number() != 13)
		return UNABLE_SHANTIN;
	int toitsu = get_����(tiles);
	return 6 - toitsu;
}

int get_��ʿ_Shantin(IntTiles & tiles)
{
	if (tiles.get_all_number() != 13)
		return UNABLE_SHANTIN;
	int res = 13 - get_�۾�����(tiles.tiles1) - get_�۾�����(tiles.tiles2) - get_�۾�����(tiles.tiles3)
		- get_�۾�����Z(tiles.tilesZ);

	if (get_����(tiles.tilesZ) > 0) return res - 1;
	if (�۾Ŷ���(tiles.tiles1)) return res - 1;
	if (�۾Ŷ���(tiles.tiles2)) return res - 1;
	if (�۾Ŷ���(tiles.tiles3)) return res - 1;
	return res;
}

int get_�۾�����(vector<int> tiles)
{
	int res = 0;
	if (tiles[0] == 1) res++;
	if (tiles.back() == 9) res++;
	return res;
}

int get_�۾�����Z(vector<int> tiles)
{
	return tiles.size() - get_����(tiles);
}

bool �۾Ŷ���(vector<int> tiles)
{
	if (tiles.size() == 1) return false;
	if (tiles[0] == tiles[1] && tiles[0] == 1) return true;
	if (tiles[tiles.size() - 1] == tiles[tiles.size() - 2] && tiles.back() == 9) return true;
	return false;
}

int get_��ͨ_Shantin(IntTiles & tiles)
{
	return 0;
}

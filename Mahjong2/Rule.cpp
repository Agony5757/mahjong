#include "Rule.h"
#include "macro.h"

using namespace std;
static std::vector<Tile*> find˳��(std::vector<Tile*> tiles, int n);
static std::vector<Tile*> find����(std::vector<Tile*> tiles, int n);

bool is����(std::vector<Tile*> hand)
{
	return false;
}

bool is����(std::vector<Tile*> hand)
{
	return false;
}

bool is�߶�(std::vector<Tile*> hand, Tile *)
{
	return false;
}

bool is��ʿ��˫(std::vector<Tile*> hand, Tile *)
{
	return false;
}

bool isCommon������(std::vector<Tile*> tiles) {

	if (tiles.size() % 3 != 2) return false;

	auto instance = mahjong::Yaku::GetInstance();

	auto extern_tiles = convert_tiles_to_extern_tiles(tiles);

	auto agari_tile = extern_tiles.back();

	extern_tiles.pop_back();

	auto s = instance->getAllCompletedTiles(extern_tiles, agari_tile, false);
	
	if (s.size() != 0)
		return true;
	else
		return false;
}

bool can����(std::vector<Tile*> hand, std::unordered_map<Tile*, std::vector<Tile*>> fulus, std::vector<Tile*> river, Tile * newtile, bool isHaidi)
{
	return false;
}

std::vector<Tile*> find˳��(std::vector<Tile*> tiles, int n)
{
	return {};
}

std::vector<Tile*> find����(std::vector<Tile*> tiles, int n)
{
	return {};
}

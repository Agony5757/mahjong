#include "Rule.h"
#include "macro.h"

using namespace std;
static std::vector<Tile*> find顺子(std::vector<Tile*> tiles, int n);
static std::vector<Tile*> find刻子(std::vector<Tile*> tiles, int n);

bool is听牌(std::vector<Tile*> hand)
{
	return false;
}

bool is振听(std::vector<Tile*> hand)
{
	return false;
}

bool is七对(std::vector<Tile*> hand, Tile *)
{
	return false;
}

bool is国士无双(std::vector<Tile*> hand, Tile *)
{
	return false;
}

bool isCommon和牌型(std::vector<Tile*> tiles) {

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

bool can和牌(std::vector<Tile*> hand, std::unordered_map<Tile*, std::vector<Tile*>> fulus, std::vector<Tile*> river, Tile * newtile, bool isHaidi)
{
	return false;
}

std::vector<Tile*> find顺子(std::vector<Tile*> tiles, int n)
{
	return {};
}

std::vector<Tile*> find刻子(std::vector<Tile*> tiles, int n)
{
	return {};
}

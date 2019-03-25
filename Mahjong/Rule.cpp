#include "Rule.h"
#include "macro.h"

using namespace std;

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
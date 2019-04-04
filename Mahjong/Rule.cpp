#include "Rule.h"
#include "macro.h"

using namespace std;

std::vector<CompletedTiles> getCompletedTiles(std::vector<BaseTile> tiles)
{
	if (tiles.size() % 3 != 2) throw runtime_error("Not Enough Tiles");	
	auto instance = mahjong::Yaku::GetInstance();
	auto extern_tiles = convert_basetiles_to_extern_tiles(tiles);
	auto agari_tile = extern_tiles.back();
	extern_tiles.pop_back();
	auto s = instance->getAllCompletedTiles(extern_tiles, agari_tile, true);
	return convert_extern_completed_tiles_to_internal(s);
}

TileGroup convert_extern_tilegroup_to_internal(mahjong::TileGroup tilegroup)
{
	TileGroup tg;
	tg.tiles = convert_extern_tiles_to_basetiles(tilegroup.getTilesList());
	switch (tilegroup.getTileGroupType()) {
	case mahjong::TileGroupType::Toitsu:
		tg.type = TileGroup::Type::Toitsu;
		return tg;
	case mahjong::TileGroupType::Shuntsu:
		tg.type = TileGroup::Type::Shuntsu;
		return tg;
	case mahjong::TileGroupType::Ankou:
		tg.type = TileGroup::Type::Koutsu;
		return tg;
	default:
		throw runtime_error("Unhandled TileGroupType");		
	}
}

CompletedTiles convert_extern_completed_tiles_to_internal(mahjong::CompletedTiles completed_tiles)
{
	CompletedTiles ct;
	ct.head = convert_extern_tilegroup_to_internal(completed_tiles.head);
	for (auto body : completed_tiles.body) {
		ct.body.push_back(convert_extern_tilegroup_to_internal(body));
	}
	return ct;
}

std::vector<CompletedTiles> convert_extern_completed_tiles_to_internal(
	std::vector<mahjong::CompletedTiles> completed_tiles)
{
	std::vector<CompletedTiles> internal_completed_tiles;
	for_each(completed_tiles.begin(), completed_tiles.end(),
		[&internal_completed_tiles](mahjong::CompletedTiles& ct) 
		{internal_completed_tiles.push_back(
		convert_extern_completed_tiles_to_internal(ct)); }
	);
	return internal_completed_tiles;
}

bool isCommon和牌型(std::vector<BaseTile> basetiles) {

	if (basetiles.size() % 3 != 2) return false;
	
	// auto basetiles = convert_tiles_to_base_tiles(tiles);
	auto s = getCompletedTiles(basetiles);	
	if (s.size() != 0)
		return true;
	else
		return false;
}

std::vector<BaseTile> isCommon听牌型(std::vector<BaseTile> tiles)
{
	vector<BaseTile> 听牌;
	for (int i = BaseTile::_1m; i <= BaseTile::中; ++i) {
		tiles.push_back(static_cast<BaseTile>(i));
		if (isCommon和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
		}
		tiles.pop_back();
	}
	return 听牌;
}

bool is七对和牌型(std::vector<BaseTile> tiles)
{
	if (tiles.size() != 14) return false;
	sort(tiles.begin(), tiles.end());
	if (tiles[0] == tiles[1]
		&&
		tiles[1] != tiles[2]
		&&
		tiles[2] == tiles[3]
		&&
		tiles[3] != tiles[4]
		&&
		tiles[4] == tiles[5]
		&&
		tiles[5] != tiles[6]
		&&
		tiles[6] == tiles[7]
		&&
		tiles[7] != tiles[8]
		&&
		tiles[8] == tiles[9]
		&&
		tiles[9] != tiles[10]
		&&
		tiles[10] == tiles[11]
		&&
		tiles[11] != tiles[12]
		&&
		tiles[12] == tiles[13])
		return true;
	else return false;
}

std::vector<BaseTile> is七对听牌型(std::vector<BaseTile> tiles)
{
	vector<BaseTile> 听牌;
	for (int i = BaseTile::_1m; i <= BaseTile::中; ++i) {
		tiles.push_back(static_cast<BaseTile>(i));
		if (is七对和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
		}
		tiles.pop_back();
	}
	return 听牌;
}


bool is国士无双和牌型(std::vector<BaseTile> tiles)
{
	if (tiles.size() != 14) return false;
	sort(tiles.begin(), tiles.end());

	vector<BaseTile> raw
	{ _1m, _9m, _1s, _9s, _1p, _9p, east, south, west, north, 白, 发, 中 };

	vector<BaseTile> adds
	{ _1m, _9m, _1s, _9s, _1p, _9p, east, south, west, north, 白, 发, 中 };

	for (auto add : adds) {
		raw.push_back(add);
		sort(tiles.begin(), tiles.end());
		if (is_same_capacitor(tiles, raw))
			return true;
		else
			raw.pop_back();
	}
	return false;
}

std::vector<BaseTile> is国士无双听牌型(std::vector<BaseTile> tiles)
{
	vector<BaseTile> 听牌;
	for (int i = BaseTile::_1m; i <= BaseTile::中; ++i) {
		tiles.push_back(static_cast<BaseTile>(i));
		if (is国士无双和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
		}
		tiles.pop_back();
	}
	return 听牌;
}

std::vector<BaseTile> is听牌(std::vector<BaseTile> tiles)
{
	vector<BaseTile> 听牌;
	for (int i = BaseTile::_1m; i <= BaseTile::中; ++i) {
		tiles.push_back(static_cast<BaseTile>(i));
		if (is国士无双和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
			continue;
		}
		if (is七对和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
			continue;
		}
		if (isCommon和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
			continue;
		}
		tiles.pop_back();
	}
	return 听牌;
}





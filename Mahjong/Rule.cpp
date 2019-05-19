#include "Rule.h"
#include "macro.h"
#include "Table.h"
using namespace std;

std::vector<CompletedTiles> getCompletedTiles(std::vector<BaseTile> tiles)
{
	if (tiles.size() % 3 != 2) throw STD_RUNTIME_ERROR_WITH_FILE_LINE_FUNCTION("Not Enough Tiles");	
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
		throw STD_RUNTIME_ERROR_WITH_FILE_LINE_FUNCTION("Unhandled TileGroupType");		
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
		if (is_same_container(tiles, raw))
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



std::vector<BaseTile> get听牌(std::vector<BaseTile> tiles)
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

bool is和牌(std::vector<BaseTile> tiles)
{
	if (is国士无双和牌型(tiles)) {
		return true;
	}
	if (is七对和牌型(tiles)) {
		return true;
	}
	if (isCommon和牌型(tiles)) {
		return true;
	}
	return false;
}

std::vector<Tile*> is_riichi_able(std::vector<Tile*> hands, bool 门清)
{
	std::vector<Tile*> play_tiles;
	if (!门清) return play_tiles;
	if (hands.size() % 3 != 2) return play_tiles;

	for (int i = 0; i < hands.size(); ++i) {
		std::vector<Tile*> copy_hand(hands.begin(), hands.end());
		copy_hand.erase(copy_hand.begin() + i);
		auto s = convert_tiles_to_base_tiles(copy_hand);
		auto tenhai = get听牌(s);
		if (tenhai.size() != 0) {
			play_tiles.push_back(hands[i]);
		}
	}
	return play_tiles;
}

bool can_ron(std::vector<Tile*> hands, Tile * get_tile)
{
	hands.push_back(get_tile);
	if (is和牌(convert_tiles_to_base_tiles(hands)))
		return true;
	return false;
}

bool can_tsumo(std::vector<Tile*> hands)
{
	if (is和牌(convert_tiles_to_base_tiles(hands)))
		return true;
	return false;
}

bool is纯九莲和牌型(std::vector<BaseTile> tiles)
{
	if (tiles.size() != 14) return false;
	vector<int> 纯九莲和牌型raw = { 1,1,1,2,3,4,5,6,7,8,9,9,9 };
	vector<int> 纯九莲和牌型[9];
	for (int i = 1; i <= 9; ++i) {
		纯九莲和牌型[i - 1].assign(纯九莲和牌型raw.begin(), 纯九莲和牌型raw.end());
		纯九莲和牌型[i - 1].push_back(i);
	}

	for (auto 纯九莲 : 纯九莲和牌型)
	{
		vector<BaseTile> 纯九莲m;
		for (int i = 0; i < 14; ++i) {
			纯九莲m.push_back(BaseTile(纯九莲[i] + int(_1m) - 1));
		}
		vector<BaseTile> 纯九莲s;
		for (int i = 0; i < 14; ++i) {
			纯九莲m.push_back(BaseTile(纯九莲[i] + int(_1s) - 1));
		}
		vector<BaseTile> 纯九莲p;
		for (int i = 0; i < 14; ++i) {
			纯九莲m.push_back(BaseTile(纯九莲[i] + int(_1p) - 1));
		}
		if (is_same_container(tiles, 纯九莲m)) return true;
		if (is_same_container(tiles, 纯九莲p)) return true;
		if (is_same_container(tiles, 纯九莲s)) return true;
	}

	return false;
}

bool is九莲和牌型(std::vector<BaseTile> tiles)
{
	sort(tiles.begin(), tiles.end());
	if (tiles.size() != 14) return false;
	vector<int> 九莲和牌型raw = { 1,1,1,2,3,4,5,6,7,8,9,9,9 };
	vector<int> 九莲和牌型[9];
	for (int i = 1; i <= 9; ++i) {
		九莲和牌型[i - 1].assign(九莲和牌型raw.begin(), 九莲和牌型raw.end());
		九莲和牌型[i - 1].push_back(i);		
	}
	for (auto 九莲 : 九莲和牌型) {
		vector<BaseTile> 九莲m;
		for (int i = 0; i < 14; ++i) {
			九莲m.push_back(BaseTile(九莲[i] + int(_1m) - 1));
		}
		sort(九莲m.begin(), 九莲m.end());

		vector<BaseTile> 九莲s;
		for (int i = 0; i < 14; ++i) {
			九莲m.push_back(BaseTile(九莲[i] + int(_1s) - 1));
		}
		sort(九莲s.begin(), 九莲s.end());

		vector<BaseTile> 九莲p;
		for (int i = 0; i < 14; ++i) {
			九莲m.push_back(BaseTile(九莲[i] + int(_1p) - 1));
		}
		sort(九莲p.begin(), 九莲p.end());

		if (is_same_container(tiles, 九莲m)) return true;
		if (is_same_container(tiles, 九莲p)) return true;
		if (is_same_container(tiles, 九莲s)) return true;
	}
	return false;
}


//
//std::vector<Yaku> get_立直_双立直(bool double_riichi, bool riichi, bool 一发)
//{
//	vector<Yaku> yaku;
//	if (double_riichi) {
//		yaku.push_back(Yaku::两立直); 
//	}
//	else if (riichi) {
//		yaku.push_back(Yaku::立直);
//	}
//	if (一发) {
//		yaku.push_back(Yaku::一发);
//	}
//	return yaku;
//}
//
//vector<Yaku> get_平和(CompletedTiles complete_tiles, bool 门清, BaseTile get_tile, 
//	Wind 场风, Wind 自风)
//{
//	vector<Yaku> yaku;
//	// cout << "Warning: 平和 is not considered." << endl;
//	complete_tiles.sort_body();
//	if (complete_tiles.body[0].type != TileGroup::Toitsu) {
//		throw runtime_error("First group is not Toitsu.");
//	}
//	if (!门清) return yaku;
//	
//	if (!all_of(complete_tiles.body.begin() + 1, complete_tiles.body.end(),
//		[](TileGroup &s) {return (s.type == TileGroup::Shuntsu); })
//	) {
//		return yaku;
//	}
//
//	if (!any_of(complete_tiles.body.begin()+1, complete_tiles.body.end(),
//		[get_tile](TileGroup &s) { 
//		// get_tile存在于s.tiles中
//		// 并且s.tiles除去这张牌，是23，34，。。。78中的一个
//		// 因为是顺子，所以肯定不是字牌
//		// 因此和这两张牌都不是老头牌，以及这两张牌差为1等价
//		auto iter = find(s.tiles.begin(), s.tiles.end(), get_tile);
//		if (iter == s.tiles.end()) { return false; }
//		else {
//			s.tiles.erase(iter);
//			sort(s.tiles.begin(), s.tiles.end());
//			if (is_老头牌(s.tiles[0]) || is_老头牌(s.tiles[1])
//				||
//				abs(s.tiles[0] - s.tiles[1]) != 1
//				) {
//				return false;
//			}
//			else return true;
//		}
//	}))
//		return yaku;
//
//	if (is_役牌(get_tile, 场风, 自风))
//		return yaku;
//
//	yaku.push_back(Yaku::平和);
//
//	return yaku;
//}
//
//std::vector<Yaku> get_门前自摸(bool 门清, bool 自摸)
//{
//	vector<Yaku> yaku;
//	if (门清 && 自摸) {
//		yaku.push_back(Yaku::门前清自摸和);
//	}
//	return yaku;
//}
//
//std::vector<Yaku> get_四暗刻_三暗刻(CompletedTiles complete_tiles)
//{
//	vector<Yaku> yaku;
//	cout << "Warning: 四暗刻 is not considered." << endl;
//	return yaku;
//}
//
//std::vector<Yaku> get_yaku_tsumo(Table* table, Player * player)
//{
//	auto 门清 = player->门清;
//	auto riichi = player->riichi;
//	auto double_riichi = player->double_riichi;
//	bool 自摸 = true;
//	bool 一发 = player->一发;
//
//	vector<Yaku> yakus;
//	merge_into(yakus, get_门前自摸(门清, 自摸));
//	merge_into(yakus, get_立直_双立直(double_riichi, riichi, 一发));
//
//	return yakus;
//}
//
//std::vector<Yaku> get_yaku_ron(Table* table, Player * player, Tile* get_tile)
//{
//	auto 门清 = player->门清;
//	auto riichi = player->riichi;
//	auto double_riichi = player->double_riichi;
//	bool 自摸 = true;
//	bool 一发 = player->一发;
//
//	vector<Yaku> yakus;
//	merge_into(yakus, get_立直_双立直(double_riichi, riichi, 一发));
//
//	return yakus;
//}
//

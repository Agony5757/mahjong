#include "Rule.h"
#include "macro.h"
#include "Table.h"
using namespace std;

基本和牌型& 基本和牌型::GetInstance()
{
	static 基本和牌型 inst;
	return inst;
}

void 基本和牌型::reset()
{
	// m_completedTiles.head.reset();
	/*for (auto it : m_completedTiles.body)
		it.reset();*/
	completed_tiles.body.clear();
	has_head = false;
}

vector<CompletedTiles> 基本和牌型::getAllCompletedTiles(const vector<BaseTile>& curTiles)
{
	if (curTiles.size() == 0) {
		return { completed_tiles };
	}
	vector<CompletedTiles> ret, all_completed_tiles;
	vector<BaseTile> tmpTiles;
	int index = 0;

	for (int index = 0; index < curTiles.size(); ++index)
	{
		if (index > 0 && curTiles[index] == curTiles[index - 1])
		{ // Skip same tiles
			index++;
			continue;
		}

		BaseTile this_tile = curTiles[index];
		// 1. Find Toitsu (Head)
		if (!has_head)
		{
			if (count(curTiles.begin(), curTiles.end(), this_tile) >= 2)
			{
				tmpTiles = curTiles; // 复制一份当前手牌
				TileGroup tmp_group;

				// 设置全局状态的head已经并移除对子
				tmp_group.type = TileGroup::Type::Toitsu;
				tmp_group.set_tiles({ this_tile, this_tile });
				erase_n(tmpTiles, this_tile, 2);
				has_head = true;
				completed_tiles.head = tmp_group;

				// 根据当前状态递归
				all_completed_tiles = getAllCompletedTiles(tmpTiles);
				ret.insert(ret.end(), all_completed_tiles.begin(), all_completed_tiles.end());

				// 恢复系统状态
				has_head = false;
			}
		}

		// 2. Find Koutsu
		if (count(curTiles.begin(), curTiles.end(), this_tile) >= 3)
		{
			tmpTiles = curTiles; // 复制一份当前手牌
			TileGroup tmp_group;

			// 设置全局状态的head已经并移除刻子
			tmp_group.type = TileGroup::Type::Toitsu;
			tmp_group.set_tiles({ this_tile , this_tile , this_tile });
			erase_n(tmpTiles, this_tile, 3);
			// 设置临时状态
			completed_tiles.body.push_back(tmp_group);
			// 根据当前状态递归
			all_completed_tiles = getAllCompletedTiles(tmpTiles);
			ret.insert(ret.end(), all_completed_tiles.begin(), all_completed_tiles.end());
			// 恢复状态
			completed_tiles.body.pop_back();
		}

		// 3. Find Shuntsu
		if (!is_in({_8m, _9m, _8p, _9p, _8s, _9s, _1z, _2z, _3z, _4z, _5z, _6z, _7z }, this_tile)			
			&& is_in(curTiles, BaseTile(curTiles[index] + 1))
			&& is_in(curTiles, BaseTile(curTiles[index] + 2)))

		{
			tmpTiles = curTiles; // 复制一份当前手牌
			TileGroup tmp_group;
			tmp_group.type = TileGroup::Type::Shuntsu;
			tmp_group.set_tiles({ curTiles[index], BaseTile(curTiles[index] + 1), BaseTile(curTiles[index] + 2) });
			erase_n(tmpTiles, curTiles[index], 1);
			erase_n(tmpTiles, BaseTile(curTiles[index] + 1), 1);
			erase_n(tmpTiles, BaseTile(curTiles[index] + 2), 1);

			// 设置临时状态
			completed_tiles.body.push_back(tmp_group);
			// 根据当前状态递归
			all_completed_tiles = getAllCompletedTiles(tmpTiles);
			ret.insert(ret.end(), all_completed_tiles.begin(), all_completed_tiles.end());
			// 恢复状态
			completed_tiles.body.pop_back();
		}
	}

	return ret;
}


bool 基本和牌型::hasOneCompletedTiles(const vector<BaseTile>& curTiles)
{
	if (curTiles.size() == 0) {
		return true;
	}
	vector<BaseTile> tmpTiles;
	int index = 0;

	for (int index = 0; index < curTiles.size(); ++index)
	{
		if (index > 0 && curTiles[index] == curTiles[index - 1])
		{ // Skip same tiles
			index++;
			continue;
		}

		BaseTile this_tile = curTiles[index];
		// 1. Find Toitsu (Head)
		if (!has_head)
		{
			if (count(curTiles.begin(), curTiles.end(), this_tile) >= 2)
			{
				tmpTiles = curTiles; // 复制一份当前手牌
				TileGroup tmp_group;

				// 设置全局状态的head已经并移除对子
				tmp_group.type = TileGroup::Type::Toitsu;
				tmp_group.set_tiles({ this_tile, this_tile });
				erase_n(tmpTiles, this_tile, 2);
				has_head = true;
				completed_tiles.head = tmp_group;

				// 根据当前状态递归
				bool ret = hasOneCompletedTiles(tmpTiles);
				if (ret) { return true; }

				// 恢复系统状态
				has_head = false;
			}
		}

		// 2. Find Koutsu
		if (count(curTiles.begin(), curTiles.end(), this_tile) >= 3)
		{
			tmpTiles = curTiles; // 复制一份当前手牌
			TileGroup tmp_group;

			// 设置全局状态的head已经并移除刻子
			tmp_group.type = TileGroup::Type::Toitsu;
			tmp_group.set_tiles({ this_tile , this_tile , this_tile });
			erase_n(tmpTiles, this_tile, 3);
			// 设置临时状态
			completed_tiles.body.push_back(tmp_group);
			// 根据当前状态递归
			bool ret = hasOneCompletedTiles(tmpTiles);
			if (ret) { return true; }
			// 恢复状态
			completed_tiles.body.pop_back();
		}

		// 3. Find Shuntsu
		if (!is_in({ _8m, _9m, _8p, _9p, _8s, _9s, _1z, _2z, _3z, _4z, _5z, _6z, _7z }, this_tile)
			&& is_in(curTiles, BaseTile(curTiles[index] + 1))
			&& is_in(curTiles, BaseTile(curTiles[index] + 2)))

		{
			tmpTiles = curTiles; // 复制一份当前手牌
			TileGroup tmp_group;
			tmp_group.type = TileGroup::Type::Shuntsu;
			tmp_group.set_tiles({ curTiles[index], BaseTile(curTiles[index] + 1), BaseTile(curTiles[index] + 2) });
			erase_n(tmpTiles, curTiles[index], 1);
			erase_n(tmpTiles, BaseTile(curTiles[index] + 1), 1);
			erase_n(tmpTiles, BaseTile(curTiles[index] + 2), 1);

			// 设置临时状态
			completed_tiles.body.push_back(tmp_group);
			// 根据当前状态递归
			bool ret = hasOneCompletedTiles(tmpTiles);
			if (ret) { return true; }
			// 恢复状态
			completed_tiles.body.pop_back();
		}
	}

	return false;
}

std::vector<CompletedTiles> get_completed_tiles(std::vector<BaseTile> tiles)
{
	if (tiles.size() % 3 != 2) throw runtime_error("Not Enough Tiles");	
	auto& inst = 基本和牌型::GetInstance();
	inst.reset();
	auto completed_tiles = inst.getAllCompletedTiles(tiles);
	for (auto& completed : completed_tiles) {
		completed.sort_body();
	}
	sort(completed_tiles.begin(), completed_tiles.end());
	completed_tiles.erase(unique(completed_tiles.begin(), completed_tiles.end()), completed_tiles.end());
	return completed_tiles;
}

bool has_completed_tiles(std::vector<BaseTile> tiles)
{
	if (tiles.size() % 3 != 2) throw runtime_error("Not Enough Tiles");
	auto& inst = 基本和牌型::GetInstance();
	inst.reset();
	return inst.hasOneCompletedTiles(tiles);
}
//
//TileGroup convert_extern_tilegroup_to_internal(mahjong_algorithm::TileGroup tilegroup)
//{
//	TileGroup tg;
//	tg.tiles = convert_extern_tiles_to_basetiles(tilegroup.getTilesList());
//	switch (tilegroup.getTileGroupType()) {
//	case mahjong_algorithm::TileGroupType::Toitsu:
//		tg.type = TileGroup::Type::Toitsu;
//		return tg;
//	case mahjong_algorithm::TileGroupType::Shuntsu:
//		tg.type = TileGroup::Type::Shuntsu;
//		return tg;
//	case mahjong_algorithm::TileGroupType::Ankou:
//		tg.type = TileGroup::Type::Koutsu;
//		return tg;
//	default:
//		throw runtime_error("Unhandled TileGroupType");		
//	}
//}
//
//CompletedTiles convert_extern_completed_tiles_to_internal(mahjong_algorithm::CompletedTiles completed_tiles)
//{
//	CompletedTiles ct;
//	ct.head = convert_extern_tilegroup_to_internal(completed_tiles.head);
//	for (auto body : completed_tiles.body) {
//		ct.body.push_back(convert_extern_tilegroup_to_internal(body));
//	}
//	return ct;
//}
//
//std::vector<CompletedTiles> convert_extern_completed_tiles_to_internal(
//	std::vector<mahjong_algorithm::CompletedTiles> completed_tiles)
//{
//	std::vector<CompletedTiles> internal_completed_tiles;
//	for_each(completed_tiles.begin(), completed_tiles.end(),
//		[&internal_completed_tiles](mahjong_algorithm::CompletedTiles& ct) 
//		{internal_completed_tiles.push_back(
//		convert_extern_completed_tiles_to_internal(ct)); }
//	);
//	return internal_completed_tiles;
//}

bool isCommon和牌型(std::vector<BaseTile> basetiles) {

	FunctionProfiler;
	if (basetiles.size() % 3 != 2) return false;
	
	// auto basetiles = convert_tiles_to_base_tiles(tiles);
	return has_completed_tiles(basetiles);
}

std::vector<BaseTile> isCommon听牌型(std::vector<BaseTile> tiles)
{
	vector<BaseTile> 听牌;
	for (int i = BaseTile::_1m; i <= BaseTile::_7z; ++i) {
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
	FunctionProfiler;
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
	for (int i = BaseTile::_1m; i <= BaseTile::_7z; ++i) {
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
	FunctionProfiler;
	vector<BaseTile> raw
	{ _1m, _9m, _1s, _9s, _1p, _9p, _1z, _2z, _3z, _4z, _5z, _6z, _7z };

	vector<BaseTile> adds
	{ _1m, _9m, _1s, _9s, _1p, _9p, _1z, _2z, _3z, _4z, _5z, _6z, _7z };

	if (tiles.size() != 14) return false;

	// 任何一张牌不是幺九牌，直接返回（大概率减少运行时间）
	if (any_of(tiles.begin(), tiles.end(),
		[](BaseTile bt) { return !is_幺九牌(bt); })) {
		return false;
	}
	sort(tiles.begin(), tiles.end());

	for (auto add : adds) {
        auto new_raw = raw;
		new_raw.push_back(add);
		sort(new_raw.begin(), new_raw.end());
		if (is_same_container(tiles, new_raw))
			return true;
	}
	return false;
}

std::vector<BaseTile> is国士无双听牌型(std::vector<BaseTile> tiles)
{
	// 任何一张牌不是幺九牌，直接返回（大概率减少运行时间）
	if (any_of(tiles.begin(), tiles.end(),
		[](BaseTile bt) { return !is_幺九牌(bt); })) {
		return {};
	}
	vector<BaseTile> 听牌;
	vector<BaseTile> adds{ _1m, _9m, _1s, _9s, _1p, _9p, _1z, _2z, _3z, _4z, _5z, _6z, _7z };
	for (auto i : adds) {
		tiles.push_back(i);
		if (is国士无双和牌型(tiles)) {
			听牌.push_back(static_cast<BaseTile>(i));
		}
		tiles.pop_back();
	}
	return 听牌;
}

vector<BaseTile> get听牌(vector<BaseTile> tiles, vector<BaseTile> except_tiles)
{
	FunctionProfiler;
	vector<BaseTile> 听牌;
	for (int i = BaseTile::_1m; i <= BaseTile::_7z; ++i) {
		if (except_tiles.size() > 0) {
			if (is_in(except_tiles, static_cast<BaseTile>(i))) {
				continue;
			}
		}
		tiles.push_back(static_cast<BaseTile>(i));
		if (is_幺九牌(static_cast<BaseTile>(i)) && is国士无双和牌型(tiles)) {
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

bool is听牌(vector<BaseTile> tiles, vector<BaseTile> except_tiles)
{
	FunctionProfiler;
	for (int i = BaseTile::_1m; i <= BaseTile::_7z; ++i) {
		if (except_tiles.size() > 0) {
			if (is_in(except_tiles, static_cast<BaseTile>(i))) {
				continue;
			}
		}
		tiles.push_back(static_cast<BaseTile>(i));
		if (is_幺九牌(static_cast<BaseTile>(i)) && is国士无双和牌型(tiles)) {
			return true;
		}
		if (is七对和牌型(tiles)) {
			return true;
		}
		if (isCommon和牌型(tiles)) {
			return true;
		}
		tiles.pop_back();
	}
	return false;
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

bool can_ron(std::vector<Tile*> hands, Tile *get_tile)
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
		vector<BaseTile> 纯九莲p;
		for (int i = 0; i < 14; ++i) {
			纯九莲p.push_back(BaseTile(纯九莲[i] + int(_1p) - 1));
		}
		vector<BaseTile> 纯九莲s;
		for (int i = 0; i < 14; ++i) {
			纯九莲s.push_back(BaseTile(纯九莲[i] + int(_1s) - 1));
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
			九莲s.push_back(BaseTile(九莲[i] + int(_1s) - 1));
		}
		sort(九莲s.begin(), 九莲s.end());

		vector<BaseTile> 九莲p;
		for (int i = 0; i < 14; ++i) {
			九莲p.push_back(BaseTile(九莲[i] + int(_1p) - 1));
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

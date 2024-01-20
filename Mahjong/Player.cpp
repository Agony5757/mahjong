#include "Player.h"
#include "Table.h"

using namespace std;
namespace_mahjong

Player::Player() 
{ }

Player::Player(int init_score)
{
	score = init_score;
}

string Player::hand_to_string() const
{
	stringstream ss;

	for (auto hand_tile : hand) {
		ss << hand_tile->to_string() << " ";
	}
	return ss.str();
}

string Player::river_to_string() const
{
	return river.to_string();
}

string Player::to_string() const
{
	std::string str_fuuro;
	if (call_groups.size() != 0)
	{
		str_fuuro += "Calls: ";
		for (auto call_group : call_groups) {
			str_fuuro += call_group.to_string();
			str_fuuro += ' ';
		}
		str_fuuro += '\n';
	}

	return fmt::format(
		"Pt: {}\n"
		"Wind: {}\n"
		"Hand: {}\n"
		"{}"
		"River: {}\n"
		"Riichi: {}\n"
		"Menzen: {}", 
		score, 
		wind_to_string(wind), 
		hand_to_string(), 
		str_fuuro, 
		river_to_string(),
		riichi ? "Yes" : "No", 
		menzen ? "Yes" : "No"
	);
}

string Player::tenpai_to_string() const
{
	string s = "";
	for (int i = 0; i < atari_tiles.size(); ++i)
	{
		s += basetile_to_string(atari_tiles[i]);
	}
	return s;
}

void Player::update_atari_tiles()
{
	vector<BaseTile> bt = convert_tiles_to_basetiles(hand);
	atari_tiles = get_atari_hai(bt, get_false_atari_hai());
}

void Player::update_furiten_river()
{
	if (furiten_riichi) return;
	for (auto rivertile : river.river) {
		if (any_of(atari_tiles.begin(), atari_tiles.end(),
			[&rivertile](BaseTile t) {return t == rivertile.tile->tile; })) 
		{
			if (is_riichi()) { furiten_riichi = true; }
			else { furiten_river = true; }
		}
		else {
			furiten_river = false;
		}
	}
}

void Player::remove_atari_tiles(BaseTile t)
{
	// TODO: 不能听5张
	// 暂时没有加入这个规则，假设认为可以听第5张
	// 调用get听牌的地方全部都要修改
	// Player::get_except_tiles()
}

int Player::get_normal向胡数() const {
	auto &inst = Syanten::instance();
    return inst.normal_round_to_win(hand, call_groups.size());
}

vector<SelfAction> Player::get_kakan() const
{
	vector<SelfAction> actions;
	//if (after_chipon == true) return actions;

	for (auto CallGroup : call_groups) {
		if (CallGroup.type == CallGroup::Pon) {
			auto match_tile =
				find_match_tile(hand, CallGroup.tiles[0]->tile);
			if (match_tile != hand.end()) {
				SelfAction action;
				action.action = BaseAction::KaKan;
				action.correspond_tiles.push_back(*match_tile);
				actions.push_back(action);
			}
		}
	}
	return actions;
}

vector<SelfAction> Player::get_ankan() const
{
	vector<SelfAction> actions;

	for (auto tile : hand) {
		auto duplicate = get_n_copies(hand, tile->tile, 4);
		sort(duplicate.begin(), duplicate.end());
		if (duplicate.size() == 4) {
			SelfAction action;
			action.action = BaseAction::AnKan;
			action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
			actions.push_back(action);
		}
	}
	return actions;
}

static bool is_kuikae(const Player* player, BaseTile t) 
 {
	// 拿出最后一个副露
	auto last_CallGroup = player->call_groups.back();

	if (last_CallGroup.type == CallGroup::Pon) {
		// 碰的情况，只要不是那一张就可以了
		if (last_CallGroup.tiles[0]->tile == t)
			return true;
		else return false;
	}
	else if (last_CallGroup.type == CallGroup::Chi) {
		// 吃的情况
		if (last_CallGroup.take == 1) {
			// 嵌张
			if (last_CallGroup.tiles[last_CallGroup.take]->tile == t)
				return true;
			else return false;
		}
		if (last_CallGroup.take == 0) {
			if (is_9hai(last_CallGroup.tiles[2]->tile)) {
				// 考虑(7)89
				if (last_CallGroup.tiles[last_CallGroup.take]->tile == t)
					return true;
				else return false;
			}
			else {
				// (3)45(6)
				if (last_CallGroup.tiles[last_CallGroup.take]->tile == t
					||
					last_CallGroup.tiles[last_CallGroup.take]->tile + 3 == t
					)
					return true;
				else return false;
			}
		}
		if (last_CallGroup.take == 2) {
			if (is_1hai(last_CallGroup.tiles[0]->tile)) {
				// 考虑12(3)
				if (last_CallGroup.tiles[last_CallGroup.take]->tile == t)
					return true;
				else return false;
			}
			else {
				// (3)45(6)
				if (last_CallGroup.tiles[last_CallGroup.take]->tile == t
					||
					last_CallGroup.tiles[last_CallGroup.take]->tile - 3 == t
					)
					return true;
				else return false;
			}
		}
		else throw runtime_error("??");
	}
	else
		throw runtime_error("Cannot read last call group.");
}

vector<SelfAction> Player::get_discard(bool after_chipon) const
{
	profiler _("Player.cpp/get_discard");
	vector<SelfAction> actions;
	for (auto tile : hand) {
		// 检查食替情况,不可打出
		if (after_chipon && is_kuikae(this, tile->tile))
			continue;

		// 其他所有牌均可打出
		SelfAction action;
		action.action = BaseAction::Discard;
		action.correspond_tiles.push_back(tile);
		actions.push_back(action);
	}
	return actions;
}

vector<SelfAction> Player::get_tsumo(const Table* table) const
{
	vector<SelfAction> actions;

	// 听牌列表里的牌可以被自摸
	if (is_in(atari_tiles, hand.back()->tile)) {
		ScoreCounter sc(table, this, nullptr, false, false);
		auto&& result = sc.yaku_counter();
		if (can_agari(result.yakus)) {
			SelfAction action;
			action.action = BaseAction::Tsumo;
			actions.push_back(action);
		}
	}

	return actions;
}

vector<SelfAction> Player::get_riichi() const
{
	vector<SelfAction> actions;

	auto riichi_tiles = is_riichi_able(hand, get_false_atari_hai(), menzen);
	for (auto riichi_tile : riichi_tiles) {

		/* Todo: remove the riichi_tile when the tenpai is not available*/

		SelfAction action;
		action.action = BaseAction::Riichi;
		action.correspond_tiles.push_back(riichi_tile);
		actions.push_back(action);
	}

	return actions;
}

// static int count_yaochuhai(vector<Tile*> hand) {
// 	int counter = 0;
// 	for (int tile = BaseTile::_1m; tile <= BaseTile::_7z; ++tile) {
// 		auto basetile = static_cast<BaseTile>(tile);
// 		if (is_幺九牌(basetile)) {
// 			if (find_match_tile(hand, basetile) != hand.end())
// 				counter++;
// 		}
// 	}
// 	return counter;
// }

vector<SelfAction> Player::get_kyushukyuhai() const
{
	vector<SelfAction> actions;
	if (!first_round) return actions;

	// 考虑到第一巡可以有人暗杠，但是自己不行
	if (hand.size() != 14) return actions;
	
	static auto get_kyuhai = [](const vector<Tile*> &hand) {		
		constexpr BaseTile kyuhai_list[] = {_1m, _9m, _1p, _9p, _1s, _9s, _1z, _2z, _3z, _4z, _5z, _6z, _7z};
		vector<Tile*> kyuhai_collection;
		for (auto tile : kyuhai_list) {
			auto iter = find_match_tile(hand, tile);
			if (iter != hand.end()) {
				kyuhai_collection.push_back(*iter);
			}
		}
		return kyuhai_collection;
	};

	auto kyuhai_collection = get_kyuhai(hand);
	if (kyuhai_collection.size() >= 9) {
		SelfAction action;
		action.action = BaseAction::Kyushukyuhai;
		action.correspond_tiles = kyuhai_collection;
		actions.push_back(action);	
	}
	return actions;
}

static vector<vector<Tile*>> get_Chi_tiles(vector<Tile*> hand, Tile* tile) 
{
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_shuntsu({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[i + j] });
			}
	}
	return chi_tiles;
}

static vector<vector<Tile*>> get_Pon_tiles(vector<Tile*> hand, Tile* tile) 
{
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_koutsu({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[i + j] });

			}
	}
	return chi_tiles;
}

static vector<vector<Tile*>> get_Kan_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	if (hand.size() < 2) {
		return chi_tiles;
	}

	for (int i = 0; i < hand.size() - 2; ++i) {
		for (int j = 1; (i + j) < hand.size() - 1; ++j)
			for (int k = 1; (i + j + k) < hand.size(); ++k)
				if (
					is_kantsu({
						hand[i]->tile,
						hand[i + j]->tile,
						hand[i + j + k]->tile,
						tile->tile })) {
					chi_tiles.push_back({ hand[i] , hand[i + j], hand[i + j + k] });
				}
	}
	return chi_tiles;
}

vector<ResponseAction> Player::get_ron(Table* table, Tile* tile)
{
	vector<ResponseAction> actions;

	if (is_furiten() == true) {
		// 振听直接无
		return {};
	}

	// 听牌列表里的才能荣
	if (is_in(atari_tiles, tile->tile)) {
		ScoreCounter sc(table, this, tile, false, false);
		auto&& result = sc.yaku_counter();
		if (can_agari(result.yakus)) {
			ResponseAction action;
			action.action = BaseAction::Ron;
			action.correspond_tiles = { tile };
			actions.push_back(action);
		}
		else {
			// 如果无役，则进入同巡振听阶段
			furiten_round = true;
		}
	}

	return actions;
}

vector<ResponseAction> Player::get_chi(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;

	if (t >= BaseTile::_1z && t <= BaseTile::_7z)
		// 字牌不能吃
		return actions;

	auto chi_tiles = get_Chi_tiles(hand, tile);
	
	for (auto one_chi_tiles : chi_tiles) {
		// 食替特殊情况
		BaseTile t1 = one_chi_tiles[0]->tile;
		BaseTile t2 = one_chi_tiles[1]->tile;

		if (t2 - t1 == 2) {
			// 坎张
			BaseTile ban_tile = BaseTile(t1 + 1);
			auto copyhand = convert_tiles_to_basetiles(hand);
			erase_n(copyhand, t1, 1);
			erase_n(copyhand, t2, 1);
			if (all_of(copyhand.begin(), copyhand.end(), 
				[ban_tile](BaseTile t) {return t == ban_tile; })) {
				continue;
			}
		}
		else if (t2 - t1 == 1) {
			// 顺子
			vector<BaseTile> ban_tiles;
			if (t1 != _1m && t1 != _1p && t1 != _1s) {
				ban_tiles.push_back(BaseTile(t1 - 1));
			}
			if (t2 != _9m && t2 != _9p && t2 != _9s) {
				ban_tiles.push_back(BaseTile(t2 + 1));
			}
			auto copyhand = convert_tiles_to_basetiles(hand);
			erase_n(copyhand, t1, 1);
			erase_n(copyhand, t2, 1);
			
			if (all_of(copyhand.begin(), copyhand.end(),
				[ban_tiles](BaseTile t) {return is_in(ban_tiles, t); })) {
				continue;
			}
		}
		// 不属于食替特殊情况才可以吃
		ResponseAction action;
		action.action = BaseAction::Chi;
		action.correspond_tiles = one_chi_tiles;
		actions.push_back(action);
	}

	return actions;
}

vector<ResponseAction> Player::get_pon(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;
	auto chi_tiles = get_Pon_tiles(hand, tile);

	for (auto one_chi_tiles : chi_tiles) {
		ResponseAction action;
		action.action = BaseAction::Pon;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

vector<ResponseAction> Player::get_kan(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;
	auto kan_tiles = get_Kan_tiles(hand, tile);
	sort(kan_tiles.begin(), kan_tiles.end());
	for (auto one_chi_tiles : kan_tiles) {
		ResponseAction action;
		action.action = BaseAction::Kan;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

vector<ResponseAction> Player::get_chanankan(Tile* tile)
{
	vector<ResponseAction> actions;
	if (!is_yaochuhai(tile->tile)) { return {}; }

	if (is_in(atari_tiles, tile->tile)) {
		auto copyhand = hand;
		copyhand.push_back(tile);
		if (is_kokushi_shape(convert_tiles_to_basetiles(copyhand)))
		{
			ResponseAction action;
			action.action = BaseAction::ChanAnKan;
			action.correspond_tiles = { tile };
			actions.push_back(action);
		}
	}

	return actions;
}

vector<ResponseAction> Player::get_chankan(Tile* tile)
{
	vector<ResponseAction> actions;

	if (is_in(atari_tiles, tile->tile)) {
		ResponseAction action;
		action.action = BaseAction::ChanKan;
		action.correspond_tiles = { tile };
		actions.push_back(action);
	}

	return actions;
}

vector<SelfAction> Player::riichi_get_ankan()
{
	vector<SelfAction> actions;

	// 从手牌获取听牌
	// auto original_听牌 = atari_tiles;

	for (auto tile : hand) {
		auto duplicate = get_n_copies(hand, tile->tile, 4);

		if (duplicate.size() == 4) {

			// 尝试从手牌删除掉这四张牌，之后检查听牌
			vector<Tile*> copyhand(hand.begin(), hand.end());
			copyhand.erase(
				remove_if(copyhand.begin(), copyhand.end(),
					[duplicate](Tile* tile) {
						if (tile->tile == duplicate[0]->tile) return true;
						else return false;
					}), copyhand.end());

			auto new_atari_hai = get_atari_hai(convert_tiles_to_basetiles(copyhand),
				get_false_atari_hai());
			
			if (is_same_container(new_atari_hai, atari_tiles)) {
				SelfAction action;
				action.action = BaseAction::AnKan;
				action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
				actions.push_back(action);
			}
		}
	}
	return actions;
}

vector<SelfAction> Player::riichi_get_discard()
{
	vector<SelfAction> actions;

	SelfAction action;
	action.action = BaseAction::Discard;
	action.correspond_tiles.push_back(hand.back());
	actions.push_back(action);

	return actions;
}

void Player::execute_naki(vector<Tile*> tiles, Tile* tile, int relative_position)
{
	menzen = false;
	CallGroup call_group;
	if (is_koutsu({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// 碰的情况
		// 创建对象
		call_group.type = CallGroup::Pon;
		switch (relative_position) {
		case 1: // 下家
		case -3:
			call_group.take = 2; break;
		case 2: // 对家
		case -2:
			call_group.take = 1; break;
		case 3: // 上家
		case -1:
			call_group.take = 0; break;
		default:
			throw runtime_error("Bad Position in Fulu (Pon/Kan).");
		}
		call_group.tiles = { tiles[0], tiles[1], tile };

		// 加入
		call_groups.push_back(call_group);

		// 删掉原来的牌
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		return;
	}
	if (is_shuntsu({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// 吃的情况
		// 创建对象
		call_group.type = CallGroup::Chi;
		if (tile->tile < tiles[0]->tile) {
			//(1)23
			call_group.take = 0;
			call_group.tiles = { tile, tiles[0], tiles[1] };
		}
		else if (tile->tile > tiles[1]->tile) {
			//12(3)
			call_group.take = 2;
			call_group.tiles = { tiles[0], tiles[1], tile };
		}
		else {
			//1(2)3
			call_group.take = 1;
			call_group.tiles = { tiles[0], tile, tiles[1] };
		}
		// 加入
		call_groups.push_back(call_group);

		// 删掉原来的牌
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		return;
	}
	if (is_kantsu({ tiles[0]->tile, tiles[1]->tile, tiles[2]->tile, tile->tile })
		&& tiles.size() == 3) {
		// 杠的情况
		// 创建对象
		call_group.type = CallGroup::DaiMinKan;
		switch (relative_position % 4) {
		case 1: // 下家
		case -3:
			call_group.take = 2; break;
		case 2: // 对家
		case -2:
			call_group.take = 1; break;
		case 3: // 上家
		case -1:
			call_group.take = 0; break;
		default:
			throw runtime_error("Bad Position in Fulu (Pon/Kan).");
		}
		call_group.tiles = { tiles[0], tiles[1], tiles[2], tile };

		// 加入
		call_groups.push_back(call_group);

		// 删掉原来的牌
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		hand.erase(find(hand.begin(), hand.end(), tiles[2]));
		return;
	}
}

void Player::remove_from_hand(Tile* tile)
{
	auto iter =	remove_if(hand.begin(), hand.end(), 
		[tile](Tile* t) {return tile == t; });
	hand.erase(iter, hand.end());
}

void Player::execute_ankan(BaseTile tile)
{
	CallGroup CallGroup;
	CallGroup.type = CallGroup::AnKan;
	CallGroup.take = 0;

	for_each(hand.begin(), hand.end(),
		[&CallGroup, tile](Tile* t)
		{
			if (tile == t->tile) CallGroup.tiles.push_back(t);
		});
	auto iter = remove_if(hand.begin(), hand.end(),
			[tile](Tile* t) {return t->tile == tile; });
	call_groups.push_back(CallGroup);
	hand.erase(iter, hand.end());
}

void Player::execute_kakan(Tile* tile)
{
	for (auto& CallGroup : call_groups) {
		if (CallGroup.type == CallGroup::Pon) {
			if (tile->tile == CallGroup.tiles[0]->tile)
			{
				CallGroup.type = CallGroup::KaKan;
				CallGroup.tiles.push_back(tile);
			}
		}
	}
	remove_from_hand(tile);
}

std::vector<BaseTile> Player::get_false_atari_hai() const
{
	// add the tiles with four in hands
	static std::array<int, N_BASETILES> tile_counter;

	std::vector<BaseTile> except_tiles;
	tile_counter.fill(0);
	for (auto tile : hand)
	{
		tile_counter[int(tile->tile)]++;
		if (tile_counter[int(tile->tile)] == 4)
			except_tiles.push_back(tile->tile);
	}
	return except_tiles;
}

void Player::execute_discard(Tile* tile, int& number, bool on_riichi, bool fromhand)
{
	remove_from_hand(tile);
	number++;
	river.push_back({ tile, number, riichi || on_riichi, true, fromhand });
}

void Player::sort_hand()
{
	sort(hand.begin(), hand.end());
}

namespace_mahjong_end

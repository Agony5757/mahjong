#include "Player.h"
#include "Table.h"

namespace_mahjong
using namespace std;

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
	stringstream ss;
	ss << "点数:" << score << endl;
	ss << "自风" << wind_to_string(wind) << endl;
	ss << "手牌:" << hand_to_string();

	if (副露s.size() != 0)
	{
		ss << " 副露:";
		for (auto fulu : 副露s)
			ss << fulu.to_string() << " ";
	}

	ss << endl;
	ss << "牌河:" << river_to_string();
	ss << endl;

	if (riichi)	ss << "立";
	else 		ss << "No立";

	ss << "|";

	if (门清)	ss << "门清";
	else		ss << "副露";
	ss << endl;

	return ss.str();
}

string Player::tenpai_to_string() const
{
	string s = "";
	for (int i = 0; i < 听牌.size(); ++i)
	{
		s += basetile_to_string(听牌[i]);
	}
	return s;
}

void Player::update_听牌()
{
	听牌 = get听牌(convert_tiles_to_basetiles(hand));
}

void Player::update_舍牌振听()
{
	if (立直振听) return;
	for (auto rivertile : river.river) {
		if (any_of(听牌.begin(), 听牌.end(),
			[&rivertile](BaseTile t) {return t == rivertile.tile->tile; })) 
		{
			if (is_riichi()) { 立直振听 = true; }
			else { 舍牌振听 = true; }
		}
		else {
			舍牌振听 = false;
		}
	}
}

void Player::remove_听牌(BaseTile t)
{
	// TODO: 不能听5张
	// 暂时没有加入这个规则，假设认为可以听第5张
	// 调用get听牌的地方全部都要修改
	// Player::get_except_tiles()
}

int Player::get_normal向胡数()const {
	auto &inst = Syanten::instance();
    return inst.normal_round_to_win(hand, 副露s.size());
}

vector<SelfAction> Player::get_加杠() const 
{
	vector<SelfAction> actions;
	//if (after_chipon == true) return actions;

	for (auto fulu : 副露s) {
		if (fulu.type == Fulu::Pon) {
			auto match_tile =
				find_match_tile(hand, fulu.tiles[0]->tile);
			if (match_tile != hand.end()) {
				SelfAction action;
				action.action = BaseAction::加杠;
				action.correspond_tiles.push_back(*match_tile);
				actions.push_back(action);
			}
		}
	}
	return actions;
}

vector<SelfAction> Player::get_暗杠() const
{
	vector<SelfAction> actions;

	for (auto tile : hand) {
		auto duplicate = get_duplicate(hand, tile->tile, 4);
		sort(duplicate.begin(), duplicate.end());
		if (duplicate.size() == 4) {
			SelfAction action;
			action.action = BaseAction::暗杠;
			action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
			actions.push_back(action);
		}
	}
	return actions;
}

static bool is食替(const Player* player, BaseTile t)
 {
	// 拿出最后一个副露
	auto last_fulu = player->副露s.back();

	if (last_fulu.type == Fulu::Pon) {
		// 碰的情况，只要不是那一张就可以了
		if (last_fulu.tiles[0]->tile == t)
			return true;
		else return false;
	}
	else if (last_fulu.type == Fulu::Chi) {
		// 吃的情况
		if (last_fulu.take == 1) {
			// 嵌张
			if (last_fulu.tiles[last_fulu.take]->tile == t)
				return true;
			else return false;
		}
		if (last_fulu.take == 0) {
			if (is_九牌(last_fulu.tiles[2]->tile)) {
				// 考虑(7)89
				if (last_fulu.tiles[last_fulu.take]->tile == t)
					return true;
				else return false;
			}
			else {
				// (3)45(6)
				if (last_fulu.tiles[last_fulu.take]->tile == t
					||
					last_fulu.tiles[last_fulu.take]->tile + 3 == t
					)
					return true;
				else return false;
			}
		}
		if (last_fulu.take == 2) {
			if (is_幺牌(last_fulu.tiles[0]->tile)) {
				// 考虑12(3)
				if (last_fulu.tiles[last_fulu.take]->tile == t)
					return true;
				else return false;
			}
			else {
				// (3)45(6)
				if (last_fulu.tiles[last_fulu.take]->tile == t
					||
					last_fulu.tiles[last_fulu.take]->tile - 3 == t
					)
					return true;
				else return false;
			}
		}
		else throw runtime_error("??");
	}
	else
		throw runtime_error("最后一手既不是吃又不是碰，不考虑食替");
}

vector<SelfAction> Player::get_打牌(bool after_chipon) const
{
	profiler _("Player.cpp/get_discard");
	vector<SelfAction> actions;
	for (auto tile : hand) {
		// 检查食替情况,不可打出
		if (after_chipon && is食替(this, tile->tile))
			continue;

		// 其他所有牌均可打出
		SelfAction action;
		action.action = BaseAction::出牌;
		action.correspond_tiles.push_back(tile);
		actions.push_back(action);
	}
	return actions;
}

vector<SelfAction> Player::get_自摸(const Table* table) const
{
	vector<SelfAction> actions;

	// 听牌列表里的牌可以被自摸
	if (is_in(听牌, hand.back()->tile)) {
		ScoreCounter sc(table, this, nullptr, false, false);
		auto&& result = sc.yaku_counter();
		if (can_agari(result.yakus)) {
			SelfAction action;
			action.action = BaseAction::自摸;
			actions.push_back(action);
		}
	}

	return actions;
}

vector<SelfAction> Player::get_立直() const
{
	vector<SelfAction> actions;

	auto riichi_tiles = is_riichi_able(hand, 门清);
	for (auto riichi_tile : riichi_tiles) {
		SelfAction action;
		action.action = BaseAction::立直;
		action.correspond_tiles.push_back(riichi_tile);
		actions.push_back(action);
	}

	return actions;
}

// static int 九种九牌counter(vector<Tile*> hand) {
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

vector<SelfAction> Player::get_九种九牌() const
{
	vector<SelfAction> actions;
	if (!first_round) return actions;

	// 考虑到第一巡可以有人暗杠，但是自己不行
	if (hand.size() != 14) return actions;
	
	static auto get_九牌 = [](const vector<Tile*> &hand) {		
		constexpr BaseTile 幺九牌list[] = {_1m, _9m, _1p, _9p, _1s, _9s, _1z, _2z, _3z, _4z, _5z, _6z, _7z};
		vector<Tile*> 九牌collection;
		for (auto tile : 幺九牌list) {
			auto iter = find_match_tile(hand, tile);
			if (iter != hand.end()) {
				九牌collection.push_back(*iter);
			}
		}
		return 九牌collection;
	};

	auto 九牌collection = get_九牌(hand);
	if (九牌collection.size() >= 9) {
		SelfAction action;
		action.action = BaseAction::九种九牌;
		action.correspond_tiles = 九牌collection;
		actions.push_back(action);	
	}
	return actions;
}

static vector<vector<Tile*>> get_Chi_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_顺子({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[i + j] });
			}
	}
	return chi_tiles;
}

static vector<vector<Tile*>> get_Pon_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_刻子({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
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
					is_杠({
						hand[i]->tile,
						hand[i + j]->tile,
						hand[i + j + k]->tile,
						tile->tile })) {
					chi_tiles.push_back({ hand[i] , hand[i + j], hand[i + j + k] });
				}
	}
	return chi_tiles;
}

vector<ResponseAction> Player::get_荣和(Table* table, Tile* tile)
{
	vector<ResponseAction> actions;

	if (is振听() == true) {
		// 振听直接无
		return {};
	}

	// 听牌列表里的才能荣
	if (is_in(听牌, tile->tile)) {
		ScoreCounter sc(table, this, tile, false, false);
		auto&& result = sc.yaku_counter();
		if (can_agari(result.yakus)) {
			ResponseAction action;
			action.action = BaseAction::荣和;
			action.correspond_tiles = { tile };
			actions.push_back(action);
		}
		else {
			// 如果无役，则进入同巡振听阶段
			同巡振听 = true;
		}
	}

	return actions;
}

vector<ResponseAction> Player::get_Chi(Tile* tile)
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
		action.action = BaseAction::吃;
		action.correspond_tiles = one_chi_tiles;
		actions.push_back(action);
	}

	return actions;
}

vector<ResponseAction> Player::get_Pon(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;
	auto chi_tiles = get_Pon_tiles(hand, tile);

	for (auto one_chi_tiles : chi_tiles) {
		ResponseAction action;
		action.action = BaseAction::碰;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

vector<ResponseAction> Player::get_Kan(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;
	auto kan_tiles = get_Kan_tiles(hand, tile);
	sort(kan_tiles.begin(), kan_tiles.end());
	for (auto one_chi_tiles : kan_tiles) {
		ResponseAction action;
		action.action = BaseAction::杠;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

vector<ResponseAction> Player::get_抢暗杠(Tile* tile)
{
	vector<ResponseAction> actions;
	if (!is_幺九牌(tile->tile)) { return {}; }

	if (is_in(听牌, tile->tile)) {
		auto copyhand = hand;
		copyhand.push_back(tile);
		if (is国士无双和牌型(convert_tiles_to_basetiles(copyhand)))
		{
			ResponseAction action;
			action.action = BaseAction::抢暗杠;
			action.correspond_tiles = { tile };
			actions.push_back(action);
		}
	}

	return actions;
}

vector<ResponseAction> Player::get_抢杠(Tile* tile)
{
	vector<ResponseAction> actions;

	if (is_in(听牌, tile->tile)) {
		ResponseAction action;
		action.action = BaseAction::抢杠;
		action.correspond_tiles = { tile };
		actions.push_back(action);
	}

	return actions;
}

vector<SelfAction> Player::riichi_get_暗杠()
{
	vector<SelfAction> actions;

	// 从手牌获取听牌
	auto original_听牌 = 听牌;

	for (auto tile : hand) {
		auto duplicate = get_duplicate(hand, tile->tile, 4);
		if (duplicate.size() == 4) {

			// 尝试从手牌删除掉这四张牌，之后检查听牌
			vector<Tile*> copyhand(hand.begin(), hand.end());
			copyhand.erase(
				remove_if(copyhand.begin(), copyhand.end(),
					[duplicate](Tile* tile) {
						if (tile->tile == duplicate[0]->tile) return true;
						else return false;
					}), copyhand.end());

			auto final_听牌 = get听牌(convert_tiles_to_basetiles(copyhand));

			if (is_same_container(final_听牌, original_听牌)) {
				SelfAction action;
				action.action = BaseAction::暗杠;
				action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
				actions.push_back(action);
			}
		}
	}
	return actions;
}

vector<SelfAction> Player::riichi_get_打牌()
{
	vector<SelfAction> actions;

	SelfAction action;
	action.action = BaseAction::出牌;
	action.correspond_tiles.push_back(hand.back());
	actions.push_back(action);

	return actions;
}

void Player::move_from_hand_to_fulu(vector<Tile*> tiles, Tile* tile, int relative_position)
{
	Fulu fulu;
	if (is_刻子({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// 碰的情况
		// 创建对象
		fulu.type = Fulu::Pon;
		switch (relative_position) {
		case 1: // 下家
		case -3:
			fulu.take = 2; break;
		case 2: // 对家
		case -2:
			fulu.take = 1; break;
		case 3: // 上家
		case -1:
			fulu.take = 0; break;
		default:
			throw runtime_error("Bad Position in Fulu (Pon/Kan).");
		}
		fulu.tiles = { tiles[0], tiles[1], tile };

		// 加入
		副露s.push_back(fulu);

		// 删掉原来的牌
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		return;
	}
	if (is_顺子({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// 吃的情况
		// 创建对象
		fulu.type = Fulu::Chi;
		if (tile->tile < tiles[0]->tile) {
			//(1)23
			fulu.take = 0;
			fulu.tiles = { tile, tiles[0], tiles[1] };
		}
		else if (tile->tile > tiles[1]->tile) {
			//12(3)
			fulu.take = 2;
			fulu.tiles = { tiles[0], tiles[1], tile };
		}
		else {
			//1(2)3
			fulu.take = 1;
			fulu.tiles = { tiles[0], tile, tiles[1] };
		}
		// 加入
		副露s.push_back(fulu);

		// 删掉原来的牌
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		return;
	}
	if (is_杠({ tiles[0]->tile, tiles[1]->tile, tiles[2]->tile, tile->tile })
		&& tiles.size() == 3) {
		// 杠的情况
		// 创建对象
		fulu.type = Fulu::大明杠;
		switch (relative_position % 4) {
		case 1: // 下家
		case -3:
			fulu.take = 2; break;
		case 2: // 对家
		case -2:
			fulu.take = 1; break;
		case 3: // 上家
		case -1:
			fulu.take = 0; break;
		default:
			throw runtime_error("Bad Position in Fulu (Pon/Kan).");
		}
		fulu.tiles = { tiles[0], tiles[1], tiles[2], tile };

		// 加入
		副露s.push_back(fulu);

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

void Player::play_暗杠(BaseTile tile)
{
	Fulu fulu;
	fulu.type = Fulu::暗杠;
	fulu.take = 0;

	for_each(hand.begin(), hand.end(),
		[&fulu, tile](Tile* t)
		{
			if (tile == t->tile) fulu.tiles.push_back(t);
		});
	auto iter = remove_if(hand.begin(), hand.end(),
			[tile](Tile* t) {return t->tile == tile; });
	副露s.push_back(fulu);
	hand.erase(iter, hand.end());
}

void Player::play_加杠(Tile* tile)
{
	门清 = false;
	for (auto& fulu : 副露s) {
		if (fulu.type == Fulu::Pon) {
			if (tile->tile == fulu.tiles[0]->tile)
			{
				fulu.type = Fulu::加杠;
				fulu.tiles.push_back(tile);
			}
		}
	}
	remove_from_hand(tile);
}

void Player::move_from_hand_to_river(Tile* tile, int& number, bool on_riichi, bool fromhand)
{
	remove_from_hand(tile);
	number++;
	river.push_back({ tile, number, riichi || on_riichi, true, fromhand });
}

void Player::sort_hand()
{
	sort(hand.begin(), hand.end());
}

void Player::test_show_hand()
{
	cout << hand_to_string();
}

namespace_mahjong_end

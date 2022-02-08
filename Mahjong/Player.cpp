#include "Player.h"
#include "Table.h"

using namespace std;

Player::Player() 
{ }

Player::Player(int init_score)
{
	score = init_score;
}

std::string Player::hand_to_string() const
{
	stringstream ss;

	for (auto hand_tile : hand) {
		ss << hand_tile->to_string() << " ";
	}
	return ss.str();
}

std::string Player::river_to_string() const
{
	return river.to_string();
}

std::string Player::to_string() const
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


std::vector<SelfAction> Player::get_加杠()
{
	vector<SelfAction> actions;
	//if (after_chipon == true) return actions;

	for (auto fulu : 副露s) {
		if (fulu.type == Fulu::Pon) {
			auto match_tile =
				find_match_tile(hand, fulu.tiles[0]->tile);
			if (match_tile != hand.end()) {
				SelfAction action;
				action.correspond_tiles.push_back(*match_tile);
				action.action = Action::加杠;
				actions.push_back(action);
			}
		}
	}
	return actions;
}

std::vector<SelfAction> Player::get_暗杠()
{
	vector<SelfAction> actions;

	for (auto tile : hand) {
		auto duplicate = get_duplicate(hand, tile->tile, 4);
		if (duplicate.size() == 4) {
			SelfAction action;
			action.action = Action::暗杠;
			action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
			actions.push_back(action);
		}
	}
	return actions;
}

static bool is食替(Player* player, BaseTile t)
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

std::vector<SelfAction> Player::get_打牌(bool after_chipon)
{
	vector<SelfAction> actions;
	for (auto tile : hand) {
		// 检查食替情况,不可打出
		if (after_chipon)
			if (is食替(this, tile->tile))
				continue;

		// 其他所有牌均可打出
		SelfAction action;
		action.action = Action::出牌;
		action.correspond_tiles.push_back(tile);
		actions.push_back(action);
	}
	return actions;
}

std::vector<SelfAction> Player::get_自摸()
{
	std::vector<SelfAction> actions;
	if (is和牌(convert_tiles_to_base_tiles(hand))) {
		SelfAction action;
		action.action = Action::自摸;
		actions.push_back(action);
	}
	// 在桌子那边加以过滤
	return actions;
}

std::vector<SelfAction> Player::get_立直()
{
	std::vector<SelfAction> actions;

	auto riichi_tiles = is_riichi_able(hand, 门清);
	for (auto riichi_tile : riichi_tiles) {
		SelfAction action;
		action.action = Action::立直;
		action.correspond_tiles.push_back(riichi_tile);
		actions.push_back(action);
	}

	return actions;
}

static int 九种九牌counter(std::vector<Tile*> hand) {
	int counter = 0;
	for (int tile = BaseTile::_1m; tile <= BaseTile::中; ++tile) {
		auto basetile = static_cast<BaseTile>(tile);
		if (is_幺九牌(basetile)) {
			if (find_match_tile(hand, basetile) != hand.end())
				counter++;
		}
	}
	return counter;
}

std::vector<SelfAction> Player::get_九种九牌()
{
	vector<SelfAction> actions;
	if (!first_round) return actions;

	// 考虑到第一巡可以有人暗杠，但是自己不行
	if (hand.size() != 14) return actions;

	if (九种九牌counter(hand) >= 9) {
		SelfAction action;
		action.action = Action::九种九牌;
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

std::vector<ResponseAction> Player::get_荣和(Table* table, Tile* tile)
{
	std::vector<ResponseAction> actions;

	auto copy_hand = hand;
	copy_hand.push_back(tile);

	if (is和牌(convert_tiles_to_base_tiles(copy_hand))) {
		ResponseAction action;
		action.action = Action::荣和;
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_Chi(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;

	if (t >= BaseTile::east && t <= BaseTile::中)
		// 字牌不能吃
		return actions;

	auto chi_tiles = get_Chi_tiles(hand, tile);
	for (auto one_chi_tiles : chi_tiles) {
		ResponseAction action;
		action.action = Action::吃;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_Pon(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;
	auto chi_tiles = get_Pon_tiles(hand, tile);

	for (auto one_chi_tiles : chi_tiles) {
		ResponseAction action;
		action.action = Action::碰;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_Kan(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;
	auto chi_tiles = get_Kan_tiles(hand, tile);

	for (auto one_chi_tiles : chi_tiles) {
		ResponseAction action;
		action.action = Action::杠;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_抢暗杠(Tile* tile)
{
	std::vector<ResponseAction> actions;

	auto copy_hand = hand;
	copy_hand.push_back(tile);

	if (is国士无双和牌型(convert_tiles_to_base_tiles(copy_hand))) {
		ResponseAction action;
		action.action = Action::抢暗杠;
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_抢杠(Tile* tile)
{
	std::vector<ResponseAction> actions;

	auto copy_hand = hand;
	copy_hand.push_back(tile);

	if (is和牌(convert_tiles_to_base_tiles(copy_hand))) {
		ResponseAction action;
		action.action = Action::抢杠;
		actions.push_back(action);
	}

	return actions;
}

std::vector<SelfAction> Player::riichi_get_暗杠()
{
	vector<SelfAction> actions;

	// 从手牌获取听牌
	auto original_听牌 = get听牌(convert_tiles_to_base_tiles(hand));

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

			auto final_听牌 = get听牌(convert_tiles_to_base_tiles(copyhand));

			if (is_same_container(final_听牌, original_听牌)) {
				SelfAction action;
				action.action = Action::暗杠;
				action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
				actions.push_back(action);
			}
		}
	}
	return actions;
}

std::vector<SelfAction> Player::riichi_get_打牌()
{
	vector<SelfAction> actions;

	SelfAction action;
	action.action = Action::出牌;
	action.correspond_tiles.push_back(hand.back());
	actions.push_back(action);

	return actions;
}

void Player::move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile)
{
	Fulu fulu;
	if (is_刻子({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// 碰的情况
		// 创建对象
		fulu.type = Fulu::Pon;
		fulu.take = 0;
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
		fulu.take = 0;
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
			if (tile == t->tile)
				fulu.tiles.push_back(t);
		});
	auto iter = remove_if(hand.begin(), hand.end(),
			[tile](Tile* t) {return t->tile == tile; });
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

void Player::move_from_hand_to_river(Tile* tile, int& number, bool remain, bool fromhand)
{
	remove_from_hand(tile);
	number++;
	river.push_back({ tile, number, riichi, remain, fromhand });
}

void Player::sort_hand()
{
	std::sort(hand.begin(), hand.end(), tile_comparator);
}

void Player::test_show_hand()
{
	cout << hand_to_string();
}
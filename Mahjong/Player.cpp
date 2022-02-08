#include "Player.h"

Player::Player()
	:riichi(false), score(INIT_SCORE)
{ }

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
	ss << "����:" << score << endl;
	ss << "�Է�" << wind_to_string(wind) << endl;
	ss << "����:" << hand_to_string();

	if (��¶s.size() != 0)
	{
		ss << " ��¶:";
		for (auto fulu : ��¶s)
			ss << fulu.to_string() << " ";
	}

	ss << endl;
	ss << "�ƺ�:" << river_to_string();
	ss << endl;

	if (riichi)	ss << "��";
	else 		ss << "No��";

	ss << "|";

	if (����)	ss << "����";
	else		ss << "��¶";
	ss << endl;

	return ss.str();
}


std::vector<SelfAction> Player::get_�Ӹ�()
{
	vector<SelfAction> actions;
	//if (after_chipon == true) return actions;

	for (auto fulu : ��¶s) {
		if (fulu.type == Fulu::Pon) {
			auto match_tile =
				find_match_tile(hand, fulu.tiles[0]->tile);
			if (match_tile != hand.end()) {
				SelfAction action;
				action.correspond_tiles.push_back(*match_tile);
				action.action = Action::�Ӹ�;
				actions.push_back(action);
			}
		}
	}
	return actions;
}

std::vector<SelfAction> Player::get_����()
{
	vector<SelfAction> actions;
	//if (after_chipon == true) return actions;

	for (auto tile : hand) {
		auto duplicate = get_duplicate(hand, tile->tile, 4);
		if (duplicate.size() == 4) {
			SelfAction action;
			action.action = Action::����;
			action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
			actions.push_back(action);
		}
	}
	return actions;
}

static bool isʳ��(Player* player, BaseTile t) {
	// �ó����һ����¶
	auto last_fulu = player->��¶s.back();

	if (last_fulu.type == Fulu::Pon) {
		// ���������ֻҪ������һ�žͿ�����
		if (last_fulu.tiles[0]->tile == t)
			return true;
		else return false;
	}
	else if (last_fulu.type == Fulu::Chi) {
		// �Ե����
		if (last_fulu.take == 1) {
			// Ƕ��
			if (last_fulu.tiles[last_fulu.take]->tile == t)
				return true;
			else return false;
		}
		if (last_fulu.take == 0) {
			if (is_����(last_fulu.tiles[2]->tile)) {
				// ����(7)89
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
			if (is_����(last_fulu.tiles[0]->tile)) {
				// ����12(3)
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
		throw runtime_error("���һ�ּȲ��ǳ��ֲ�������������ʳ��");
}

std::vector<SelfAction> Player::get_����(bool after_chipon)
{
	vector<SelfAction> actions;
	for (auto tile : hand) {
		// ���ʳ�����,���ɴ��
		if (after_chipon)
			if (isʳ��(this, tile->tile))
				continue;

		// ���������ƾ��ɴ��
		SelfAction action;
		action.action = Action::����;
		action.correspond_tiles.push_back(tile);
		actions.push_back(action);
	}
	return actions;
}

std::vector<SelfAction> Player::get_����(Table* table)
{
	// cout << "Warning:���� is not considered yet" << endl;

	std::vector<SelfAction> actions;
	if (is����(convert_tiles_to_base_tiles(hand))) {
		SelfAction action;
		action.action = Action::����;
		actions.push_back(action);
	}
	// �������Ǳ߼��Թ���
	return actions;
}

std::vector<SelfAction> Player::get_��ֱ()
{
	// cout << "Warning:��ֱ is not considered yet" << endl;
	std::vector<SelfAction> actions;

	auto riichi_tiles = is_riichi_able(hand, ����);
	for (auto riichi_tile : riichi_tiles) {
		SelfAction action;
		action.action = Action::��ֱ;
		action.correspond_tiles.push_back(riichi_tile);
		actions.push_back(action);
	}

	return actions;
}

static int ���־���counter(std::vector<Tile*> hand) {
	int counter = 0;
	for (int tile = BaseTile::_1m; tile <= BaseTile::��; ++tile) {
		auto basetile = static_cast<BaseTile>(tile);
		if (is_�۾���(basetile)) {
			if (find_match_tile(hand, basetile) != hand.end())
				counter++;
		}
	}
	return counter;
}

std::vector<SelfAction> Player::get_���־���()
{
	vector<SelfAction> actions;
	if (!first_round) return actions;

	// ���ǵ���һѲ�������˰��ܣ������Լ�����
	if (hand.size() != 14) return actions;

	if (���־���counter(hand) >= 9) {
		SelfAction action;
		action.action = Action::���־���;
		actions.push_back(action);
	}
	return actions;
}

static
vector<vector<Tile*>> get_Chi_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_˳��({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[i + j] });

			}
	}
	return chi_tiles;
}

static
vector<vector<Tile*>> get_Pon_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_����({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[i + j] });

			}
	}
	return chi_tiles;
}

static
vector<vector<Tile*>> get_Kan_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	if (hand.size() < 2) {
		return chi_tiles;
	}

	for (int i = 0; i < hand.size() - 2; ++i) {
		for (int j = 1; (i + j) < hand.size() - 1; ++j)
			for (int k = 1; (i + j + k) < hand.size(); ++k)
				if (
					is_��({
						hand[i]->tile,
						hand[i + j]->tile,
						hand[i + j + k]->tile,
						tile->tile })) {
					chi_tiles.push_back({ hand[i] , hand[i + j], hand[i + j + k] });
				}
	}
	return chi_tiles;
}

std::vector<ResponseAction> Player::get_�ٺ�(Table* table, Tile* tile)
{
	std::vector<ResponseAction> actions;

	auto copy_hand = hand;
	copy_hand.push_back(tile);

	if (is����(convert_tiles_to_base_tiles(copy_hand))) {
		ResponseAction action;
		action.action = Action::�ٺ�;
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_Chi(Tile* tile)
{
	vector<ResponseAction> actions;

	BaseTile t = tile->tile;

	if (t >= BaseTile::east && t <= BaseTile::��)
		// ���Ʋ��ܳ�
		return actions;

	auto chi_tiles = get_Chi_tiles(hand, tile);
	for (auto one_chi_tiles : chi_tiles) {
		ResponseAction action;
		action.action = Action::��;
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
		action.action = Action::��;
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
		action.action = Action::��;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_������(Tile* tile)
{
	std::vector<ResponseAction> actions;

	auto copy_hand = hand;
	copy_hand.push_back(tile);

	if (is��ʿ��˫������(convert_tiles_to_base_tiles(copy_hand))) {
		ResponseAction action;
		action.action = Action::������;
		actions.push_back(action);
	}

	return actions;
}

std::vector<ResponseAction> Player::get_����(Tile* tile)
{
	std::vector<ResponseAction> actions;

	auto copy_hand = hand;
	copy_hand.push_back(tile);

	if (is����(convert_tiles_to_base_tiles(copy_hand))) {
		ResponseAction action;
		action.action = Action::����;
		actions.push_back(action);
	}

	return actions;
}

std::vector<SelfAction> Player::riichi_get_����(Table* table)
{
	vector<SelfAction> actions;
	if (table->dora_spec == 5) {
		// �Ѿ�4�ܣ���׼�ٸ�
		return actions;
	}

	// �����ƻ�ȡ����
	auto original_���� = get����(convert_tiles_to_base_tiles(hand));

	for (auto tile : hand) {
		auto duplicate = get_duplicate(hand, tile->tile, 4);
		if (duplicate.size() == 4) {

			// ���Դ�����ɾ�����������ƣ�֮��������
			vector<Tile*> copyhand(hand.begin(), hand.end());
			copyhand.erase(
				remove_if(copyhand.begin(), copyhand.end(),
					[duplicate](Tile* tile) {
						if (tile->tile == duplicate[0]->tile) return true;
						else return false;
					}), copyhand.end());

			auto final_���� = get����(convert_tiles_to_base_tiles(copyhand));

			if (is_same_container(final_����, original_����)) {
				SelfAction action;
				action.action = Action::����;
				action.correspond_tiles.assign(duplicate.begin(), duplicate.end());
				actions.push_back(action);
			}
		}
	}
	return actions;
}

std::vector<SelfAction> Player::riichi_get_����()
{
	vector<SelfAction> actions;

	SelfAction action;
	action.action = Action::����;
	action.correspond_tiles.push_back(hand.back());
	actions.push_back(action);

	return actions;
}

void Player::move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile)
{
	Fulu fulu;
	if (is_����({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// �������
		// ��������
		fulu.type = Fulu::Pon;
		fulu.take = 0;
		fulu.tiles = { tiles[0], tiles[1], tile };

		// ����
		��¶s.push_back(fulu);

		// ɾ��ԭ������
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		return;
	}
	if (is_˳��({ tiles[0]->tile, tiles[1]->tile, tile->tile })
		&& tiles.size() == 2) {
		// �Ե����
		// ��������
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
		// ����
		��¶s.push_back(fulu);

		// ɾ��ԭ������
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		return;
	}
	if (is_��({ tiles[0]->tile, tiles[1]->tile, tiles[2]->tile, tile->tile })
		&& tiles.size() == 3) {
		// �ܵ����
		// ��������
		fulu.type = Fulu::������;
		fulu.take = 0;
		fulu.tiles = { tiles[0], tiles[1], tiles[2], tile };

		// ����
		��¶s.push_back(fulu);

		// ɾ��ԭ������
		hand.erase(find(hand.begin(), hand.end(), tiles[0]));
		hand.erase(find(hand.begin(), hand.end(), tiles[1]));
		hand.erase(find(hand.begin(), hand.end(), tiles[2]));
		return;
	}
}

void Player::remove_from_hand(Tile* tile)
{
	auto iter =
		remove_if(hand.begin(), hand.end(), [tile](Tile* t) {return tile == t; });
	hand.erase(iter, hand.end());
}

void Player::play_����(BaseTile tile)
{
	Fulu fulu;
	fulu.type = Fulu::����;
	fulu.take = 0;

	for_each(hand.begin(), hand.end(),
		[&fulu, tile](Tile* t)
		{
			if (tile == t->tile)
				fulu.tiles.push_back(t);
		});
	auto iter =
		remove_if(hand.begin(), hand.end(),
			[tile](Tile* t) {return t->tile == tile; });
	hand.erase(iter, hand.end());
}

void Player::play_�Ӹ�(Tile* tile)
{
	���� = false;
	for (auto& fulu : ��¶s) {
		if (fulu.type == Fulu::Pon) {
			if (tile->tile == fulu.tiles[0]->tile)
			{
				fulu.type = Fulu::�Ӹ�;
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
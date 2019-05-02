#include "Table.h"
#include "Table.h"
#include "macro.h"
#include "Rule.h"
#include "GameResult.h"
#include "Agent.h"
#include "ScoreCounter.h"
#include <random>
using namespace std;

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
	//if (after_chipon == true) return actions;
	
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

static bool is食替(Player* player, BaseTile t) {
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

std::vector<SelfAction> Player::get_自摸(Table* table)
{
	// cout << "Warning:自摸 is not considered yet" << endl;

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
	// cout << "Warning:立直 is not considered yet" << endl;
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

static
vector<vector<Tile*>> get_Chi_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_顺子({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
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
			if (is_刻子({ hand[i]->tile, hand[i + j]->tile, tile->tile })) {
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

std::vector<ResponseAction> Player::get_荣和(Table* table, Tile * tile)
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

std::vector<ResponseAction> Player::get_Pon(Tile * tile)
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

std::vector<ResponseAction> Player::get_Kan(Tile * tile)
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

std::vector<ResponseAction> Player::get_抢暗杠(Tile * tile)
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

std::vector<ResponseAction> Player::get_抢杠(Tile * tile)
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

std::vector<SelfAction> Player::riichi_get_暗杠(Table * table)
{
	vector<SelfAction> actions;
	if (table->dora_spec == 5) {
		// 已经4杠，不准再杠
		return actions;
	}

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

void Player::move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile * tile)
{
	Fulu fulu;
	if (is_刻子({ tiles[0]->tile, tiles[1]->tile, tile->tile } )
		&& tiles.size()==2) {
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
			fulu.tiles = { tiles[0], tiles[1], tile};
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

void Player::remove_from_hand(Tile *tile)
{
	auto iter=
		remove_if(hand.begin(), hand.end(), [tile](Tile* t) {return tile == t; });
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
	auto iter = 
		remove_if(hand.begin(), hand.end(),
			[tile](Tile* t) {return t->tile == tile; });		
	hand.erase(iter, hand.end());
}

void Player::play_加杠(Tile * tile)
{
	门清 = false;
	for (auto &fulu : 副露s) {
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

void Player::move_from_hand_to_river(Tile * tile, int &number, bool remain, bool fromhand)
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

void Table::init_tiles()
{
	for (int i = 0; i < N_TILES; ++i) {
		tiles[i].tile = static_cast<BaseTile>(i % 34);
		//tiles[i].belongs = Belong::yama;
		tiles[i].red_dora = false;
	}
}

void Table::init_red_dora_3()
{
	tiles[4].red_dora = true;
	tiles[13].red_dora = true;
	tiles[22].red_dora = true;
}

void Table::shuffle_tiles()
{
	std::random_device rd;
	std::mt19937 g(rd());
	std::shuffle(tiles, tiles + N_TILES, g);
}

void Table::init_yama()
{
	vector<Tile*> empty;
	牌山.swap(empty);
	for (int i = 0; i < N_TILES; ++i) {
		牌山.push_back(&(tiles[i]));
	}

	dora_spec = 1;
	里宝牌指示牌 = { 牌山[5],牌山[7],牌山[9],牌山[11],牌山[13] };
	宝牌指示牌 = { 牌山[4],牌山[6],牌山[8],牌山[10],牌山[12] };

}

string Table::export_yama() {
	stringstream ss;
	for (int i = N_TILES - 1; i >= 0; --i) {
		ss << tiles[i].to_simple_string();
	}
	return ss.str();
}

// void Table::import_yama(std::string yama) {
// 	constexpr int LENGTH = N_TILES * sizeof(Tile);
// 	Base64 base64;
// 	auto decode = base64.Decode(yama, LENGTH);
// 	const char *s = decode.c_str();
// 	for (int i = 0; i < N_TILES; i++) {
// 		memcpy(tiles + i, s + i * sizeof(Tile), sizeof(Tile));
// 	}
// }

void Table::init_wind()
{
	players[庄家].wind = Wind::East;
	players[(庄家 + 1) % 4].wind = Wind::South;
	players[(庄家 + 2) % 4].wind = Wind::West;
	players[(庄家 + 3) % 4].wind = Wind::North;
}

void Table::test_show_yama_with_王牌()
{
	cout << "牌山:";
	if (牌山.size() < 14) {
		cout << "牌不足14张" << endl;
		return;
	}
	for (int i = 0; i < 14; ++i) {
		cout << 牌山[i]->to_string() << " ";
	}
	cout << "(王牌区)| ";
	for (int i = 14; i < 牌山.size(); ++i) {
		cout << 牌山[i]->to_string() << " ";
	}
	cout << endl;
	cout << "宝牌指示牌为:";
	for (int i = 0; i < dora_spec; ++i) {
		cout << 宝牌指示牌[i]->to_string() << " ";
	}
	cout << endl;
}

void Table::test_show_yama()
{
	cout << "牌山:";
	for (int i = 0; i < 牌山.size(); ++i) {
		cout << 牌山[i]->to_string() << " ";
	}
	cout << "共" << 牌山.size() << "张牌";
	cout << endl;
}

void Table::test_show_player_hand(int i_player)
{
	players[i_player].test_show_hand();
}

void Table::test_show_all_player_hand()
{
	for (int i = 0; i < 4; ++i) {
		cout << "Player" << i << " : "
			<< players[i].hand_to_string()
			<< endl;
	}
	cout << endl;
}

void Table::test_show_player_info(int i_player)
{
	cout << "Player" << i_player << " : "
		<< endl << players[i_player].to_string();
}

void Table::test_show_all_player_info()
{
	for (int i = 0; i < 4; ++i)
		test_show_player_info(i);
}

void Table::test_show_open_gamelog()
{
	cout << "Open GameLog:" << endl;
	cout << openGameLog.to_string();
}

void Table::test_show_full_gamelog()
{
	cout << "Full GameLog:" << endl;
	cout << fullGameLog.to_string();
}

Result Table::GameProcess(bool verbose, std::string yama)
{
	if (yama == "") {
		init_tiles();
		init_red_dora_3();
		shuffle_tiles();
		init_yama();

		// 将牌山导出为字符串
		// VERBOSE{
		// 	cout << "牌山代码:" << export_yama() << endl;
		// }
	}
	else {
		// import_yama(yama);
		throw runtime_error("Yama export is not available now.");
		init_yama();

		VERBOSE{
			cout << "导入牌山" << endl;
		}
	}

	// 每人发13张牌
	_deal(0, 13);
	_deal(1, 13);
	_deal(2, 13);
	_deal(3, 13);
	ALLSORT;

	// 初始化每人自风
	init_wind();

	turn = 庄家;

	// 测试Agent
	for (int i = 0; i < 4; ++i) {
		if (agents[i] == nullptr)
			throw runtime_error("Agent " + to_string(i) + " is not registered!");
	}

	// 游戏进程的主循环,循环的开始是某人有3n+2张牌
	while (1) {
		// 四风连打判定
		if (
			players[0].river.size() == 1 &&
			players[1].river.size() == 1 &&
			players[2].river.size() == 1 &&
			players[3].river.size() == 1 &&
			players[0].副露s.size() == 0 &&
			players[1].副露s.size() == 0 &&
			players[2].副露s.size() == 0 &&
			players[3].副露s.size() == 0 &&
			players[0].river[0].tile->tile == players[1].river[0].tile->tile &&
			players[1].river[0].tile->tile == players[2].river[0].tile->tile &&
			players[2].river[0].tile->tile == players[3].river[0].tile->tile)
		{
			return 四风连打流局结算(this);
		}

		if (
			players[0].riichi &&
			players[1].riichi &&
			players[2].riichi &&
			players[3].riichi) {
			return 四立直流局结算(this);
		}

		// 判定四杠散了
		if (get_remain_kan_tile() == 0) {
			int n_杠 = 0;
			for (int i = 0; i < 4; ++i) {
				if (any_of(players[i].副露s.begin(), players[i].副露s.end(),
					[](Fulu &f) {
					return f.type == Fulu::暗杠 ||
						f.type == Fulu::大明杠 ||
						f.type == Fulu::加杠;
				})) {
					// 统计一共有多少个人杠过
					n_杠++;
				}
			}
			if (n_杠 >= 1) {
				return 四杠流局结算(this);
			}
		}

		if (get_remain_tile() == 0)
			return 荒牌流局结算(this);

		// 全部自动整理手牌
		for (int i = 0; i < 4; ++i) {
			if (i != turn)
				players[i].sort_hand();
		}

		// 如果是after_minkan, 从岭上抓
		if (after_daiminkan()) {
			发岭上牌(turn);
			goto WAITING_PHASE;
		}

		// 如果是after_ankan, 从岭上抓
		if (after_ankan()) {
			发岭上牌(turn);
			goto WAITING_PHASE;
		}

		// 如果是after_chipon, 不抓
		if (after_chipon()) {
			goto WAITING_PHASE;
		}

		// 如果是after_chipon, 从岭上抓
		if (after_加杠()) {
			发岭上牌(turn);
			goto WAITING_PHASE;
		}

		// 剩下的情况正常抓
		发牌(turn);

	WAITING_PHASE:

		// 此时统计每个人的牌河振听状态
		// turn可以解除振听，即使player[turn]确实振听了，在下一次WAITING_PHASE之前，也会追加振听效果
		// 其他人按照规则追加振听效果
		for (int i = 0; i < 4; ++i) {
			if (i == turn) {
				players[turn].振听 = false;
				continue;
			}

			auto &hand = players[i].hand;
			auto tiles = get听牌(convert_tiles_to_base_tiles(hand));
			auto river = players[i].river.to_basetile();

			// 检查river和tiles是否有重合
			for (auto& tile : tiles) {
				if (find(river.begin(), river.end(), tile) != river.end()) {
					// 只要找到一个
					players[i].振听 = true;
					continue;
				}
			}
		}

		vector<SelfAction> actions;
		if (players[turn].is_riichi())
			actions = GetRiichiActions();
		else
			actions = GetValidActions();

		int selection;
		if (actions.size() == 1)
			selection = 0;
		else
			selection = agents[turn]->get_self_action(this, actions);

		// 让Agent进行选择
		auto selected_action = actions[selection];

		switch (selected_action.action) {
		case Action::九种九牌:
			return 九种九牌流局结算(this);
		case Action::自摸:
			return 自摸结算(this);
		case Action::出牌:
		case Action::立直:
		{
			// 决定不胡牌，则不具有一发状态
			players[turn].一发 = false;

			auto tile = selected_action.correspond_tiles[0];
			// 等待回复

			// 大部分情况都是手切, 除了上一步动作为 出牌 加杠 暗杠
			// 并且判定抉择弃牌是不是最后一张牌

			bool FROM_手切摸切 = FROM_手切;
			if (last_action == Action::出牌 || last_action == Action::加杠 || last_action == Action::暗杠) {
				// tile是不是最后一张
				if (tile == players[turn].hand.back())
					FROM_手切摸切 = FROM_摸切;
			}

			vector<ResponseAction> actions(4);
			Action final_action = Action::pass;
			for (int i = 0; i < 4; ++i) {
				if (i == turn) {
					actions[i].action = Action::pass;
					continue;
				}
				// 对于所有其他人
				bool is下家 = false;
				if (i == (turn + 1) % 4)
					is下家 = true;
				auto response = GetValidResponse(i, tile, is下家);

				if (response.size() != 1) {
					int selected_response =
						agents[i]->get_response_action(this, selected_action, tile, response);
					actions[i] = response[selected_response];

					// 判断立直振听和同巡振听：如果选项中有荣和，但是没有荣和
					// 则1. 立直以后都不能荣和 2. 没有立直，进入同巡振听状态
					if (any_of(response.begin(), response.end(), [](ResponseAction &ra) {
						return ra.action == Action::荣和;
					}) && actions[i].action != Action::荣和) {
						if (players[i].is_riichi()) {
							players[i].立直振听 = true;
						}
						else {
							players[i].振听 = true;
						}
					}

				}
				else
					actions[i].action = Action::pass;

				// 从actions中获得优先级
				if (actions[i].action > final_action)
					final_action = actions[i].action;
			}

			std::vector<int> response_player;
			for (int i = 0; i < 4; ++i) {
				if (actions[i].action == final_action) {
					response_player.push_back(i);
				}
			}
			int response = response_player[0];
			// 根据最终的final_action来进行判断
			// response_player里面保存了所有最终action和final_action相同的玩家
			// 只有在pass和荣和的时候才会出现这种情况
			// 其他情况用response来代替

			switch (final_action) {
			case Action::pass:

				// 立直成功
				if (selected_action.action == Action::立直) {
					if (players[turn].first_round) {
						players[turn].double_riichi = true;
					}
					players[turn].riichi = true;
					n立直棒++;
					players[turn].score -= 1000;
					players[turn].一发 = true;
				}

				// 杠，打出牌之后且其他人pass
				if (after_杠()) { dora_spec++; }

				// 什么都不做。将action对应的牌从手牌移动到牌河里面	

				players[turn].move_from_hand_to_river_really(tile, river_counter, FROM_手切摸切);


				// 消除第一巡
				players[turn].first_round = false;

				last_action = Action::出牌;
				next_turn();
				continue;
			case Action::吃:
			case Action::碰:
			case Action::杠:

				if (selected_action.action == Action::立直) {
					// 立直成功
					if (players[turn].first_round) {
						players[turn].double_riichi = true;
					}
					players[turn].riichi = true;
					n立直棒++;
					players[turn].score -= 1000;
					// 立直即鸣牌，一定没有一发
				}

				players[turn].remove_from_hand(tile);
				players[turn].move_from_hand_to_river_log_only(tile, river_counter, FROM_手切摸切);

				players[response].门清 = false;
				players[response].move_from_hand_to_fulu(
					actions[response].correspond_tiles, tile);
				turn = response;

				// 这是鸣牌，消除所有人第一巡和一发
				for (int i = 0; i < 4; ++i) {
					players[i].first_round = false;
					players[i].一发 = false;
				}

				// 明杠，打出牌之后且其他人吃碰
				if (after_杠()) { dora_spec++; }
				last_action = final_action;
				continue;

			case Action::荣和:
				return 荣和结算(this, selected_action.correspond_tiles[0], response_player);
			default:
				throw runtime_error("Invalid Selection.");
			}
		}
		case Action::暗杠: {
			auto tile = selected_action.correspond_tiles[0];

			// 暗杠的情况，第一巡也消除了
			players[turn].first_round = false;
			// 等待回复

			vector<ResponseAction> actions(4);
			Action final_action = Action::pass;
			for (int i = 0; i < 4; ++i) {
				if (i == turn) {
					actions[i].action = Action::pass;
					continue;
				}

				auto response = Get抢暗杠(i, tile);
				if (response.size() != 1) {
					int selected_response =
						agents[i]->get_response_action(this, selected_action, tile, response);
					actions[i] = response[selected_response];
				}
				else
					actions[i].action = Action::pass;

				// 从actions中获得优先级
				if (actions[i].action == Action::抢暗杠)
					final_action = actions[i].action;
			}

			std::vector<int> response_player;
			for (int i = 0; i < 4; ++i) {
				if (actions[i].action == final_action) {
					response_player.push_back(i);
				}
			}
			if (response_player.size() != 0 && final_action == Action::抢暗杠) {
				// 有人抢杠则进行结算
				return 抢暗杠结算(this, tile, response_player);
			}
			players[turn].play_暗杠(selected_action.correspond_tiles[0]->tile);
			last_action = Action::暗杠;
			// 立即翻宝牌指示牌
			dora_spec++;

			continue;
		}
		case Action::加杠: {
			auto tile = selected_action.correspond_tiles[0];
			// 等待回复

			vector<ResponseAction> actions(4);
			Action final_action = Action::pass;
			for (int i = 0; i < 4; ++i) {
				if (i == turn) {
					actions[i].action = Action::pass;
					continue;
				}

				auto response = Get抢杠(i, tile);
				if (response.size() != 1) {
					int selected_response =
						agents[i]->get_response_action(this, selected_action, tile, response);
					actions[i] = response[selected_response];
				}
				else
					actions[i].action = Action::pass;

				// 从actions中获得优先级
				if (actions[i].action == Action::抢杠)
					final_action = actions[i].action;
			}

			std::vector<int> response_player;
			for (int i = 0; i < 4; ++i) {
				if (actions[i].action == final_action) {
					response_player.push_back(i);
				}
			}

			if (response_player.size() != 0) {
				// 有人抢杠则进行结算，除非加杠宣告成功，否则一发状态仍然存在
				return 抢杠结算(this, tile, response_player);
			}		

			players[turn].play_加杠(selected_action.correspond_tiles[0]);
			last_action = Action::加杠;
			
			// 这是鸣牌，消除所有人第一巡和一发
			for (int i = 0; i < 4; ++i) {
				players[i].first_round = false;
				players[i].一发 = false;
			}

			continue;
		}

		default:
			throw runtime_error("Selection invalid!");
		}
	}
}

void Table::_deal(int i_player)
{		
	players[i_player].hand.push_back(牌山.back());
	牌山.pop_back();
}

void Table::_deal(int i_player, int n_tiles)
{
	for (int i = 0; i < n_tiles; ++i) {
		_deal(i_player);
	}
}

void Table::发牌(int i_player)
{
	_deal(i_player);
	//openGameLog.log摸牌(i_player, nullptr);
	//fullGameLog.log摸牌(i_player, player[i_player].hand.back());
}

void Table::发岭上牌(int i_player)
{
	_deal(i_player);
	//openGameLog.log摸牌(i_player, nullptr);
	//fullGameLog.log摸牌(i_player, player[i_player].hand.back());
}

std::string Table::to_string(int option) const
{
	stringstream ss;
	if (option & ToStringOption::YAMA) {
		ss << "牌山:";
		if (牌山.size() < 14) {
			ss << "牌不足14张" << endl;
			return ss.str();
		}
		for (int i = 0; i < 14; ++i) {
			ss << 牌山[i]->to_string() << " ";
		}
		ss << "(王牌区)| ";
		for (int i = 14; i < 牌山.size(); ++i) {
			ss << 牌山[i]->to_string() << " ";
		}
		ss << endl;
	}
	if (option & ToStringOption::DORA) {
		ss << "宝牌指示牌为:";
		for (int i = 0; i < dora_spec; ++i) {
			ss << 宝牌指示牌[i]->to_string() << " ";
		}
		ss << endl;
	}

	if (option & ToStringOption::REMAIN_TILE) {
		ss << "余" << get_remain_tile() << "张牌" << endl;
	}
	if (option & ToStringOption::PLAYER) {
		for (int i = 0; i < 4; ++i)
		ss << "Player" << i << " : "
			<< endl << players[i].to_string();
		ss << endl;
	}
	if (option & ToStringOption::亲家) {
		ss << "亲家: Player " << 庄家 << endl;
	}
	if (option & ToStringOption::N_本场) {
		ss << n本场 << "本场";
	}
	if (option & ToStringOption::N_立直棒) {
		ss << n本场 << "立直棒";
	}
	ss << endl;
	return ss.str();
}

Table::Table(int 庄家, Agent * p1, Agent * p2, Agent * p3, Agent * p4)
	: dora_spec(1), 庄家(庄家)
{
	agents[0] = p1;
	agents[1] = p2;
	agents[2] = p3;
	agents[3] = p4;
	for (int i = 0; i < 4; ++i) players[i].score = 25000;
}

Table::Table(int 庄家,
	Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4])
	: dora_spec(1), 庄家(庄家)
{
	agents[0] = p1;
	agents[1] = p2;
	agents[2] = p3;
	agents[3] = p4;
	for (int i = 0; i < 4; ++i) players[i].score = scores[i];
}

std::vector<SelfAction> Table::GetValidActions()
{
	vector<SelfAction> actions;
	auto& the_player = players[turn];
	if (!after_chipon()) {
		merge_into(actions, the_player.get_暗杠());
		merge_into(actions, the_player.get_加杠());
	}
	
	merge_into(actions, the_player.get_打牌(after_chipon()));
	merge_into(actions, the_player.get_九种九牌());
	merge_into(actions, the_player.get_自摸(this));

	if (players[turn].score >= 1000 &&
		get_remain_tile() > 4)
		// 有1000点才能立直，否则不行
		// 牌河有4张以下牌，则不能立直
		merge_into(actions, the_player.get_立直());

	// 过滤器

	// 如果已经有了4个杠子，禁止接下来的杠
	if (get_remain_kan_tile() == 0) {
		auto iter = remove_if(actions.begin(), actions.end(),
			[](SelfAction& sa) {
			if (sa.action == Action::暗杠) return true;
			if (sa.action == Action::加杠) return true;
			return false;
		});
		actions.erase(iter, actions.end());
	}

	// 计算役，如果无役，则禁止自摸
	auto result = yaku_counter(this, turn, nullptr, false, false, players[turn].wind, 场风);
	if (!can_agari(result.yakus)) {
		auto iter = remove_if(actions.begin(), actions.end(),
			[](SelfAction& sa) {
			if (sa.action == Action::自摸) return true;
			return false;
		});
		actions.erase(iter,actions.end());
	}

	return actions;
}

std::vector<SelfAction> Table::GetRiichiActions()
{
	vector<SelfAction> actions;
	auto& the_player = players[turn];
	merge_into(actions, the_player.riichi_get_暗杠(this));
	merge_into(actions, the_player.riichi_get_打牌());
	merge_into(actions, the_player.get_自摸(this));

	return actions;
}

std::vector<ResponseAction> Table::GetValidResponse(
	int i, Tile* tile, bool is下家)
{
	std::vector<ResponseAction> actions;
	
	// first: pass action
	ResponseAction action_pass;
	action_pass.action = Action::pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];

	merge_into(actions, the_player.get_荣和(this, tile));
	if (!the_player.is_riichi()) {
		merge_into(actions, the_player.get_Pon(tile));
		merge_into(actions, the_player.get_Kan(tile));

		if (is下家) {
			merge_into(actions, the_player.get_Chi(tile));
		}
	}

	// 过滤器
	auto &response = actions;

	// 如果吃了之后，手上只有食替牌，那么就移除这个吃
	{
		auto iter = remove_if(response.begin(), response.end(),
			[&the_player](ResponseAction &ra) {
			if (ra.action != Action::吃) return false;
			auto tiles = ra.correspond_tiles;
			// 计算食替牌
			vector<BaseTile> 食替牌;

			if (tiles[1] > tiles[0]) {
				if (tiles[0]->tile != _1m && tiles[0]->tile != _1s && tiles[0]->tile != _1p) {
					食替牌.push_back(BaseTile(tiles[0]->tile - 1));
				}
				if (tiles[1]->tile != _9m && tiles[1]->tile != _9s && tiles[1]->tile != _9p) {
					食替牌.push_back(BaseTile(tiles[1]->tile + 1));
				}
			}
			else if (tiles[1] < tiles[0]) {
				if (tiles[1]->tile != _1m && tiles[1]->tile != _1s && tiles[1]->tile != _1p) {
					食替牌.push_back(BaseTile(tiles[1]->tile - 1));
				}
				if (tiles[0]->tile != _9m && tiles[0]->tile != _9s && tiles[0]->tile != _9p) {
					食替牌.push_back(BaseTile(tiles[0]->tile + 1));
				}
			}
			else throw runtime_error("Error in response action: chi.");

			// 去掉这些吃牌
			auto copyhand = the_player.hand;
			copyhand.erase(remove_if(copyhand.begin(), copyhand.end(), [&tiles](Tile* tile) {
				return is_in(tiles, tile);
			}));

			// 全部是食替牌
			return all_of(copyhand.begin(), copyhand.end(), [&食替牌](Tile* tile) {
				return is_in(食替牌, tile->tile);
			});
		});
		response.erase(iter, response.end());
	}

	// 如果是海底状态，删除掉除了荣和和pass之外的所有情况
	if (get_remain_tile() == 0) {
		auto iter =
			remove_if(response.begin(), response.end(),
				[](ResponseAction& ra) {
			if (ra.action == Action::pass) return false;
			if (ra.action == Action::荣和) return false;
			return true;
		});
		response.erase(iter, response.end());
	}

	// 如果已经有了4个杠子，禁止接下来的杠
	if (get_remain_kan_tile() == 0) {
		auto iter = remove_if(response.begin(), response.end(),
			[](ResponseAction& ra) {
			if (ra.action == Action::杠) return true;
			return false;
		});
		actions.erase(iter, actions.end());
	}

	// 如果是振听状态，则不能荣和
	if (the_player.is振听() == true) {
		auto iter = remove_if(response.begin(), response.end(),
			[](ResponseAction& ra) {
			if (ra.action == Action::荣和) return true;
			return false;
		});
		actions.erase(iter, actions.end());
		// 玩家继续处于振听状态
	}

	// 如果无役，则不能荣和
	if (!can_agari(yaku_counter(this, i, tile, false, false, players[i].wind, 场风).yakus)) {
		auto iter = remove_if(response.begin(), response.end(),
			[](ResponseAction& ra) {
			if (ra.action == Action::荣和) return true;
			return false;
		});
		actions.erase(iter, actions.end());

		// 不仅如此，还要追加振听状态
		the_player.振听 = true;
	}

	return actions;
}

std::vector<ResponseAction> Table::Get抢暗杠(int i, Tile * tile)
{
	std::vector<ResponseAction> actions;

	// first: pass action
	ResponseAction action_pass;
	action_pass.action = Action::pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];
	merge_into(actions, the_player.get_抢暗杠(tile));

	return actions;
}

std::vector<ResponseAction> Table::Get抢杠(int i, Tile * tile)
{
	std::vector<ResponseAction> actions;

	// first: pass action
	ResponseAction action_pass;
	action_pass.action = Action::pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];
	merge_into(actions, the_player.get_抢杠(tile));

	return actions;
}

void Table::_action_phase_mt(int selection)
{
	// Brief: 进行选择，根据选择生成接下来的玩家的Responses或者终局
	lock.lock();
	selected_action = self_action[selection];
	switch (selected_action.action) {
	case Action::九种九牌:
		result = 九种九牌流局结算(this);
		phase_mt = GAME_OVER_MT;
		return;
	case Action::自摸:
		result = 自摸结算(this);
		phase_mt = GAME_OVER_MT;
		return;
	case Action::出牌:
	case Action::立直:
	{
		// 决定不胡牌，则不具有一发状态
		players[turn].一发 = false;

		tile = selected_action.correspond_tiles[0];
		// 等待回复

		// 大部分情况都是手切, 除了上一步动作为 出牌 加杠 暗杠
		// 并且判定抉择弃牌是不是最后一张牌

		FROM_手切摸切 = FROM_手切;
		if (last_action == Action::出牌 || last_action == Action::加杠 || last_action == Action::暗杠) {
			// tile是不是最后一张
			if (tile == players[turn].hand.back())
				FROM_手切摸切 = FROM_摸切;
		}
		phase_mt = RESPONSE_MT;
		for (int i = 0; i < 4; ++i) {
			if (i == turn) {
				continue;
			}
			else {
				// 对于所有其他人
				bool is下家 = false;
				if (i == (turn + 1) % 4)
					is下家 = true;
				response_action_mt.insert({ i, GetValidResponse(0, tile, is下家) });
			}
		}
		return;
	}
	case Action::暗杠:
	{
		tile = selected_action.correspond_tiles[0];

		// 暗杠的情况，第一巡也消除了
		players[turn].first_round = false;
		// 等待回复
		phase_mt = RESPONSE_MT;
		for (int i = 0; i < 4; ++i) {
			if (i == turn) {
				continue;
			}
			else {
				response_action_mt.insert({ i, Get抢暗杠(0, tile) });
			}
		}

		return;
	}
	case Action::加杠:
	{
		tile = selected_action.correspond_tiles[0];

		// 暗杠的情况，第一巡也消除了
		players[turn].first_round = false;
		// 等待回复
		phase_mt = RESPONSE_MT;
		for (int i = 0; i < 4; ++i) {
			if (i == turn) {
				continue;
			}
			else {
				response_action_mt.insert({ i, Get抢杠(0, tile) });
			}
		}
		return;
	}
	default:
		throw runtime_error("Unknown SelfAction");
	}

	lock.unlock();
}

void Table::_final_response_mt()
{
	lock.lock();
	actions.push_back(response_action[selection]);
	// 从actions中获得优先级
	if (response_action[selection].action > final_action)
		final_action = response_action[selection].action;

	// 选择优先级，并且进行response结算
	std::vector<int> response_player;
	for (int i = 0; i < 4; ++i) {
		if (actions[i].action == final_action) {
			response_player.push_back(i);
		}
	}
	int response = response_player[0];
	// 根据最终的final_action来进行判断
	// response_player里面保存了所有最终action和final_action相同的玩家
	// 只有在pass和荣和的时候才会出现这种情况
	// 其他情况用response来代替

	switch (final_action) {
	case Action::pass:
	{
		if (selected_action.action == Action::暗杠) {
			players[turn].play_暗杠(selected_action.correspond_tiles[0]->tile);
			last_action = Action::暗杠;
			// 立即翻宝牌指示牌
			dora_spec++;
			// 这是暗杠，消除所有人第一巡和一发
			for (int i = 0; i < 4; ++i) {
				players[i].first_round = false;
				players[i].一发 = false;
			}
		}
		else if (selected_action.action == Action::加杠) {

			players[turn].play_加杠(selected_action.correspond_tiles[0]);
			last_action = Action::加杠;

			// 这是鸣牌，消除所有人第一巡和一发
			for (int i = 0; i < 4; ++i) {
				players[i].first_round = false;
				players[i].一发 = false;
			}
		}
		else {
			// 立直成功
			if (selected_action.action == Action::立直) {
				if (players[turn].first_round) {
					players[turn].double_riichi = true;
				}
				players[turn].riichi = true;
				n立直棒++;
				players[turn].score -= 1000;
				players[turn].一发 = true;
			}

			// 杠，打出牌之后且其他人pass
			if (after_杠()) { dora_spec++; }

			// 什么都不做。将action对应的牌从手牌移动到牌河里面	

			players[turn].move_from_hand_to_river_really(tile, river_counter, FROM_手切摸切);

			// 消除第一巡
			players[turn].first_round = false;

			last_action = Action::出牌;
			next_turn();
		}
		break;
	}
	case Action::吃:
	case Action::碰:
	case Action::杠:
	{
		if (selected_action.action == Action::立直) {
			// 立直成功
			if (players[turn].first_round) {
				players[turn].double_riichi = true;
			}
			players[turn].riichi = true;
			n立直棒++;
			players[turn].score -= 1000;
			// 立直即鸣牌，一定没有一发
		}

		players[turn].remove_from_hand(tile);
		players[turn].move_from_hand_to_river_log_only(tile, river_counter, FROM_手切摸切);

		players[response].门清 = false;
		players[response].move_from_hand_to_fulu(
			actions[response].correspond_tiles, tile);
		turn = response;

		// 这是鸣牌，消除所有人第一巡和一发
		for (int i = 0; i < 4; ++i) {
			players[i].first_round = false;
			players[i].一发 = false;
		}

		// 明杠，打出牌之后且其他人吃碰
		if (after_杠()) { dora_spec++; }
		last_action = final_action;
		break;
	}
	case Action::荣和:
	case Action::抢杠:
	case Action::抢暗杠:
		result = 荣和结算(this, selected_action.correspond_tiles[0], response_player);
		phase = GAME_OVER;
		return;
	default:
		throw runtime_error("Invalid Selection.");
	}
	
	// 回到循环的最开始
	_from_beginning_mt();

	lock.unlock();
	return;
}

void Table::_from_beginning_mt()
{// 四风连打判定
	if (
		players[0].river.size() == 1 &&
		players[1].river.size() == 1 &&
		players[2].river.size() == 1 &&
		players[3].river.size() == 1 &&
		players[0].副露s.size() == 0 &&
		players[1].副露s.size() == 0 &&
		players[2].副露s.size() == 0 &&
		players[3].副露s.size() == 0 &&
		players[0].river[0].tile->tile == players[1].river[0].tile->tile &&
		players[1].river[0].tile->tile == players[2].river[0].tile->tile &&
		players[2].river[0].tile->tile == players[3].river[0].tile->tile)
	{
		result = 四风连打流局结算(this);
		phase = GAME_OVER;
		return;
	}

	if (
		players[0].riichi &&
		players[1].riichi &&
		players[2].riichi &&
		players[3].riichi) {
		result = 四立直流局结算(this);
		phase = GAME_OVER;
		return;
	}

	// 判定四杠散了
	if (get_remain_kan_tile() == 0) {
		int n_杠 = 0;
		for (int i = 0; i < 4; ++i) {
			if (any_of(players[i].副露s.begin(), players[i].副露s.end(),
				[](Fulu &f) {
				return f.type == Fulu::暗杠 ||
					f.type == Fulu::大明杠 ||
					f.type == Fulu::加杠;
			})) {
				// 统计一共有多少个人杠过
				n_杠++;
			}
		}
		if (n_杠 >= 1) {
			result = 四杠流局结算(this);
			phase = GAME_OVER;
			return;
		}
	}

	if (get_remain_tile() == 0) {
		result = 荒牌流局结算(this);
		phase = GAME_OVER;
		return;
	}

	// 全部自动整理手牌
	for (int i = 0; i < 4; ++i) {
		if (i != turn)
			players[i].sort_hand();
	}

	// 如果是after_minkan, 从岭上抓
	if (after_daiminkan()) {
		发岭上牌(turn);
		goto WAITING_PHASE;
	}

	// 如果是after_ankan, 从岭上抓
	if (after_ankan()) {
		发岭上牌(turn);
		goto WAITING_PHASE;
	}

	// 如果是after_chipon, 不抓
	if (after_chipon()) {
		goto WAITING_PHASE;
	}

	// 如果是after_chipon, 从岭上抓
	if (after_加杠()) {
		发岭上牌(turn);
		goto WAITING_PHASE;
	}

	// 剩下的情况正常抓
	发牌(turn);

WAITING_PHASE:

	// 此时统计每个人的牌河振听状态
	// turn可以解除振听，即使player[turn]确实振听了，在下一次WAITING_PHASE之前，也会追加振听效果
	// 其他人按照规则追加振听效果
	for (int i = 0; i < 4; ++i) {
		if (i == turn) {
			players[turn].振听 = false;
			continue;
		}

		auto &hand = players[i].hand;
		auto tiles = get听牌(convert_tiles_to_base_tiles(hand));
		auto river = players[i].river.to_basetile();

		// 检查river和tiles是否有重合
		for (auto& tile : tiles) {
			if (find(river.begin(), river.end(), tile) != river.end()) {
				// 只要找到一个
				players[i].振听 = true;
				continue;
			}
		}
	}

	vector<SelfAction> actions;
	if (players[turn].is_riichi())
		self_action = GetRiichiActions();
	else
		self_action = GetValidActions();

	phase_mt = (_Phase_MultiThread_)turn;
}

void Table::_from_beginning()
{
	// 四风连打判定
	if (
		players[0].river.size() == 1 &&
		players[1].river.size() == 1 &&
		players[2].river.size() == 1 &&
		players[3].river.size() == 1 &&
		players[0].副露s.size() == 0 &&
		players[1].副露s.size() == 0 &&
		players[2].副露s.size() == 0 &&
		players[3].副露s.size() == 0 &&
		players[0].river[0].tile->tile == players[1].river[0].tile->tile &&
		players[1].river[0].tile->tile == players[2].river[0].tile->tile &&
		players[2].river[0].tile->tile == players[3].river[0].tile->tile)
	{
		result = 四风连打流局结算(this);
		phase = GAME_OVER;
		return;
	}

	if (
		players[0].riichi &&
		players[1].riichi &&
		players[2].riichi &&
		players[3].riichi) {
		result = 四立直流局结算(this);
		phase = GAME_OVER;
		return;
	}

	// 判定四杠散了
	if (get_remain_kan_tile() == 0) {
		int n_杠 = 0;
		for (int i = 0; i < 4; ++i) {
			if (any_of(players[i].副露s.begin(), players[i].副露s.end(),
				[](Fulu &f) {
				return f.type == Fulu::暗杠 ||
					f.type == Fulu::大明杠 ||
					f.type == Fulu::加杠;
			})) {
				// 统计一共有多少个人杠过
				n_杠++;
			}
		}
		if (n_杠 >= 1) {
			result = 四杠流局结算(this);
			phase = GAME_OVER;
			return;
		}
	}

	if (get_remain_tile() == 0) {
		result = 荒牌流局结算(this);
		phase = GAME_OVER;
		return;
	}

	// 全部自动整理手牌
	for (int i = 0; i < 4; ++i) {
		if (i != turn)
			players[i].sort_hand();
	}

	// 如果是after_minkan, 从岭上抓
	if (after_daiminkan()) {
		发岭上牌(turn);
		goto WAITING_PHASE;
	}

	// 如果是after_ankan, 从岭上抓
	if (after_ankan()) {
		发岭上牌(turn);
		goto WAITING_PHASE;
	}

	// 如果是after_chipon, 不抓
	if (after_chipon()) {
		goto WAITING_PHASE;
	}

	// 如果是after_chipon, 从岭上抓
	if (after_加杠()) {
		发岭上牌(turn);
		goto WAITING_PHASE;
	}

	// 剩下的情况正常抓
	发牌(turn);

WAITING_PHASE:

	// 此时统计每个人的牌河振听状态
	// turn可以解除振听，即使player[turn]确实振听了，在下一次WAITING_PHASE之前，也会追加振听效果
	// 其他人按照规则追加振听效果
	for (int i = 0; i < 4; ++i) {
		if (i == turn) {
			players[turn].振听 = false;
			continue;
		}

		auto &hand = players[i].hand;
		auto tiles = get听牌(convert_tiles_to_base_tiles(hand));
		auto river = players[i].river.to_basetile();

		// 检查river和tiles是否有重合
		for (auto& tile : tiles) {
			if (find(river.begin(), river.end(), tile) != river.end()) {
				// 只要找到一个
				players[i].振听 = true;
				continue;
			}
		}
	}

	vector<SelfAction> actions;
	if (players[turn].is_riichi())
		self_action = GetRiichiActions();
	else
		self_action = GetValidActions();

	phase = (_Phase_)turn;
}

void Table::game_init_with_metadata(std::unordered_map<std::string, std::string> metadata)
{
	// yama : "1z1z1z..."
	using namespace std;

	if (metadata.find("yama") != metadata.end()) {
		auto val = metadata["yama"];
		if (val.size() != N_TILES * 2) throw runtime_error("Yama string incomplete.");
		for (int i = 0; i < N_TILES * 2; i += 2) {
			bool red_dora;
			// 逆序插入
			tiles[N_TILES - 1 - i / 2].tile = char2_to_basetile(val[i], val[i + 1], red_dora);
			tiles[N_TILES - 1 - i / 2].red_dora = red_dora;
		}
	}
	else {
		init_tiles();
		init_red_dora_3();
		shuffle_tiles();
	}

	if (metadata.find("oya") != metadata.end()) {
		auto val = metadata["oya"];
		if (val == "0") {
			庄家 = 0;
		}
		if (val == "1") {
			庄家 = 1;
		}
		if (val == "2") {
			庄家 = 2;
		}
		if (val == "3") {
			庄家 = 3;
		}
		else throw runtime_error("Cannot Read Option: oya");
	}
	else {
		庄家 = 0;
	}

	if (metadata.find("wind") != metadata.end()) {
		auto val = metadata["wind"];
		if (val == "east") {
			场风 = Wind::East;
		}
		if (val == "west") {
			场风 = Wind::West;
		}
		if (val == "south") {
			场风 = Wind::South;
		}
		if (val == "north") {
			场风 = Wind::North;
		}
		else throw runtime_error("Cannot Read Option: wind");
	}
	else {
		场风 = Wind::East;
	}

	init_yama();

	// 每人发13张牌
	if (metadata.find("deal") != metadata.end()) {
		auto val = metadata["deal"];
		if (val == "from_oya") {
			for (int i = 庄家; i < 庄家 + 4; ++i) {
				_deal(i % 4, 13);
			}
		}
		if (val == "from_0") {
			_deal(0, 13);
			_deal(1, 13);
			_deal(2, 13);
			_deal(3, 13);
		}
		else throw runtime_error("Cannot Read Option: deal");
	}
	else {
		_deal(0, 13);
		_deal(1, 13);
		_deal(2, 13);
		_deal(3, 13);
	}
	ALLSORT;

	// 初始化每人自风
	init_wind();
	turn = 庄家;
	_from_beginning();
}

void Table::make_selection(int selection)
{
	// 这个地方控制了游戏流转
	
	// 分为两种情况，如果是ACTION阶段
	switch (phase) {
	case P1_ACTION:
	case P2_ACTION:
	case P3_ACTION:
	case P4_ACTION: {
		selected_action = self_action[selection];
		switch (selected_action.action) {
		case Action::九种九牌:
			result = 九种九牌流局结算(this);
			phase = GAME_OVER;
			return;
		case Action::自摸:
			result = 自摸结算(this);
			phase = GAME_OVER;
			return;
		case Action::出牌:
		case Action::立直:
		{
			// 决定不胡牌，则不具有一发状态
			players[turn].一发 = false;

			tile = selected_action.correspond_tiles[0];
			// 等待回复

			// 大部分情况都是手切, 除了上一步动作为 出牌 加杠 暗杠
			// 并且判定抉择弃牌是不是最后一张牌

			FROM_手切摸切 = FROM_手切;
			if (last_action == Action::出牌 || last_action == Action::加杠 || last_action == Action::暗杠) {
				// tile是不是最后一张
				if (tile == players[turn].hand.back())
					FROM_手切摸切 = FROM_摸切;
			}
			phase = P1_RESPONSE;
			if (0 == turn) {
				ResponseAction ra;
				ra.action = Action::pass;
				response_action = { ra };
			}
			else {
				// 对于所有其他人
				bool is下家 = false;
				if (0 == (turn + 1) % 4)
					is下家 = true;
				response_action = GetValidResponse(0, tile, is下家);
			}			
			return;
		}
		case Action::暗杠:
		{	
			tile = selected_action.correspond_tiles[0];

			// 暗杠的情况，第一巡也消除了
			players[turn].first_round = false;
			// 等待回复
			phase = P1_抢暗杠RESPONSE;
			if (0 == turn) {
				ResponseAction ra;
				ra.action = Action::pass;
				response_action = { ra };
			}
			else {
				response_action = Get抢暗杠(0, tile);
			}

			return;
		}
		case Action::加杠:
		{
			tile = selected_action.correspond_tiles[0];

			// 暗杠的情况，第一巡也消除了
			players[turn].first_round = false;
			// 等待回复
			phase = P1_抢杠RESPONSE;
			if (0 == turn) {
				ResponseAction ra;
				ra.action = Action::pass;
				response_action = { ra };
			}
			else {
				response_action = Get抢杠(0, tile);
			}
			return;
		}
		}
	}

	case P1_RESPONSE:
		actions.resize(0);
		final_action = Action::pass;
	case P2_RESPONSE:
	case P3_RESPONSE: {
		// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase
		actions.push_back(response_action[selection]);
		// 从actions中获得优先级
		if (response_action[selection].action > final_action)
			final_action = response_action[selection].action;

		phase = _Phase_(phase + 1);
		int i = phase - P1_RESPONSE;
		if (i == turn) {
			ResponseAction ra;
			ra.action = Action::pass;
			response_action = { ra };
		}
		else {
			// 对于所有其他人
			bool is下家 = false;
			if (i == (turn + 1) % 4)
				is下家 = true;
			response_action = GetValidResponse(i, tile, is下家);
		}
		return;
	}
	case P4_RESPONSE: {
		// 做出选择		
		actions.push_back(response_action[selection]);
		// 从actions中获得优先级
		if (response_action[selection].action > final_action)
			final_action = response_action[selection].action;

		// 选择优先级，并且进行response结算
		std::vector<int> response_player;
		for (int i = 0; i < 4; ++i) {
			if (actions[i].action == final_action) {
				response_player.push_back(i);
			}
		}
		int response = response_player[0];
		// 根据最终的final_action来进行判断
		// response_player里面保存了所有最终action和final_action相同的玩家
		// 只有在pass和荣和的时候才会出现这种情况
		// 其他情况用response来代替

		switch (final_action) {
		case Action::pass:

			// 立直成功
			if (selected_action.action == Action::立直) {
				if (players[turn].first_round) {
					players[turn].double_riichi = true;
				}
				players[turn].riichi = true;
				n立直棒++;
				players[turn].score -= 1000;
				players[turn].一发 = true;
			}

			// 杠，打出牌之后且其他人pass
			if (after_杠()) { dora_spec++; }

			// 什么都不做。将action对应的牌从手牌移动到牌河里面	

			players[turn].move_from_hand_to_river_really(tile, river_counter, FROM_手切摸切);

			// 消除第一巡
			players[turn].first_round = false;

			last_action = Action::出牌;
			next_turn();

			phase = (_Phase_)turn;
			break;
		case Action::吃:
		case Action::碰:
		case Action::杠:

			if (selected_action.action == Action::立直) {
				// 立直成功
				if (players[turn].first_round) {
					players[turn].double_riichi = true;
				}
				players[turn].riichi = true;
				n立直棒++;
				players[turn].score -= 1000;
				// 立直即鸣牌，一定没有一发
			}

			players[turn].remove_from_hand(tile);
			players[turn].move_from_hand_to_river_log_only(tile, river_counter, FROM_手切摸切);

			players[response].门清 = false;
			players[response].move_from_hand_to_fulu(
				actions[response].correspond_tiles, tile);
			turn = response;

			// 这是鸣牌，消除所有人第一巡和一发
			for (int i = 0; i < 4; ++i) {
				players[i].first_round = false;
				players[i].一发 = false;
			}

			// 明杠，打出牌之后且其他人吃碰
			if (after_杠()) { dora_spec++; }
			last_action = final_action;
			phase = (_Phase_)turn;
			break;

		case Action::荣和:
			result = 荣和结算(this, selected_action.correspond_tiles[0], response_player);
			phase = GAME_OVER;
			return;
		default:
			throw runtime_error("Invalid Selection.");
		}

		// 回到循环的最开始
		_from_beginning();
		return;
	}
	
	case P1_抢杠RESPONSE:
		actions.resize(0);
		final_action = Action::pass;
	case P2_抢杠RESPONSE:
	case P3_抢杠RESPONSE: {
		// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase
		actions.push_back(response_action[selection]);
		// 从actions中获得优先级
		if (response_action[selection].action > final_action)
			final_action = response_action[selection].action;

		phase = _Phase_(phase + 1);
		int i = phase - P1_抢杠RESPONSE;
		if (i == turn) {
			ResponseAction ra;
			ra.action = Action::pass;
			response_action = { ra };
		}
		else {
			response_action = Get抢杠(i, tile);
		}
		return;
	}
	case P4_抢杠RESPONSE: {
		// 做出选择		
		actions.push_back(response_action[selection]);

		// 选择优先级，并且进行response结算
		std::vector<int> response_player;
		for (int i = 0; i < 4; ++i) {
			if (actions[i].action == Action::抢杠) {
				response_player.push_back(i);
			}
		}
		if (response_player.size() != 0) {
			// 有人抢杠则进行结算，除非加杠宣告成功，否则一发状态仍然存在
			result = 抢杠结算(this, tile, response_player);
			phase = GAME_OVER;
			return;
		}
		players[turn].play_加杠(selected_action.correspond_tiles[0]);
		last_action = Action::加杠;

		// 这是鸣牌，消除所有人第一巡和一发
		for (int i = 0; i < 4; ++i) {
			players[i].first_round = false;
			players[i].一发 = false;
		}
		_from_beginning();
		return;
	}

	case P1_抢暗杠RESPONSE:
		actions.resize(0);
		final_action = Action::pass;
	case P2_抢暗杠RESPONSE:
	case P3_抢暗杠RESPONSE: {
		// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase
		actions.push_back(response_action[selection]);
		// 从actions中获得优先级
		if (response_action[selection].action > final_action)
			final_action = response_action[selection].action;

		phase = _Phase_(phase + 1);
		int i = phase - P1_抢暗杠RESPONSE;
		if (i == turn) {
			ResponseAction ra;
			ra.action = Action::pass;
			response_action = { ra };
		}
		else {
			response_action = Get抢暗杠(i, tile);
		}
		return;
	}
	case P4_抢暗杠RESPONSE: {
		// 做出选择		
		actions.push_back(response_action[selection]);

		// 选择优先级，并且进行response结算
		std::vector<int> response_player;
		for (int i = 0; i < 4; ++i) {
			if (actions[i].action == Action::抢暗杠) {
				response_player.push_back(i);
			}
		}
		if (response_player.size() != 0) {
			// 有人抢暗杠则进行结算
			result = 抢暗杠结算(this, tile, response_player);
			phase = GAME_OVER;
			return;
		}
		players[turn].play_暗杠(selected_action.correspond_tiles[0]->tile);
		last_action = Action::暗杠;
		// 立即翻宝牌指示牌
		dora_spec++;

		// 这是暗杠，消除所有人第一巡和一发
		for (int i = 0; i < 4; ++i) {
			players[i].first_round = false;
			players[i].一发 = false;
		}
		_from_beginning();
		return;
	}

	}
}

int Table::get_phase_mt() const
{
	return phase_mt;
}

bool Table::make_selection_mt(int player, int selection)
{
	// 如果不轮到这个玩家，做出的选择无效
	if (should_i_make_selection_mt(player)) {
		// 这里也去除了GAME_OVER_MT的情况
		return false;
	}
	else {
		if (phase_mt == RESPONSE_MT) {
			// 回复阶段
			lock.lock();
			decided_response_action_mt.insert({ player,
				response_action_mt[player][selection] });
			lock.unlock(); 

			if (decided_response_action_mt.size() == 3) {
				// 已经有3个玩家做出回复
				_final_response_mt();
			}
		}
		else {
			_action_phase_mt(selection);
		}
		
		// 选择有效
		return true;
	}
}

const vector<SelfAction> Table::get_self_actions_mt(int player) {
	// if not your turn, or you have already made selection, return nothing
	if (!should_i_make_selection_mt(player)) {
		return vector<SelfAction>();
	}
	else {
		return self_action;
	}
}

const std::vector<ResponseAction> Table::get_response_actions_mt(int player)
{
	if (!should_i_make_selection_mt(player)) {
		return vector<ResponseAction>();
	}
	else {
		return response_action_mt[player];
	}
}

bool Table::should_i_make_selection_mt(int player) {

	// 等待其他玩家释放锁，因为有可能进入了selection状态
	lock.lock();
	lock.unlock();

	switch (phase_mt) {
	case P1_ACTION_MT:
	case P2_ACTION_MT:
	case P3_ACTION_MT:
	case P4_ACTION_MT:
		if (phase_mt == player) return true;
		else return false;

	case RESPONSE_MT:
		if (turn == player) return false;
		else {
			if (decided_response_action_mt.find(player)
				== decided_response_action_mt.end()) {
				return true;
			}
			return false;
		}
	case GAME_OVER_MT:
		return false;
	default:
		throw runtime_error("Error in _phase_mt");
	}
}

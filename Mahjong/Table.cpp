#include "Table.h"
#include "macro.h"
#include "Rule.h"
#include "GameResult.h"
#include "Agent.h"

#include <random>
using namespace std;

#pragma region PLAYER
Player::Player()
	:riichi(false), score(INIT_SCORE)
{ }

std::string Player::hand_to_string()
{
	stringstream ss;

	for (auto hand_tile : hand) {
		ss << hand_tile->to_string() << " ";
	}
	return ss.str();
}

std::string Player::river_to_string()
{
	stringstream ss;

	for (auto tile : river) {
		ss << tile->to_string() << " ";
	}
	return ss.str();
}

std::string Player::to_string()
{
	stringstream ss;
	ss << "自风" << wind_to_string(wind) << endl;
	ss << "手牌:" << hand_to_string();
	ss << endl;
	ss << "牌河:" << river_to_string();
	ss << endl;
	if (riichi) {
		ss << "立直状态" << endl;
	}
	else {
		ss << "未立直状态" << endl;
	}
	return ss.str();
}


std::vector<SelfAction> Player::get_加杠(bool after_chipon)
{
	vector<SelfAction> actions;
	if (after_chipon == true) return actions;

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

std::vector<SelfAction> Player::get_暗杠(bool after_chipon)
{
	vector<SelfAction> actions;
	if (after_chipon == true) return actions;
	
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
	}
	else throw runtime_error("最后一手既不是吃又不是碰，不考虑食替");
}

std::vector<SelfAction> Player::get_打牌(bool after_chipon)
{
	vector<SelfAction> actions;
	for (auto tile : hand) {
		// 检查食替情况,不可打出
		if (after_chipon && is食替(this, tile->tile)) continue;
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
	cout << "Warning:自摸 is not considered yet" << endl;
	return std::vector<SelfAction>();
}

std::vector<SelfAction> Player::get_立直()
{
	cout << "Warning:立直 is not considered yet" << endl;
	return std::vector<SelfAction>();
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

std::vector<SelfAction> Player::get_九种九牌(bool 第一巡)
{
	vector<SelfAction> actions;
	if (!第一巡) return actions;

	// 考虑到第一巡可以有人暗杠，但是自己不行
	if (hand.size() != 14) return actions;

	if (九种九牌counter(hand) >= 9) {
		SelfAction action;
		action.action == Action::九种九牌;
		actions.push_back(action);		
	}	
	return actions;
}

static
vector<vector<Tile*>> get_Chi_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_顺子({ hand[i]->tile, hand[j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[j] });

			}
	}
	return chi_tiles;
}

static
vector<vector<Tile*>> get_Pon_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 1; ++i) {
		for (int j = 1; (i + j) < hand.size(); ++j)
			if (is_刻子({ hand[i]->tile, hand[j]->tile, tile->tile })) {
				chi_tiles.push_back({ hand[i] , hand[j] });

			}
	}
	return chi_tiles;
}

static
vector<vector<Tile*>> get_Kan_tiles(vector<Tile*> hand, Tile* tile) {
	vector<vector<Tile*>> chi_tiles;
	for (int i = 0; i < hand.size() - 2; ++i) {
		for (int j = 1; (i + j) < hand.size() - 1; ++j)
			for (int k = 1; (i + j + k) < hand.size(); ++k)
				if (
					is_杠({ 
						hand[i]->tile, 
						hand[j]->tile, 
						hand[k]->tile,
						tile->tile })) {
					chi_tiles.push_back({ hand[i] , hand[j], hand[k] });

				}
	}
	return chi_tiles;
}

std::vector<ResponseAction> Player::get_荣和(Tile * tile)
{
	cout << "Warning:荣和 is not considered yet" << endl;
	return std::vector<ResponseAction>();
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
		action.action = Action::碰;
		action.correspond_tiles.assign(one_chi_tiles.begin(), one_chi_tiles.end());
		actions.push_back(action);
	}

	return actions;
}

void Player::sort_hand()
{
	std::sort(hand.begin(), hand.end(), tile_comparator);
}

void Player::test_show_hand()
{
	cout << hand_to_string();
}

#pragma endregion

#pragma region TABLE

void Table::init_tiles()
{
	for (int i = 0; i < N_TILES; ++i) {
		tiles[i].tile = static_cast<BaseTile>(i % 34);
		tiles[i].belongs = Belong::yama;
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
}

void Table::init_wind()
{
	player[庄家].wind = Wind::East;
	player[(庄家 + 1) % 4].wind = Wind::South;
	player[(庄家 + 2) % 4].wind = Wind::West;
	player[(庄家 + 3) % 4].wind = Wind::North;
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
		cout << 牌山[5 - i * 2]->to_string() << " ";
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
	player[i_player].test_show_hand();
}

void Table::test_show_all_player_hand()
{
	for (int i = 0; i < 4; ++i) {
		cout << "Player" << i << " : "
			<< player[i].hand_to_string()
			<< endl;
	}
	cout << endl;
}

void Table::test_show_player_info(int i_player)
{
	cout << "Player" << i_player << " : "
		<< endl << player[i_player].to_string();
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

Result Table::GameProcess(bool verbose)
{
	init_tiles();
	init_red_dora_3();
	shuffle_tiles();
	init_yama();
	// 每人发13张牌
	_deal(0, 13);
	_deal(1, 13);
	_deal(2, 13);
	_deal(3, 13);
	ALLSORT;

	// 初始化每人自风
	init_wind();
	// 给庄家发牌
	发牌(庄家);

	turn = 庄家;
	
	VERBOSE{
		test_show_all();
	}

	// 测试Agent
	for (int i = 0; i < 4; ++i) {
		if (agents[i] == nullptr) 
			throw runtime_error("Agent " + to_string(i) + " is not registered!"); 
	}

	// 游戏进程的主循环,循环的开始是某人有3n+2张牌
	while (1) {
		auto actions = GetValidActions();

		// 让Agent进行选择
		int selection = agents[turn]->get_self_action(this, actions);
		auto selected_action = actions[selection];
		switch (selected_action.action) {
		case Action::九种九牌:
			return 九种九牌流局结算(this);
		case Action::自摸:
			return 自摸结算(this);
		case Action::出牌: {
			auto tile = selected_action.correspond_tiles[0];
			// 等待回复

			vector<ResponseAction> actions(4);
			Action final_action = Action::pass;
			for (int i = 0; i < 4; ++i) {
				if (i == turn) {
					actions[i].action = Action::pass;
					continue;
				}
				// 对于所有其他人
				auto response = GetValidResponse(i, tile);
				int selected_response = agents[i]->get_response_action(this, response);
				actions[i] = response[selected_response];

				// 从actions中获得优先级
				if (actions[i].action > final_action)
					final_action = actions[i].action;
			}
			
			// 保存那张要被打出的牌
			vector<Tile*>::iterator iter = 
				find(player[turn].hand.begin(), player[turn].hand.end(), tile[0]);
			// 根据最终的final_action来进行判断
			switch (final_action) {
			case Action::pass:
				// 消除第一巡和一发
				player[turn].一发 = false;
				player[turn].first_round = false;
				// 什么都不做。将action对应的牌从手牌移动到牌河里面
				player[turn].river.push_back(tile);
				player[turn].hand.erase(iter);
				next_turn();
				continue;
			case Action::吃:
				// 消除第一巡和一发
				for (int i = 0; i < 4; ++i) {
					player[i].first_round = false;
					player[i].一发 = false;
				}

			}
		}
		default:
			throw runtime_error("Selection invalid!");
		}

	}
}

void Table::_deal(int i_player)
{		
	player[i_player].hand.push_back(牌山.back());
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
	openGameLog.log摸牌(i_player, nullptr);
	fullGameLog.log摸牌(i_player, player[i_player].hand.back());
}

Table::Table(int 庄家, Agent * p1, Agent * p2, Agent * p3, Agent * p4) : dora_spec(1), 庄家(庄家)
{
	agents[0] = p1;
	agents[1] = p2;
	agents[2] = p3;
	agents[3] = p4;
	for (int i = 0; i < 4; ++i) player[i].score = 25000;
}

Table::Table(int 庄家,
	Agent* p1, Agent* p2, Agent* p3, Agent* p4, int scores[4])
	: dora_spec(1), 庄家(庄家)
{
	agents[0] = p1;
	agents[1] = p2;
	agents[2] = p3;
	agents[3] = p4;
	for (int i = 0; i < 4; ++i) player[i].score = scores[i];
}

std::vector<SelfAction> Table::GetValidActions()
{
	vector<SelfAction> actions;
	auto& the_player = player[turn];
	merge_into(actions, the_player.get_加杠(after_chipon));
	merge_into(actions, the_player.get_暗杠(after_chipon));
	merge_into(actions, the_player.get_打牌(after_chipon));
	merge_into(actions, the_player.get_自摸());
	merge_into(actions, the_player.get_立直());

	return actions;
}

std::vector<ResponseAction> Table::GetValidResponse(int i, Tile* tile)
{
	std::vector<ResponseAction> actions;
	
	// first: pass action
	ResponseAction action_pass;
	action_pass.action = Action::pass;
	actions.push_back(action_pass);

	auto &the_player = player[i];

	merge_into(actions, the_player.get_荣和(tile));
	merge_into(actions, the_player.get_Chi(tile));
	merge_into(actions, the_player.get_Pon(tile));
	merge_into(actions, the_player.get_Kan(tile));

	return actions;
}

Table::~Table()
{
}

#pragma endregion

#pragma region(GAMELOG)
#pragma endregion


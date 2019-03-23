#include "Table.h"
#include "macro.h"
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
	srand((unsigned)time(NULL));
	for (int i = N_TILES - 1; i > 0; --i)
	{
		swap(tiles[i], tiles[rand() % (i + 1)]);
	}
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

	// 游戏进程的主循环,循环的开始是某人有14张牌
	while (1) {

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

Table::Table(int 庄家)
	: dora_spec(1), 庄家(庄家)
{
}


Table::~Table()
{
}

#pragma endregion

BaseGameLog::BaseGameLog(int p1, int p2, Action action, Tile *tile,
	std::vector<Tile*> fulu)
	:player(p1), player2(p2), action(action), 牌(tile), 副露(fulu)
{
}

std::string BaseGameLog::to_string()
{
	stringstream ss;
	switch (action) {
	case Action::暗杠:
		ss << "暗杠|"; 
		goto 副露情况;
	case Action::碰:
		ss << "碰|";
		goto 副露情况;
	case Action::吃:
		ss << "吃|";
		goto 副露情况;
	case Action::手切:
		ss << "手切|";
		goto 出牌情况;
	case Action::摸切:
		ss << "摸切|";
		goto 出牌情况;
	case Action::摸牌:
		ss << "摸牌|";
		goto 出牌情况;
	default:
		return "??\n";
	}
	
出牌情况:
	if (牌 == nullptr) {
		ss << "-";
	}
	else {
		ss << 牌->to_string();
	}
	ss << "|Player" << player << endl;
	return ss.str();
副露情况:
	ss << 副露_to_string(牌, 副露)
		<< "|Player" << player
		<< "|Player2" << player2
		<< endl;
	return ss.str();
}

std::string GameLog::to_string()
{
	stringstream ss;
	for (auto log : logs) {
		ss << log.to_string();
	}
	return ss.str();
}

void GameLog::_log(int player1, int player2, Action action,
	Tile *tile, std::vector<Tile*> fulu)
{
	logs.push_back(BaseGameLog(player1, player2, action, tile, fulu));
}

void GameLog::log摸牌(int player, Tile* tile)
{
	_log(player, -1, Action::摸牌, tile, {});
}

void GameLog::log摸切(int player, Tile *tile)
{
	_log(player, -1, Action::摸切, tile, {});
}

void GameLog::log手切(int player, Tile *tile)
{
	_log(player, -1, Action::手切, tile, {});
}

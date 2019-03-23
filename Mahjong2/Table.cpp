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
	ss << "�Է�" << wind_to_string(wind) << endl;
	ss << "����:" << hand_to_string();
	ss << endl;
	ss << "�ƺ�:" << river_to_string();
	ss << endl;
	if (riichi) {
		ss << "��ֱ״̬" << endl;
	}
	else {
		ss << "δ��ֱ״̬" << endl;
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
	��ɽ.swap(empty);
	for (int i = 0; i < N_TILES; ++i) {
		��ɽ.push_back(&(tiles[i]));
	}
}

void Table::init_wind()
{
	player[ׯ��].wind = Wind::East;
	player[(ׯ�� + 1) % 4].wind = Wind::South;
	player[(ׯ�� + 2) % 4].wind = Wind::West;
	player[(ׯ�� + 3) % 4].wind = Wind::North;
}

void Table::test_show_yama_with_����()
{
	cout << "��ɽ:";
	if (��ɽ.size() < 14) {
		cout << "�Ʋ���14��" << endl;
		return;
	}
	for (int i = 0; i < 14; ++i) {
		cout << ��ɽ[i]->to_string() << " ";
	}
	cout << "(������)| ";
	for (int i = 14; i < ��ɽ.size(); ++i) {
		cout << ��ɽ[i]->to_string() << " ";
	}
	cout << endl;
	cout << "����ָʾ��Ϊ:";
	for (int i = 0; i < dora_spec; ++i) {
		cout << ��ɽ[5 - i * 2]->to_string() << " ";
	}
	cout << endl;
}

void Table::test_show_yama()
{
	cout << "��ɽ:";
	for (int i = 0; i < ��ɽ.size(); ++i) {
		cout << ��ɽ[i]->to_string() << " ";
	}
	cout << "��" << ��ɽ.size() << "����";
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
	// ÿ�˷�13����
	_deal(0, 13);
	_deal(1, 13);
	_deal(2, 13);
	_deal(3, 13);
	ALLSORT;

	// ��ʼ��ÿ���Է�
	init_wind();
	// ��ׯ�ҷ���
	����(ׯ��);	

	turn = ׯ��;
	VERBOSE{
		test_show_all();
	}

	// ��Ϸ���̵���ѭ��,ѭ���Ŀ�ʼ��ĳ����14����
	while (1) {

	}
}

void Table::_deal(int i_player)
{		
	player[i_player].hand.push_back(��ɽ.back());
	��ɽ.pop_back();
}

void Table::_deal(int i_player, int n_tiles)
{
	for (int i = 0; i < n_tiles; ++i) {
		_deal(i_player);
	}
}

void Table::����(int i_player)
{
	_deal(i_player);
	openGameLog.log����(i_player, nullptr);
	fullGameLog.log����(i_player, player[i_player].hand.back());
}

Table::Table(int ׯ��)
	: dora_spec(1), ׯ��(ׯ��)
{
}


Table::~Table()
{
}

#pragma endregion

BaseGameLog::BaseGameLog(int p1, int p2, Action action, Tile *tile,
	std::vector<Tile*> fulu)
	:player(p1), player2(p2), action(action), ��(tile), ��¶(fulu)
{
}

std::string BaseGameLog::to_string()
{
	stringstream ss;
	switch (action) {
	case Action::����:
		ss << "����|"; 
		goto ��¶���;
	case Action::��:
		ss << "��|";
		goto ��¶���;
	case Action::��:
		ss << "��|";
		goto ��¶���;
	case Action::����:
		ss << "����|";
		goto �������;
	case Action::����:
		ss << "����|";
		goto �������;
	case Action::����:
		ss << "����|";
		goto �������;
	default:
		return "??\n";
	}
	
�������:
	if (�� == nullptr) {
		ss << "-";
	}
	else {
		ss << ��->to_string();
	}
	ss << "|Player" << player << endl;
	return ss.str();
��¶���:
	ss << ��¶_to_string(��, ��¶)
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

void GameLog::log����(int player, Tile* tile)
{
	_log(player, -1, Action::����, tile, {});
}

void GameLog::log����(int player, Tile *tile)
{
	_log(player, -1, Action::����, tile, {});
}

void GameLog::log����(int player, Tile *tile)
{
	_log(player, -1, Action::����, tile, {});
}

#pragma once

#include "Tile.h"

constexpr auto N_TILES = (34*4);
constexpr auto INIT_SCORE = 25000;

enum class Action : uint8_t {
	��, ��,
	��,
	����,
	����,
	����,
	������ֱ,
	������ֱ,
	����,
	����,
	�ٺ�,
	���־���,
};

struct SelfAction {
	Action action;
	std::vector<Tile*> correspond_tiles;
	SelfAction(Action, std::vector<Tile*>);
};

struct ResponseAction {
	Action action;
	std::vector<Tile*> correspond_tiles;
};

struct BaseGameLog {
	int player; // ����
	int player2;// ����
	Action action;
	Tile* ��;
	std::vector<Tile*> ��¶;	

	BaseGameLog(int, int, Action, Tile*, std::vector<Tile*>);

	std::string to_string();
};

class GameLog {
public:
	std::vector<BaseGameLog> logs;
	std::string to_string();
	void _log(int player1, int player2, Action, Tile*, std::vector<Tile*>);
	void log����(int player, Tile*);
	void log����(int player, Tile*);
	void log����(int player, Tile*);
};

class Player {
public:
	Player();
	bool riichi;
	Wind wind;
	bool �׼�;
	int score;
	std::vector<Tile*> hand;
	std::vector<Tile*> river;
	std::unordered_map<Tile*, std::vector<Tile*>> ��¶s;
	std::string hand_to_string();
	std::string river_to_string();

	std::string to_string();

	void play_tile();

	void sort_hand();
	void test_show_hand();	
};

enum ResultType {
	�ٺ��վ�,
	�����վ�,
	���־��������վ�,
	��������,
	������������,
	һ����������,
	������������,
	������������,
	������������,
	�����ٺ�,
	�����ٺ�,
};

struct Result {
	ResultType result_type;

	// ������һ���ٺ͵����
	int score;
	int fan;
	int fu;
	int ��������;

	// �����ٺ͵����
	int score2;
	int fan2;
	int fu2;
	int ��������2;

	// �����ٺ͵����
	int score3;
	int fan3;
	int fu3;
	int ��������3;

	std::vector<int> winner;
	std::vector<int> loser;
};

class Table
{
private:
	Tile tiles[N_TILES];
public:
	int dora_spec;
	Wind ����;
	int ׯ��;
	void init_tiles();
	void init_red_dora_3();
	void shuffle_tiles();
	void init_yama();

	void init_wind();
	
	void _deal(int i_player);
	void _deal(int i_player, int n_tiles);

	void ����(int i_player);

	inline void next_turn() { turn++; turn = turn % 4; }

	GameLog openGameLog;
	GameLog fullGameLog;

	int turn;

	Table(int ׯ��);

	// ��Ϊһ����turn���ڵ�player�ж������Բ���Ҫ����playerID
	std::vector<SelfAction> GetValidActions();
	std::vector<ResponseAction> GetValidResponse(int player);

	std::vector<Tile*> ��ɽ;
	Player player[4];
	~Table();

	void test_show_yama_with_����();
	void test_show_yama();
	void test_show_player_hand(int i_player);
	void test_show_all_player_hand();
	void test_show_player_info(int i_player);
	void test_show_all_player_info();
	void test_show_open_gamelog();
	void test_show_full_gamelog();

	inline void test_show_all() {
		test_show_yama_with_����();
		test_show_all_player_info();
		test_show_open_gamelog();
		test_show_full_gamelog();
		std::cout << "�ֵ�Player" << turn << std::endl;
	}

	Result GameProcess(bool);

};


#ifndef PLAYER_H
#define PLAYER_H

#include "Action.h"
#include "Tile.h"

class Player {
public:
	Player();
	bool double_riichi = false;
	bool riichi = false;

	inline bool is_riichi() { return riichi || double_riichi; }

	bool ���� = true;
	Wind wind;
	bool �׼�;
	bool ���� = false;
	bool ��ֱ���� = false;

	bool is����() { return ���� || ��ֱ����; }

	int score;
	std::vector<Tile*> hand;
	River river;
	std::vector<Fulu> ��¶s;
	std::string hand_to_string() const;
	std::string river_to_string() const;

	std::string to_string() const;

	bool һ��;
	bool first_round = true;

	// SelfAction
	std::vector<SelfAction> get_�Ӹ�();
	std::vector<SelfAction> get_����();
	std::vector<SelfAction> get_����(bool after_chipon);
	std::vector<SelfAction> get_����(Table*);
	std::vector<SelfAction> get_��ֱ();
	std::vector<SelfAction> get_���־���();

	// Response Action
	std::vector<ResponseAction> get_�ٺ�(Table*, Tile* tile);
	std::vector<ResponseAction> get_Chi(Tile* tile);
	std::vector<ResponseAction> get_Pon(Tile* tile);
	std::vector<ResponseAction> get_Kan(Tile* tile); // ������

	// Response Action (������)
	std::vector<ResponseAction> get_������(Tile* tile);

	// Response Action (����)
	std::vector<ResponseAction> get_����(Tile* tile);

	// ��ֱ��
	std::vector<SelfAction> riichi_get_����(Table* table);
	std::vector<SelfAction> riichi_get_����();

	void move_from_hand_to_fulu(std::vector<Tile*> tiles, Tile* tile);
	void remove_from_hand(Tile* tile);

	// �����е�BaseTileֵΪtile���ĸ����ƶ�����¶��
	void play_����(BaseTile tile);

	// �ƶ�tile����¶�к���basetile��ͬ�Ŀ�����
	void play_�Ӹ�(Tile* tile);

	// �����ƶ����ƺӣ�һ��û���˳����ܣ�
	// remainָ�������ǲ��������ϻ����ƺ�
	void move_from_hand_to_river(Tile* tile, int& number, bool remain, bool fromhand);

	inline void move_from_hand_to_river_log_only(Tile* tile, int& number, bool fromhand) {
		return move_from_hand_to_river(tile, number, false, fromhand);
	}

	inline void move_from_hand_to_river_really(Tile* tile, int& number, bool fromhand) {
		return move_from_hand_to_river(tile, number, true, fromhand);
	}

	void sort_hand();
	void test_show_hand();
};

#endif
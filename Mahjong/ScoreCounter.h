#ifndef SCORE_COUNTER_H
#define SCORE_COUNTER_H

#include <tuple>
#include <vector>
#include <sstream>
#include "Yaku.h"
#include "Tile.h"
#include "Player.h"

namespace_mahjong
int calculate_fan(const std::vector<Yaku>& yakus);

inline bool operator<(const std::pair<std::vector<Yaku>, int>& lhs, const std::pair<std::vector<Yaku>, int>& rhs)
{
	int lfan = calculate_fan(lhs.first);
	int rfan = calculate_fan(lhs.first);
	
	return std::tie(lfan, lhs.second) < std::tie(rfan, rhs.second);
}

struct CounterResult {
	std::vector<Yaku> yakus;
	
	// 分数的cases
	int score1 = 0;
	int score2 = 0; // 自摸时用。score1=亲，score2=子

	void calculate_score(bool 亲, bool 自摸);
	
	int fan = 0;
	int fu = 0;
};

//class Table;
//class Tile;

// turn 判定役的玩家
// correspond_tile (自摸为nullptr，荣和为荣和牌）
// CounterResult yaku_counter(const Table *table, const Player &player, Tile* correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风);

//CounterResult yaku_counter_v2(Table *table, Player &player, Tile* correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风);


//1pK -> 1p 1p 1p
//1pS -> 1p 2p 3p
//1zK -> 1z 1z 1z
//1zK- -> 1z 1z 1z 副露

//1p|- -> 1p 1p 1p 1p
//1p: -> 1p 1p
//1p|+ -> 1p 1p 1p 1p 暗杠

//1pK! -> (1p) 1p 1p

//1pS! -> 自摸(1p) 2p 3p
//1pS@ -> 自摸1p (2p) 3p
//1pS# -> 自摸1p 2p (3p)
//1pS$ -> (1p) 2p 3p
//1pS% -> 1p (2p) 3p
//1pS^ -> 1p 2p (3p)

// 前两位：表示牌
// 第三位：表示属性 K：刻子 ， S：顺子，: 对子，|: 杠子
// 第四位：表示位置 - 表示副露 + 表示暗杠 !@# 表示自摸 $%^表示荣和

constexpr char mark_toitsu = ':';
constexpr char mark_shuntsu = 'S';
constexpr char mark_koutsu = 'K';
constexpr char mark_kantsu = '|';
constexpr char mark_ankan = '+';
constexpr char mark_minkan = '-';
constexpr char mark_fuuro = '-';
constexpr char mark_tsumo_1st = '!';
constexpr char mark_tsumo_2nd = '@';
constexpr char mark_tsumo_3rd = '#';
constexpr char mark_ron_1st = '$';
constexpr char mark_ron_2nd = '%';
constexpr char mark_ron_3rd = '^';


//constexpr static BaseTile raw[] = { _1m, _9m, _1s, _9s, _1p, _9p,
//     _1z, _2z, _3z, _4z, _5z, _6z, _7z };

class ScoreCounter {
public:
	std::vector<Tile*> tiles;
	Tile* win_tile = nullptr;
	std::vector<BaseTile> basetiles;

	std::vector<std::vector<CompletedTiles>> completedtiles_list;

	std::vector<Yaku> 天地和;
	std::vector<Yaku> 场役;
	std::vector<Yaku> Dora役;
	// int 最大手役番 = 0;
	std::pair<std::vector<Yaku>, int> 最大手役_番符;

	const Table* table = nullptr;
	const Player* player = nullptr;

	bool 有役 = false;

	bool tsumo = false;
	bool 门清 = false;
	bool 国士 = false, 国士13 = false;
	bool 九莲 = false, 九莲纯 = false;
	bool 役满 = false;
	bool 抢杠 = false, 抢暗杠 = false;
	int 役满倍数 = 0;
	int mpsz一色 = 0;
	Wind 自风, 场风;
	
	ScoreCounter(const Table* t, const Player* p, Tile* win, bool 抢杠_, bool 抢暗杠_);
	
	bool get_天地和();
	bool get_国士();
	inline void get一色();
	bool get_九莲();

	std::vector<std::vector<std::string>> generate_tile_group_strings(const CompletedTiles& ct, const std::vector<Fulu>& fulus, bool tsumo, BaseTile last_tile);
	std::vector<Yaku> get_手役_役满(const std::vector<std::string>& tile_group_string, Wind 自风, Wind 场风, bool& 役满);
	std::pair<std::vector<Yaku>, int> get_手役(std::vector<std::string> tile_group_string, Wind 自风, Wind 场风, bool 门清);
	std::pair<std::vector<Yaku>, int> get_max_手役(const CompletedTiles& ct, const std::vector<Fulu>& fulus, Tile* correspond_tile, BaseTile tsumo_tile, Wind 自风, Wind 场风, bool 门清, bool& 役满);

	void get_立直();
	void get_海底河底();
	void get_抢杠();
	void get_岭上();
	void get_门清自摸();
	void get_一发();
	void get_aka_dora();
	void get_dora();
	void get_ura_dora();

	inline void get_场役_Dora役()
	{
		get_立直();
		get_海底河底();

		get_抢杠();
		get_岭上();

		get_一发();
		get_门清自摸();

		get_aka_dora();
		get_dora();
		get_ura_dora();
	}	

	CounterResult yaku_counter();
	bool check_有役();
	
};

namespace_mahjong_end

#endif
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

inline bool compare_yaku_fu(const std::pair<std::vector<Yaku>, int>& lhs, const std::pair<std::vector<Yaku>, int>& rhs)
{
	int lfan = calculate_fan(lhs.first);
	int rfan = calculate_fan(rhs.first);
	
	return std::tie(lfan, lhs.second) < std::tie(rfan, rhs.second);
}

struct CounterResult {
	std::vector<Yaku> yakus;
	
	// 分数的cases
	int score1 = 0;
	int score2 = 0; // 自摸时用。score1=亲，score2=子

	void calculate_score(bool oya, bool tsumo);
	
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

class ScoreCounter {
public:
	std::vector<Tile*> tiles;
	Tile* win_tile = nullptr;
	std::vector<BaseTile> basetiles;

	std::vector<std::vector<CompletedTiles>> completedtiles_list;

	// 天地胡
	std::vector<Yaku> tenhou_chihou_yakus;

	// 基于状态的役，包括立直、一发、海底、河底、抢杠、岭上、门清自摸
	std::vector<Yaku> state_yakus;

	// dora役
	std::vector<Yaku> dora_yakus;

	// 最大手役番&符
	std::pair<std::vector<Yaku>, int> max_hand_yakus_fan_fu = { {}, 20 };

	const Table* table = nullptr;
	const Player* player = nullptr;

	// 有役
	bool have_yaku = false;

	bool tsumo = false;
	bool menzen = false;
	bool kokushi = false, kokushi_13 = false;
	bool churen = false, churen_pure = false;

	bool chankan = false, chanankan = false;
	// 役满状态
	bool yakuman = false;

	// 几倍役满
	int yakuman_fold = 0;

	// 清一色 or 字一色 (mpsz = 0,1,2,3, respectively)
	int mpsz_pure_type = 0;
	Wind self_wind, game_wind;
	
	/* Arguments:
		Table *t,
		Player* p,
		Tile* win_tile,
		bool chankan,
		bool chanankan		
	*/
	ScoreCounter(const Table* t, const Player* p, Tile* win, bool chankan, bool chanankan);
	
	bool get_tenhou_chihou();
	bool get_kokushi();
	bool get_churen();

	// 更新清一色 or 字一色, mpsz_pure_type
	void get_pure_type();

	std::vector<std::vector<std::string>> generate_tile_group_strings(const CompletedTiles& ct, const std::vector<CallGroup>& callgroups, bool tsumo, BaseTile last_tile);
	std::vector<Yaku> get_hand_yakuman(const std::vector<std::string>& tile_group_string, Wind self_wind, Wind game_wind, bool& yakuman);
	std::pair<std::vector<Yaku>, int> get_hand_yakus(const std::vector<std::string> &tile_group_string, Wind self_wind, Wind game_wind, bool menzen);
	std::pair<std::vector<Yaku>, int> get_max_hand_yakus(const CompletedTiles& ct, const std::vector<CallGroup>& callgroups, Tile* correspond_tile, BaseTile tsumo_tile, Wind self_wind, Wind game_wind, bool menzen, bool& yakuman);

	void get_riichi();

	// 海底&河底
	void get_haitei_hotei();
	void get_chankan();
	void get_rinshan();
	void get_menzentsumo();
	void get_ippatsu();
	void get_aka_dora();
	void get_dora();
	void get_ura_dora();

	/* 状态役 state yaku
	*	满足一定条件后可以无条件胡牌的役，包括一发，但不包括天地胡
	*	包括
	*		- 立直
	*		- 海底
	*		- 河底
	*		- 抢杠
	*		- 岭上
	*		- 一发
	*		- 门清自摸
	*/
	inline void get_state_yaku_dora_yaku()
	{
		get_riichi();
		get_haitei_hotei();

		get_chankan();
		get_rinshan();

		get_ippatsu();
		get_menzentsumo();

		get_aka_dora();
		get_dora();
		get_ura_dora();
	}	

	CounterResult yaku_counter();
		
};

namespace_mahjong_end

#endif
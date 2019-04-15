#include "ScoreCounter.h"
#include "Table.h"
#include "Rule.h"
#include "macro.h"

using namespace std;

#define REGISTER_SCORE(亲, 自摸, score_铳亲, score_亲自摸_all, score_铳子, score_子自摸_亲, score_子自摸_子) \
if (亲) {if (自摸){score1=score_亲自摸_all;} else{score1=score_铳亲;}} \
else {if (自摸) {score1=score_子自摸_亲; score2=score_子自摸_子;} else{score1=score_铳子;}}

/*


*/

static vector<pair<vector<Yaku>, int>> get_手役_from_complete_tiles(CompletedTiles ct, vector<Fulu> fulus, Tile* correspond_tile, BaseTile tsumo_tile);

CounterResult yaku_counter(Table *table, int turn, Tile *correspond_tile, bool 抢杠, bool 抢暗杠)
{
	// 首先 假设进入到这个counter阶段的，至少满足了和牌条件的牌型
	// 以及，是否有某种役是不确定的

	// 从最简单的场役开始计算

	bool tsumo = (correspond_tile == nullptr);

	CounterResult final_result;

	vector<Yaku> 场役;
	vector<Yaku> Dora役;

	auto &player = table->player[turn];

	/* riichi 和 double riichi 不重复计算 */
	if (player.double_riichi)
		场役.push_back(Yaku::两立直);
	else if (player.riichi)
		场役.push_back(Yaku::立直);

	/* 海底的条件是1. remain_tile == 0, 2. 上一手不是杠相关 */
	if (table->get_remain_tile() == 0 &&
		table->last_action != Action::暗杠 &&
		table->last_action != Action::杠 &&
		table->last_action != Action::加杠) {
		
		// 如果是tsumo
		if (tsumo) 场役.push_back(Yaku::海底捞月);
		else 场役.push_back(Yaku::河底捞鱼);
	}

	/* 天地和的条件是，在第一巡，且没人鸣牌*/
	if (player.first_round) {
		if (table->庄家 == turn)
			场役.push_back(Yaku::天和);
		else
			场役.push_back(Yaku::地和);
	}

	/* 如果是抢杠，那么计算抢杠 */
	if (抢杠 || 抢暗杠) {
		场役.push_back(Yaku::抢杠);
	}

	/* 如果上一轮动作是杠，这一轮是tsumo，那么就是岭上 */
	if (table->last_action == Action::暗杠 ||
		table->last_action == Action::加杠 ||
		table->last_action == Action::杠) {
		if (tsumo) {
			场役.push_back(Yaku::岭上开花);
		}
	}

	/* 如果保存有一发状态 */
	if (player.一发) {
		场役.push_back(Yaku::一发);
	}

	// 接下来统计红宝牌数量
	for (auto tile : player.hand) {
		if (tile->red_dora == true) {
			Dora役.push_back(Yaku::赤宝牌);
		}
	}

	for (auto fulu : player.副露s) {
		for (auto tile : fulu.tiles) {
			if (tile->red_dora == true) {
				Dora役.push_back(Yaku::赤宝牌);
			}
		}
	}
	
	// 接下来统计宝牌数量
	auto doratiles = table->get_dora();
	for (auto doratile : doratiles) {
		for (auto tile : player.hand) {
			if (tile->tile == doratile) {
				Dora役.push_back(Yaku::宝牌);
			}
		}

		for (auto fulu : player.副露s) {
			for (auto tile : fulu.tiles) {
				if (tile->tile == doratile) {
					Dora役.push_back(Yaku::宝牌);
				}
			}
		}
	}

	// 如果是立直和牌，继续统计里宝牌
	if (player.is_riichi()) {
		auto doratiles = table->get_ura_dora();
		for (auto doratile : doratiles) {
			for (auto tile : player.hand) {
				if (tile->tile == doratile) {
					Dora役.push_back(Yaku::里宝牌);
				}
			}

			for (auto fulu : player.副露s) {
				for (auto tile : fulu.tiles) {
					if (tile->tile == doratile) {
						Dora役.push_back(Yaku::里宝牌);
					}
				}
			}
		}
	}

	// 役 = 手役+场役+Dora。手役根据牌的解释不同而不同。
	vector<pair<vector<Yaku>, int>> AllYakusAndFu;

	// 接下来统计国士无双
	auto tiles = player.hand;
	if (correspond_tile != nullptr)
		tiles.push_back(correspond_tile);

	if (is国士无双和牌型(convert_tiles_to_base_tiles(tiles))) {
		vector<Yaku> yakus;
		
		yakus.push_back(Yaku::国士无双);
		AllYakusAndFu.push_back({ yakus, 0 });
	}

	// 接下来统计七对子
	if (is七对和牌型(convert_tiles_to_base_tiles(tiles))) {
		vector<Yaku> yakus;
		merge_into(yakus, 场役);
		merge_into(yakus, Dora役);
		yakus.push_back(Yaku::七对子);

		// 7对固定25符
		AllYakusAndFu.push_back({ yakus, 25 });
	}

	// 接下来对牌进行拆解
	auto &complete_tiles_list = getCompletedTiles(convert_tiles_to_base_tiles(tiles));
	for (auto &complete_tiles : complete_tiles_list) {
		auto yaku_fus = get_手役_from_complete_tiles(complete_tiles, player.副露s, correspond_tile, player.hand.back()->tile);
		for (auto &yaku_fu : yaku_fus) {
			vector<Yaku> yakus(场役.begin(), 场役.end());
			merge_into(yakus, yaku_fu.first);

			AllYakusAndFu.push_back({ yakus, yaku_fu.second });
		}
	}

}



void CounterResult::calculate_score(bool 亲, bool 自摸)
{
	if (fan == 6 * 13) {
		// 6倍 役满
		REGISTER_SCORE(亲, 自摸, 48000 * 6, 16000 * 6, 32000 * 6, 16000 * 6, 8000 * 6);
	}
	else if (fan == 5 * 13) {
		// 5倍 役满
		REGISTER_SCORE(亲, 自摸, 48000 * 5, 16000 * 5, 32000 * 5, 16000 * 5, 8000 * 5);
	}
	else if (fan == 4 * 13) {
		// 4倍 役满		
		REGISTER_SCORE(亲, 自摸, 48000 * 4, 16000 * 4, 32000 * 4, 16000 * 4, 8000 * 4);
	}
	else if (fan == 3 * 13) {
		// 3倍 役满
		REGISTER_SCORE(亲, 自摸, 48000 * 3, 16000 * 3, 32000 * 3, 16000 * 3, 8000 * 3);
	}
	else if (fan == 2 * 13) {
		// 2倍 役满
		REGISTER_SCORE(亲, 自摸, 48000 * 2, 16000 * 2, 32000 * 2, 16000 * 2, 8000 * 2);
	}
	else if (fan >= 13) {
		// 役满
		REGISTER_SCORE(亲, 自摸, 48000, 16000, 32000, 16000, 8000);
	}
	else if (fan >= 11) {
		REGISTER_SCORE(亲, 自摸, 36000, 12000, 24000, 12000, 6000);
	}
	else if (fan >= 8) {
		REGISTER_SCORE(亲, 自摸, 24000, 8000 , 16000, 8000, 4000);
	}
	else if (fan >= 6) {
		REGISTER_SCORE(亲, 自摸, 18000, 6000 , 12000, 6000, 3000);
	}
	else if (fan >= 5) {
		REGISTER_SCORE(亲, 自摸, 12000, 4000 , 8000, 4000, 2000);
	}
	else if (fan >= 4) {
		// 32符 即 40符
		if (fu >= 32) {
			REGISTER_SCORE(亲, 自摸, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 25) {
			REGISTER_SCORE(亲, 自摸, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 20) {
			REGISTER_SCORE(亲, 自摸, 7700, 2600, 5200, 2600, 1300);
		}
		else if (fu >= 22) {
			REGISTER_SCORE(亲, 自摸, 11600, 3600, 7700, 3900, 2000);
		}
	}
}

// 内部函数
vector<pair<vector<Yaku>, int>> get_手役_from_complete_tiles(CompletedTiles ct, vector<Fulu> fulus, Tile *correspond_tile, BaseTile tsumo_tile)
{
	bool tsumo;			 // 是自摸吗
	BaseTile last_tile;  // 最后取得的牌，既可以是荣和，也可以是自摸
	if (correspond_tile == nullptr) {
		tsumo = true;
		last_tile = tsumo_tile;
	}
	else {
		last_tile = correspond_tile->tile;
	}

	vector<pair<vector<Yaku>, int>> yaku_fus;
	// 当这个 荣和/自摸 的牌存在于不同的地方的时候，也有可能会导致解释不同



}

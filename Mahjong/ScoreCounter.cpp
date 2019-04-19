#include "ScoreCounter.h"
#include "Table.h"
#include "Rule.h"
#include "macro.h"

using namespace std;

#define REGISTER_SCORE(亲, 自摸, score_铳亲, score_亲自摸_all, score_铳子, score_子自摸_亲, score_子自摸_子) \
if (亲) {if (自摸){score1=score_亲自摸_all;} else{score1=score_铳亲;}} \
else {if (自摸) {score1=score_子自摸_亲; score2=score_子自摸_子;} else{score1=score_铳子;}} return;

static vector<pair<vector<Yaku>, int>> get_手役_from_complete_tiles(CompletedTiles ct, vector<Fulu> fulus, Tile* correspond_tile, BaseTile tsumo_tile);

int calculate_fan(vector<Yaku> yakus);

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

	/*门清自摸*/
	if (tsumo && player.门清) {
		场役.push_back(Yaku::门前清自摸和);
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
		bool is_13面;
		// 判定13面
		{
			auto tiles = player.hand;
			if (correspond_tile == nullptr) tiles.pop_back();
			vector<BaseTile> raw
			{ _1m, _9m, _1s, _9s, _1p, _9p, east, south, west, north, 白, 发, 中 };

			sort(tiles.begin(), tiles.end());
			if (is_same_container(raw, convert_tiles_to_base_tiles(tiles)))
				is_13面 = true;
			else is_13面 = false;
		}
		if (is_13面)
			yakus.push_back(Yaku::国士无双十三面);
		else
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
			vector<Yaku> yakus;
			merge_into(yakus, 场役);
			merge_into(yakus, Dora役);
			merge_into(yakus, yaku_fu.first);

			AllYakusAndFu.push_back({ yakus, yaku_fu.second });
		}
	}

	//对于AllYakusAndFu，判定番最高的，番相同的，判定符最高的
	
	auto iter = max_element(AllYakusAndFu.begin(), AllYakusAndFu.end(), [](pair<vector<Yaku>, int> yaku_fu1, pair<vector<Yaku>, int> yaku_fu2) {
		auto fan1 = calculate_fan(yaku_fu1.first);
		auto fan2 = calculate_fan(yaku_fu2.first);
		if (fan1 < fan2) return true;
		if (fan1 > fan2) return false;
		if (fan1 == fan2) return yaku_fu1.second < yaku_fu2.second;
	});

	if (iter == AllYakusAndFu.end()) {
		// 说明无役
		final_result.yakus.push_back(Yaku::None);
	}
	else if (!can_agari(iter->first)) {
		// 如果只有宝牌役/无役，置为无役
		final_result.yakus.assign({ Yaku::None });
	}
	else {
		final_result.yakus.assign(iter->first.begin(), iter->first.end());
		final_result.fan = calculate_fan(final_result.yakus);
		final_result.fu = iter->second;
		bool 亲家 = false;
		if (table->庄家 == turn) 亲家 = true;

		final_result.calculate_score(亲家, tsumo);
	}
	return final_result;
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
	else if (fan == 5) {
		REGISTER_SCORE(亲, 自摸, 12000, 4000 , 8000, 4000, 2000);
	}
	else if (fan == 4) {
		// 40符以上满贯
		if (fu >= 40) {
			REGISTER_SCORE(亲, 自摸, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 30) {
			REGISTER_SCORE(亲, 自摸, 11600, 3600, 7700, 3900, 2000);
		}
		else if (fu == 25) {
			REGISTER_SCORE(亲, 自摸, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 20) {
			REGISTER_SCORE(亲, 自摸, 7700, 2600, 5200, 2600, 1300);
		}
	}
	else if (fan == 3) {
		// 70符以上满贯
		if (fu >= 70) {
			REGISTER_SCORE(亲, 自摸, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 60) {
			REGISTER_SCORE(亲, 自摸, 11600, 3600, 7700, 3900, 2000);
		}
		else if (fu == 50) {
			REGISTER_SCORE(亲, 自摸, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 40) {
			REGISTER_SCORE(亲, 自摸, 7700, 2600, 5200, 2600, 1300);
		}
		else if (fu == 30) {
			REGISTER_SCORE(亲, 自摸, 5800, 2000, 3900, 2000, 1000);
		}
		else if (fu == 25) {
			REGISTER_SCORE(亲, 自摸, 4800, 1600, 3200, 1600, 800);
		}
		else if (fu == 20) {
			REGISTER_SCORE(亲, 自摸, 3900, 1300, 2600, 1300, 700);
		}
	}
	else if (fan == 2) {
		if (fu >= 110) {
			REGISTER_SCORE(亲, 自摸, 10600, 3600, 7100, 3600, 1800);
		}
		else if (fu == 100) {
			REGISTER_SCORE(亲, 自摸, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 90) {
			REGISTER_SCORE(亲, 自摸, 8700, 2900, 5800, 2900, 1500);
		}
		else if (fu == 80) {
			REGISTER_SCORE(亲, 自摸, 7700, 2600, 5200, 2600, 1300);
		}
		else if (fu == 70) {
			REGISTER_SCORE(亲, 自摸, 6800, 2300, 4500, 2300, 1200);
		}
		else if (fu == 60) {
			REGISTER_SCORE(亲, 自摸, 5800, 2000, 3900, 2000, 1000);
		}
		else if (fu == 50) {
			REGISTER_SCORE(亲, 自摸, 4800, 1600, 3200, 1600, 800);
		}
		else if (fu == 40) {
			REGISTER_SCORE(亲, 自摸, 3900, 1300, 2600, 1300, 700);
		}
		else if (fu == 30) {
			REGISTER_SCORE(亲, 自摸, 2900, 1000, 2000, 1000, 500);
		}
		else if (fu == 25) {
			REGISTER_SCORE(亲, 自摸, 2400, -1, 1600, -1, -1);
		}
		else if (fu == 20) {
			REGISTER_SCORE(亲, 自摸, 2000, 700, 1300, 700, 400);
		}
	}
	else if (fan == 1) {
		if (fu >= 110) {
			REGISTER_SCORE(亲, 自摸, 5300, -1, 3600, -1, -1);
		}
		else if (fu == 100) {
			REGISTER_SCORE(亲, 自摸, 4800, 1600, 3200, 1600, 800);
		}
		else if (fu == 90) {
			REGISTER_SCORE(亲, 自摸, 4400, 1500, 2900, 1500, 800);
		}
		else if (fu == 80) {
			REGISTER_SCORE(亲, 自摸, 3900, 1300, 2600, 1300, 700);
		}
		else if (fu == 70) {
			REGISTER_SCORE(亲, 自摸, 3400, 1200, 2300, 1200, 600);
		}
		else if (fu == 60) {
			REGISTER_SCORE(亲, 自摸, 2900, 1000, 2000, 1000, 500);
		}
		else if (fu == 50) {
			REGISTER_SCORE(亲, 自摸, 2400, 800, 1600, 800, 400);
		}
		else if (fu == 40) {
			REGISTER_SCORE(亲, 自摸, 2000, 700, 1300, 700, 400);
		}
		else if (fu == 30) {
			REGISTER_SCORE(亲, 自摸, 1500, 500, 1000, 500, 300);
		}
		else if (fu == 20) {
			REGISTER_SCORE(亲, 自摸, 1000, -1, -1, -1, -1);
		}
	}
	
	throw runtime_error("Error fan & fu cases.");	
}

// 内部函数
inline static
pair<vector<Yaku>, int> get_手役_from_complete_tiles_固定位置(
	const CompletedTiles &ct, vector<Fulu> fulus, BaseTile last_tile, bool tsumo, const BaseTile* position) {

	vector<Yaku> yakus;
	int fu;

	fu = 30;

	return { yakus, fu };
}

vector<pair<vector<Yaku>, int>> get_手役_from_complete_tiles(CompletedTiles ct, vector<Fulu> fulus, Tile *correspond_tile, BaseTile tsumo_tile)
{
	bool tsumo = false;			 // 是自摸吗
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
	// 这个牌一定在ct里面
	// 对于每一种情况，都是vector中的一个元素

	// 重要：ct之后不要进行复制
	// 首先统计ct中有多少个last_tile
	auto &head = ct.head;
	auto &body = ct.body;

	vector<BaseTile*> mark_last_tile_in_ct;
	{
		auto s = head.find(last_tile);
		if (s != nullptr) {
			mark_last_tile_in_ct.push_back(s);
		}
	}
	{
		for (auto &group : body) {
			auto s = group.find(last_tile);
			if (s != nullptr) {
				mark_last_tile_in_ct.push_back(s);
			}
		}
	}
	
	for (auto last_tile_pos : mark_last_tile_in_ct) {
		yaku_fus.push_back(get_手役_from_complete_tiles_固定位置(ct, fulus, last_tile, tsumo, last_tile_pos));
	}
	return yaku_fus;
}

int calculate_fan(vector<Yaku> yakus)
{
	bool 役满 = false;
	for (auto yaku : yakus) {
		if (yaku > Yaku::满贯 && yaku < Yaku::双倍役满) {
			役满 = true;
			break;
		}
	}
	int fan = 0;
	if (役满) {
		for (auto yaku : yakus) {
			if (yaku < Yaku::满贯) continue; // 跳过所有不是役满的
			if (yaku > Yaku::满贯 && yaku < Yaku::役满) fan += 13;
			if (yaku > Yaku::役满 && yaku < Yaku::双倍役满) fan += 26;
		}
		return fan;
	}
	else {
		for (auto yaku : yakus) {
			if (yaku > Yaku::None && yaku < Yaku::一番) fan += 1;
			if (yaku > Yaku::一番 && yaku < Yaku::二番) fan += 2;
			if (yaku > Yaku::二番 && yaku < Yaku::三番) fan += 3;
			if (yaku > Yaku::三番 && yaku < Yaku::五番) fan += 5;
			if (yaku > Yaku::五番 && yaku < Yaku::六番) fan += 6;
		}
		if (fan >= 13) {
			// 累计役满
			fan = 13;
		}
		return fan;
	}

}

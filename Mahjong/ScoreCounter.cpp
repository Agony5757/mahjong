#include "ScoreCounter.h"
#include "Player.h"
#include "Table.h"
#include "Rule.h"
#include "macro.h"

using namespace std;

#define REGISTER_SCORE(oya, tsumo, score_oya_ron, score_oya_tsumo_all, score_kodomo_ron, score_kodomo_tsumo_oya, score_kodomo_tsumo_kodomo) \
if (oya) {if (tsumo){score1=score_oya_tsumo_all;} else{score1=score_oya_ron;}} \
else {if (tsumo) {score1=score_kodomo_tsumo_oya; score2=score_kodomo_tsumo_kodomo;} else{score1=score_kodomo_ron;}} return;

static vector<pair<vector<Yaku>, int>> get_yaku_from_complete_tiles(CompletedTiles ct, vector<CallGroup> CallGroups, Tile* correspond_tile, BaseTile tsumo_tile, Wind self_wind, Wind game_wind, bool& yakuman_flag);

int calculate_fan(vector<Yaku> yakus);

CounterResult yaku_counter(Table *table, Player &player, Tile *correspond_tile, bool chankan, bool chanankan, Wind self_wind, Wind game_wind)
{
	// 首先 假设进入到这个counter阶段的，至少满足了和牌条件的牌型
	// 以及，是否有某种役是不确定的

	// 从最简单的场役开始计算

	bool tsumo = (correspond_tile == nullptr);

	// 役 = 手役+场役+Dora。手役根据牌的解释不同而不同。
	vector<pair<vector<Yaku>, int>> yaku_fu_collection;
	CounterResult final_result;

	auto tiles = player.hand;
	if (correspond_tile != nullptr)
		tiles.push_back(correspond_tile);

	bool yakuman_flag = false;

	vector<Yaku> yaku_game_status; // involves yaku without considering one's hand
	vector<Yaku> yaku_dora;  // involves dora yaku

	/* 天地和的条件是，在第一巡，且没人鸣牌*/
	if (player.first_round) {
		if (table->oya == table->turn) {
			yaku_game_status.push_back(Yaku::Tenhou);
			yakuman_flag = true;
		}
		else {
			yaku_game_status.push_back(Yaku::Chihou);
			yakuman_flag = true;
		}
	}

	// 接下来统计国士无双&九莲（定牌型）

	if (tiles.size() == 14) {
		// 过滤一次门清条件
		do {
			if (is_kokushi_shape(convert_tiles_to_base_tiles(tiles))) {
				vector<Yaku> yakus;
				merge_into(yakus, yaku_game_status); // 也有可能与天和叠加
				bool is_13;
				// 判定13面
				{
					auto tiles = player.hand;
					if (correspond_tile == nullptr) tiles.pop_back();
					vector<BaseTile> raw
					{ _1m, _9m, _1s, _9s, _1p, _9p, _1z, _2z, _3z, _4z, _5z, _6z, _7z };

					sort(tiles.begin(), tiles.end());
					if (is_same_container(raw, convert_tiles_to_base_tiles(tiles)))
						is_13 = true;
					else is_13 = false;
				}
				if (is_13)
					yakus.push_back(Yaku::Koukushimusou_13);
				else
					yakus.push_back(Yaku::Kokushimusou);
				yaku_fu_collection.push_back({ yakus, 0 });
				yakuman_flag = true;
				break; // 等同于jump出去，因为国/九莲肯定牌型不同，不需要继续判断九莲了
			}

			// 九莲
			int mpsz_pure = tiles[0]->tile / 9;
			if (mpsz_pure >= 0 && mpsz_pure <= 2) {
				for (size_t i = 1; i < 14; ++i) {
					if (tiles[i]->tile / 9 != mpsz_pure) {
						// 清一色都不是
						mpsz_pure = -1;
						break;
					}
				}
			}
			if (mpsz_pure >= 0 && mpsz_pure <= 2) break;//不满足基本条件直接跳出 
			
			if (is_churen_9_agari(convert_tiles_to_base_tiles(tiles))) {
				vector<Yaku> yakus;
				merge_into(yakus, yaku_game_status); // 也有可能与天和叠加
				yakus.push_back(Yaku::Chuurenpoutou_9);
				yakuman_flag = true;
				yaku_fu_collection.push_back({ yakus, 0 });
			}
			else if (is_churen_agari(convert_tiles_to_base_tiles(tiles))) {
				vector<Yaku> yakus;
				merge_into(yakus, yaku_game_status); // 也有可能与天和叠加
				yakus.push_back(Yaku::Chuurenpoutou);
				yakuman_flag = true;
				yaku_fu_collection.push_back({ yakus, 0 });
			}
		} while (false);
	}

	// 接下来对牌进行拆解
	auto complete_tiles_list = get_completed_tiles(convert_tiles_to_base_tiles(tiles));

	{
		sort(complete_tiles_list.begin(), complete_tiles_list.end(),
			[](CompletedTiles c1, CompletedTiles c2) {
			return c1 < c2;
		});
		auto iter = unique(complete_tiles_list.begin(), complete_tiles_list.end());
		complete_tiles_list.erase(iter, complete_tiles_list.end());
	}
	// 接下来统计七对子
	if (is_7toitsu_shape(convert_tiles_to_base_tiles(tiles))) {
		// 即使是役满这里也要纳入考虑，因为存在大七星
		CompletedTiles ct;
		for (int i = 0; i < 14; i += 2) {
			TileGroup tg;
			tg.type = TileGroup::Toitsu;
			tg.set_tiles({ tiles[i]->tile, tiles[i]->tile });
			ct.body.push_back(tg);
		}
		complete_tiles_list.push_back(ct);
	}	

	for (auto &complete_tiles : complete_tiles_list) {
		auto yaku_fus = get_yaku_from_complete_tiles(complete_tiles, player.call_groups, correspond_tile, player.hand.back()->tile, self_wind, game_wind, yakuman_flag);
		merge_into(yaku_fu_collection, yaku_fus);
	}
	if (!yakuman_flag) { // 所有可能性中都没有役满的话

		/* riichi 和 double riichi 不重复计算 */
		if (player.double_riichi)
			yaku_game_status.push_back(Yaku::Dabururiichi);
		else if (player.riichi)
			yaku_game_status.push_back(Yaku::Riichi);

		/* 海底的条件是1. remain_tile == 0, 2. 上一手不是杠相关 */
		if (tsumo && table->get_remain_tile() == 0 &&
			table->last_action != BaseAction::AnKan &&
			table->last_action != BaseAction::Kan &&
			table->last_action != BaseAction::KaKan) {
			yaku_game_status.push_back(Yaku::Haiteiraoyue);
		}
		if (!tsumo && table->get_remain_tile() == 0) {
			yaku_game_status.push_back(Yaku::Houteiraoyu);
		}

		/* 如果是抢杠，那么计算抢杠 */
		if (chankan || chanankan) {
			yaku_game_status.push_back(Yaku::Chankan);
		}

		/* 如果上一轮动作是杠，这一轮是tsumo，那么就是岭上 */
		if (table->last_action == BaseAction::AnKan ||
			table->last_action == BaseAction::KaKan ||
			table->last_action == BaseAction::Kan) {
			if (tsumo) {
				yaku_game_status.push_back(Yaku::Rinshankaihou);
			}
		}

		/* 如果保存有ippatsu状态 */
		if (player.ippatsu) {
			yaku_game_status.push_back(Yaku::Ippatsu);
		}

		/*门清自摸*/
		if (tsumo && player.menzen) {
			yaku_game_status.push_back(Yaku::Menzentsumo);
		}

		// 接下来统计红宝牌数量
		for (auto tile : player.hand) {
			if (tile->red_dora == true) {
				yaku_dora.push_back(Yaku::Akadora);
			}
		}

		for (auto CallGroup : player.call_groups) {
			for (auto tile : CallGroup.tiles) {
				if (tile->red_dora == true) {
					yaku_dora.push_back(Yaku::Akadora);
				}
			}
		}

		if (correspond_tile && correspond_tile->red_dora == true) {
			yaku_dora.push_back(Yaku::Akadora);
		}

		// 接下来统计宝牌数量
		auto doratiles = table->get_dora();
		for (auto doratile : doratiles) {
			for (auto tile : player.hand) {
				if (tile->tile == doratile) {
					yaku_dora.push_back(Yaku::Dora);
				}
			}

			for (auto CallGroup : player.call_groups) {
				for (auto tile : CallGroup.tiles) {
					if (tile->tile == doratile) {
						yaku_dora.push_back(Yaku::Dora);
					}
				}
			}

			if (correspond_tile && correspond_tile->tile == doratile) {
				yaku_dora.push_back(Yaku::Dora);
			}
		}

		// 如果是立直和牌，继续统计里宝牌
		if (player.is_riichi()) {
			auto doratiles = table->get_ura_dora();
			for (auto doratile : doratiles) {
				for (auto tile : player.hand) {
					if (tile->tile == doratile) {
						yaku_dora.push_back(Yaku::Uradora);
					}
				}

				for (auto CallGroup : player.call_groups) {
					for (auto tile : CallGroup.tiles) {
						if (tile->tile == doratile) {
							yaku_dora.push_back(Yaku::Uradora);
						}
					}
				}

				if (correspond_tile && correspond_tile->tile == doratile) {
					yaku_dora.push_back(Yaku::Uradora);
				}
			}
		}		
	}
	for (auto& yaku_fu : yaku_fu_collection) {
		merge_into(yaku_fu.first, yaku_game_status);
		merge_into(yaku_fu.first, yaku_dora);
	}

	//对于AllYakusAndFu，判定番最高的，番相同的，判定符最高的	
	auto iter = max_element(yaku_fu_collection.begin(), yaku_fu_collection.end(), [](pair<vector<Yaku>, int> yaku_fu1, pair<vector<Yaku>, int> yaku_fu2) {
		auto fan1 = calculate_fan(yaku_fu1.first);
		auto fan2 = calculate_fan(yaku_fu2.first);
		if (fan1 < fan2) return true;
		if (fan1 > fan2) return false;
		// 如果番数一样则判断符
		return yaku_fu1.second < yaku_fu2.second;
	});

	if (iter == yaku_fu_collection.end()) {
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
		bool oya = false;
		if (table->oya == table->turn) oya = true;

		final_result.calculate_score(oya, tsumo);
	}
	return final_result;
}

void CounterResult::calculate_score(bool oya, bool tsumo)
{
	if (fan == 6 * 13) {
		// 6倍 役满
		REGISTER_SCORE(oya, tsumo, 48000 * 6, 16000 * 6, 32000 * 6, 16000 * 6, 8000 * 6);
	}
	else if (fan == 5 * 13) {
		// 5倍 役满
		REGISTER_SCORE(oya, tsumo, 48000 * 5, 16000 * 5, 32000 * 5, 16000 * 5, 8000 * 5);
	}
	else if (fan == 4 * 13) {
		// 4倍 役满		
		REGISTER_SCORE(oya, tsumo, 48000 * 4, 16000 * 4, 32000 * 4, 16000 * 4, 8000 * 4);
	}
	else if (fan == 3 * 13) {
		// 3倍 役满
		REGISTER_SCORE(oya, tsumo, 48000 * 3, 16000 * 3, 32000 * 3, 16000 * 3, 8000 * 3);
	}
	else if (fan == 2 * 13) {
		// 2倍 役满
		REGISTER_SCORE(oya, tsumo, 48000 * 2, 16000 * 2, 32000 * 2, 16000 * 2, 8000 * 2);
	}
	else if (fan >= 13) {
		// 役满
		REGISTER_SCORE(oya, tsumo, 48000, 16000, 32000, 16000, 8000);
	}
	else if (fan >= 11) {
		REGISTER_SCORE(oya, tsumo, 36000, 12000, 24000, 12000, 6000);
	}
	else if (fan >= 8) {
		REGISTER_SCORE(oya, tsumo, 24000, 8000 , 16000, 8000, 4000);
	}
	else if (fan >= 6) {
		REGISTER_SCORE(oya, tsumo, 18000, 6000 , 12000, 6000, 3000);
	}
	else if (fan == 5) {
		REGISTER_SCORE(oya, tsumo, 12000, 4000 , 8000, 4000, 2000);
	}
	else if (fan == 4) {
		// 40符以上满贯
		if (fu >= 40) {
			REGISTER_SCORE(oya, tsumo, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 30) {
			REGISTER_SCORE(oya, tsumo, 12000, 3900, 7700, 3900, 2000);
		}
		else if (fu == 25) {
			REGISTER_SCORE(oya, tsumo, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 20) {
			REGISTER_SCORE(oya, tsumo, 7700, 2600, 5200, 2600, 1300);
		}
	}
	else if (fan == 3) {
		// 70符以上满贯
		if (fu >= 70) {
			REGISTER_SCORE(oya, tsumo, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 60) {
			REGISTER_SCORE(oya, tsumo, 11600, 3900, 7700, 3900, 2000);
		}
		else if (fu == 50) {
			REGISTER_SCORE(oya, tsumo, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 40) {
			REGISTER_SCORE(oya, tsumo, 7700, 2600, 5200, 2600, 1300);
		}
		else if (fu == 30) {
			REGISTER_SCORE(oya, tsumo, 5800, 2000, 3900, 2000, 1000);
		}
		else if (fu == 25) {
			REGISTER_SCORE(oya, tsumo, 4800, 1600, 3200, 1600, 800);
		}
		else if (fu == 20) {
			REGISTER_SCORE(oya, tsumo, 3900, 1300, 2600, 1300, 700);
		}
	}
	else if (fan == 2) {
		if (fu >= 110) {
			REGISTER_SCORE(oya, tsumo, 10600, 3600, 7100, 3600, 1800);
		}
		else if (fu == 100) {
			REGISTER_SCORE(oya, tsumo, 9600, 3200, 6400, 3200, 1600);
		}
		else if (fu == 90) {
			REGISTER_SCORE(oya, tsumo, 8700, 2900, 5800, 2900, 1500);
		}
		else if (fu == 80) {
			REGISTER_SCORE(oya, tsumo, 7700, 2600, 5200, 2600, 1300);
		}
		else if (fu == 70) {
			REGISTER_SCORE(oya, tsumo, 6800, 2300, 4500, 2300, 1200);
		}
		else if (fu == 60) {
			REGISTER_SCORE(oya, tsumo, 5800, 2000, 3900, 2000, 1000);
		}
		else if (fu == 50) {
			REGISTER_SCORE(oya, tsumo, 4800, 1600, 3200, 1600, 800);
		}
		else if (fu == 40) {
			REGISTER_SCORE(oya, tsumo, 3900, 1300, 2600, 1300, 700);
		}
		else if (fu == 30) {
			REGISTER_SCORE(oya, tsumo, 2900, 1000, 2000, 1000, 500);
		}
		else if (fu == 25) {
			REGISTER_SCORE(oya, tsumo, 2400, -1, 1600, -1, -1);
		}
		else if (fu == 20) {
			REGISTER_SCORE(oya, tsumo, 2000, 700, 1300, 700, 400);
		}
	}
	else if (fan == 1) {
		if (fu >= 110) {
			REGISTER_SCORE(oya, tsumo, 5300, -1, 3600, -1, -1);
		}
		else if (fu == 100) {
			REGISTER_SCORE(oya, tsumo, 4800, 1600, 3200, 1600, 800);
		}
		else if (fu == 90) {
			REGISTER_SCORE(oya, tsumo, 4400, 1500, 2900, 1500, 800);
		}
		else if (fu == 80) {
			REGISTER_SCORE(oya, tsumo, 3900, 1300, 2600, 1300, 700);
		}
		else if (fu == 70) {
			REGISTER_SCORE(oya, tsumo, 3400, 1200, 2300, 1200, 600);
		}
		else if (fu == 60) {
			REGISTER_SCORE(oya, tsumo, 2900, 1000, 2000, 1000, 500);
		}
		else if (fu == 50) {
			REGISTER_SCORE(oya, tsumo, 2400, 800, 1600, 800, 400);
		}
		else if (fu == 40) {
			REGISTER_SCORE(oya, tsumo, 2000, 700, 1300, 700, 400);
		}
		else if (fu == 30) {
			REGISTER_SCORE(oya, tsumo, 1500, 500, 1000, 500, 300);
		}
		else if (fu == 20) {
			REGISTER_SCORE(oya, tsumo, 1000, -1, -1, -1, -1);
		}
	}
	stringstream ss;
	ss << "Error fan & fu cases." << fan << " fan, " << fu << " fu." << endl;
	throw runtime_error(ss.str().c_str());	
}

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

// 这个函数不判断：7对，国士无双及13面，九莲宝灯与纯正，所有宝牌役，所有场役包括天和，地和，立直，两立直，门清自摸，抢杠，海底，河底，ippatsu，岭上

static inline bool is_call(string s) {
	if (s.size() == 3) return false;
	if (s.size() == 4) return s[3] != '-';
	throw runtime_error("??");
}

static inline bool has_19(string s) {
	if (s[2] == 'K' || s[2] == ':' || s[2] == '|') return s[0] == '1' || s[0] == '9';
	if (s[2] == 'S') return s[0] == '1' || s[0] == '7';
	throw runtime_error("??");
}

static inline bool pure_19(string s) {
	if (s[2] == 'K' || s[2] == ':' || s[2] == '|') return s[0] == '1' || s[0] == '9';
	return false;
}

static inline bool pure_green(string s) {
	string first3(s.begin(), s.begin() + 3);

	static const char* green_types[] = {"2sK", "3sK", "4sK", "2sS", "6sK", "8sK", "6zK",
		"2s:", "3s:", "4s:", "6s:", "8s:", "6z:" };

	return is_in(green_types, first3);
}

static inline bool koutsu_19(string s) {
	if (s[2] == 'K' || s[2] == '|') {
		if (s[1] != 'z')
			return s[0] == '1' || s[0] == '9';
		else
			return true;
	}
	else {
		return false;
	}
}

static inline int is_yakuhai_toitsu(string s, Wind self_wind, Wind game_wind) {
	if (s[2] != ':') return 0; //不是对子

	int cases = 0;
	if (s[1] == 'z') {
		if ((s[0] - '1') == (int)self_wind) cases++;
		if ((s[0] - '1') == (int)game_wind) cases++;
		if ((s[0] - '0') >= 5) cases++;
	}
	return cases;
}

static inline vector<string> remove_4th_character(const vector<string> &strs) {
	vector<string> retstr(strs);
	for (auto &ret : retstr) {
		if (ret.size() == 4) ret.pop_back();
	}
	return retstr;
}

// 内部函数
inline static
pair<vector<Yaku>, int> get_yaku_from_complete_tiles(
	vector<string> tile_group_string, Wind self_wind, Wind game_wind) {

	vector<Yaku> yakus;
	yakus.reserve(16); // 随便分配一些空间以免后期重新分配
	int fu = 20;

#ifdef MAJ_DEBUG
	{
		cout << "DEBUG_MODE: TILE_GROUP_STRING" << endl;
		for (auto tgs : tile_group_string)
			cout << tgs << " ";
		cout << endl;
	}
#endif

	// 判断单骑
	bool tanki = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string &s) {
		if (s.size() == 3) return false;
		if (s.size() == 4) return s[2] == ':';
		throw runtime_error("??");
	});

	// 判断门清
	bool menzen = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s.size() == 3) return true;
		if (s.size() == 4) return s[3] != '-';
		throw runtime_error("??");
	});

	// 判断7对
	if (tile_group_string.size() == 7) {
		yakus.push_back(Yaku::Chiitoitsu);
	}

	// 判断有没有顺子
	bool has_shuntsu = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[2] == 'S') return true;
		else return false;
	});
	if (!has_shuntsu && tile_group_string.size() != 7) {
		yakus.push_back(Yaku::Toitoiho);
	}

	// 判断是不是断幺九
	bool tanyao = none_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'z') return true;
		return has_19(s);
	});

	if (tanyao) yakus.push_back(Yaku::Tanyao);

	// 统计Z一色
	bool tsuiisou = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'z') return true;
		return false;
	});
	// 计算字一色
	if (tsuiisou) yakus.push_back(Yaku::Tsuiisou);

	// 统计P清一色
	bool p_chinitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'p') return true;
		return false;
	});
	bool p_honitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'p' || s[1] == 'z') return true;
		return false;
	});

	// 统计m清一色
	bool m_chinitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'm') return true;
		return false;
	});
	bool m_honitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'm' || s[1] == 'z') return true;
		return false;
	});

	// 统计S清一色
	bool s_chinitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 's') return true;
		return false;
	});
	bool s_honitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 's' || s[1] == 'z') return true;
		return false;
	});

	// 计算清一色
	if (s_chinitsu || m_chinitsu || p_chinitsu) {
		if (menzen) yakus.push_back(Yaku::Chinitsu);
		else yakus.push_back(Yaku::Chinitsu_Naki);
	}
	else {
		// 计算混一色
		if (s_honitsu || m_honitsu || p_honitsu) {
			if (menzen) yakus.push_back(Yaku::Honitsu);
			else yakus.push_back(Yaku::Honitsu_Naki);
		}
	}
	
	// 统计所有的字牌刻子和对子
	bool koutsu_z[7] = { false };
	bool toitsu_z[7] = { false };
	for_each(tile_group_string.begin(), tile_group_string.end(), [&koutsu_z, &toitsu_z](const string& s) {
		if (s[1] == 'z') {
			if (s[2] == 'K' || s[2] == '|') {
				koutsu_z[s[0] - '1'] = true;
			}
			if (s[2] == ':') {
				toitsu_z[s[0] - '1'] = true;
			}
		}
	});

	// 统计暗刻数
	int num_ankou = 0;
	for_each(tile_group_string.begin(), tile_group_string.end(), [&num_ankou](const string& s) {
		if (s.size() == 3 && s[2] == 'K') {
			num_ankou++;
		}
		else if (s.size() == 4 && s[2] == 'K' && (s[3] == '!' || s[3] == '@' || s[3] == '#')) {
			num_ankou++;
		}
		else if (s[2] == '|' && s[3] == '+') {
			num_ankou++;
		}
	});
	if (num_ankou == 4) {
		if (tanki) yakus.push_back(Yaku::Siiankou_1);
		else yakus.push_back(Yaku::Siiankou);
	}
	else if (num_ankou == 3) {
		yakus.push_back(Yaku::Sanankou);
	}

	// 统计杠子数
	int num_kantsu = 0;
	for_each(tile_group_string.begin(), tile_group_string.end(), [&num_kantsu](const string& s) {
		if (s[2] == '|') {
			num_kantsu++;
		}
	});
	if (num_kantsu == 4) {
		yakus.push_back(Yaku::Siikantsu);
	}
	else if (num_kantsu == 3) {
		yakus.push_back(Yaku::Sankantsu);
	}

	// 判断清老头混老头
	bool chinroutou = true;
	bool honroutou = true;
	for_each(tile_group_string.begin(), tile_group_string.end(), [&chinroutou, &honroutou](const string& s) {
		if (s[1] == 'z') {
			chinroutou = false;
			return;
		}
		if (!pure_19(s)) {
			chinroutou = false;
			honroutou = false;
		}
	});

	if (chinroutou) {
		yakus.push_back(Yaku::Chinroutou);
	}
	else if (honroutou) {
		yakus.push_back(Yaku::Honroutou);
	}

	// 统计幺九状态
	bool junchan = true;
	bool chanta = true;
	for_each(tile_group_string.begin(), tile_group_string.end(), [&junchan, &chanta](const string& s) {
		if (s[1] == 'z') {
			junchan = false;
			return;
		}
		if (!has_19(s)) {
			junchan = false;
			chanta = false;
		}
	});

	if (junchan && !chinroutou) {
		if (menzen) yakus.push_back(Yaku::Junchantaiyaochu);
		else yakus.push_back(Yaku::Junchantaiyaochu_Naki);
	}
	else if (chanta && !honroutou) {
		if (menzen) yakus.push_back(Yaku::Honchantaiyaochu);
		else yakus.push_back(Yaku::Honchantaiyaochu_Naki);
	}

	// 大三元及小三元
	if (koutsu_z[4] && koutsu_z[5] && koutsu_z[6]) {
		yakus.push_back(Yaku::Daisangen);
	}
	else {
		if (koutsu_z[4] && koutsu_z[5] && toitsu_z[6]) {
			yakus.push_back(Yaku::Shousangen);
		}
		if (koutsu_z[4] && toitsu_z[5] && koutsu_z[6]) {
			yakus.push_back(Yaku::Shousangen);
		}
		if (toitsu_z[4] && koutsu_z[5] && koutsu_z[6]) {
			yakus.push_back(Yaku::Shousangen);
		}
	}

	// 大四喜及小四喜
	if (koutsu_z[0] && koutsu_z[1] && koutsu_z[2] && koutsu_z[3]) {
		yakus.push_back(Yaku::Daisuushi);
	}
	else {
		if (toitsu_z[0] && koutsu_z[1] && koutsu_z[2] && koutsu_z[3]) {
			yakus.push_back(Yaku::Shousuushi);
		}
		if (koutsu_z[0] && toitsu_z[1] && koutsu_z[2] && koutsu_z[3]) {
			yakus.push_back(Yaku::Shousuushi);
		}
		if (koutsu_z[0] && koutsu_z[1] && toitsu_z[2] && koutsu_z[3]) {
			yakus.push_back(Yaku::Shousuushi);
		}
		if (koutsu_z[0] && koutsu_z[1] && koutsu_z[2] && toitsu_z[3]) {
			yakus.push_back(Yaku::Shousuushi);
		}
	}

	// 判断役牌
	if (koutsu_z[4])
		yakus.push_back(Yaku::Yakuhai_Haku);
	if (koutsu_z[5])
		yakus.push_back(Yaku::Yakuhai_Hatsu);
	if (koutsu_z[6])
		yakus.push_back(Yaku::Yakuhai_Chu);

	if (game_wind == Wind::East)
		if (koutsu_z[0]) yakus.push_back(Yaku::Bakaze_Ton);
	if (game_wind == Wind::South)
		if (koutsu_z[1]) yakus.push_back(Yaku::Bakaze_Nan);
	if (game_wind == Wind::West)
		if (koutsu_z[2]) yakus.push_back(Yaku::Bakaze_Sha);
	if (game_wind == Wind::North)
		if (koutsu_z[3]) yakus.push_back(Yaku::Bakaze_Pei);

	if (self_wind == Wind::East)
		if (koutsu_z[0]) yakus.push_back(Yaku::Jikaze_Ton);
	if (self_wind == Wind::South)
		if (koutsu_z[1]) yakus.push_back(Yaku::Jikaze_Nan);
	if (self_wind == Wind::West)
		if (koutsu_z[2]) yakus.push_back(Yaku::Jikaze_Sha);
	if (self_wind == Wind::North)
		if (koutsu_z[3]) yakus.push_back(Yaku::Jikaze_Pei);

	// 判断平和
	bool pinfu = true;

	pinfu &= menzen;
	pinfu &= (!tanki);

	// 对子不是役牌
	pinfu &= none_of(tile_group_string.begin(), tile_group_string.end(), [&self_wind, &game_wind](const string& s) {
		return is_yakuhai_toitsu(s, self_wind, game_wind);
	});

	// 对子 顺子
	pinfu &= all_of(tile_group_string.begin(), tile_group_string.end(), [&self_wind, &game_wind](const string& s) {
		if (s[2] == ':') return true;
		if (s[2] == 'S') return true;
		return false;
	});

	// 和牌型
	pinfu &= all_of(tile_group_string.begin(), tile_group_string.end(), [&self_wind, &game_wind](const string &s) {
		if (s.size() == 3) return true;
		if (s[3] == '@') return false;
		if (s[3] == '%') return false;
		if (s[2] == ':' && s[3] == '$') return false;
		if ((s[3] == '#' || s[3] == '^') && s[0] == '1') return false;
		if ((s[3] == '!' || s[3] == '$') && s[0] == '7') return false;
		return true;
	});
    pinfu &= tile_group_string.size() == 5;
	if (pinfu) yakus.push_back(Yaku::Pinfu);

	// 判断绿一色
	bool ryuiisou = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return pure_green(s);
	});
	if (ryuiisou) yakus.push_back(Yaku::Ryuiisou);

	auto tile_group_string_first_three = remove_4th_character(tile_group_string);

	// 判断三色同顺
	bool sanshoku = false;
	const static string sanshoku_all_options[] =
	{
	  "1mS","2mS","3mS","4mS","5mS","6mS","7mS",
	  "1pS","2pS","3pS","4pS","5pS","6pS","7pS",
	  "1sS","2sS","3sS","4sS","5sS","6sS","7sS",
	};
	for (int i = 0; i < 7; ++i) {
		if (is_in(tile_group_string_first_three, sanshoku_all_options[i]) &&
			is_in(tile_group_string_first_three, sanshoku_all_options[i + 7]) &&
			is_in(tile_group_string_first_three, sanshoku_all_options[i + 14])) {
			sanshoku = true;
			break;
		}
	}
	if (sanshoku) {
		if (menzen) yakus.push_back(Yaku::Sanshokudoujun);
		else yakus.push_back(Yaku::Sanshokudoujun_Naki);
	}

	// 判断三色同刻
	bool sanshokudoukou = false;
	const static string sanshokudoukou_all_options[] =
	{ 
	  "1mK","2mK","3mK","4mK","5mK","6mK","7mK","8mK","9mK",
	  "1pK","2pK","3pK","4pK","5pK","6pK","7pK","8pK","9pK",
	  "1sK","2sK","3sK","4sK","5sK","6sK","7sK","8sK","9sK",
	};
	for (int i = 0; i < 9; ++i) {
		if (is_in(tile_group_string_first_three, sanshokudoukou_all_options[i]) &&
			is_in(tile_group_string_first_three, sanshokudoukou_all_options[i + 9]) &&
			is_in(tile_group_string_first_three, sanshokudoukou_all_options[i + 18])) {
			sanshokudoukou = true;
			break;		
		}
	}
	if (sanshokudoukou) yakus.push_back(Yaku::Sanshokudoukou);

	// 判断一气通贯	
	bool ikki = false;
	const static string m_ikki[] = { "1mS", "4mS", "7mS" };
	const static string p_ikki[] = { "1pS", "4pS", "7pS" };
	const static string z_ikki[] = { "1sS", "4sS", "7sS" };
	
	// avoid using includes: it may only apply on an ordered sequence
	//一气通贯 |= includes(tile_group_string_no_4.begin(), tile_group_string_no_4.end(),
	//	一气通贯S.begin(), 一气通贯S.end());
	//一气通贯 |= includes(tile_group_string_no_4.begin(), tile_group_string_no_4.end(),
	//	一气通贯M.begin(), 一气通贯M.end());
	//一气通贯 |= includes(tile_group_string_no_4.begin(), tile_group_string_no_4.end(),
	//	一气通贯P.begin(), 一气通贯P.end());

	ikki |= all_of(begin(m_ikki), end(m_ikki),
		[&tile_group_string_first_three](string tiles) {return is_in(tile_group_string_first_three, tiles); });
	ikki |= all_of(begin(p_ikki), end(p_ikki),
		[&tile_group_string_first_three](string tiles) {return is_in(tile_group_string_first_three, tiles); });
	ikki |= all_of(begin(z_ikki), end(z_ikki),
		[&tile_group_string_first_three](string tiles) {return is_in(tile_group_string_first_three, tiles); });

	if (ikki) {
		if (menzen) yakus.push_back(Yaku::Ikkitsuukan);
		else yakus.push_back(Yaku::Ikkitsuukan_Naki);
	}

	static const string shuntsu[] = {
		"1mS", "2mS" ,"3mS" ,"4mS" ,"5mS" ,"6mS" ,"7mS",
		"1pS", "2pS" ,"3pS" ,"4pS" ,"5pS" ,"6pS" ,"7pS",
		"1sS", "2sS" ,"3sS" ,"4sS" ,"5sS" ,"6sS" ,"7sS"
	};
	// 判断二杯口 && 一杯口
	int n_peikou = 0;
	if (menzen) {
		for (const string &tiles : shuntsu) {
		    if (count_if(tile_group_string_first_three.begin(), 
		                 tile_group_string_first_three.end(),
						 [&tiles](const string &s) {return s == tiles;})
						 >= 2) n_peikou++;
						
		}
	}

	if (n_peikou == 2) yakus.push_back(Yaku::Rianpeikou);
	else if (n_peikou == 1) yakus.push_back(Yaku::Ippeikou);

	// 计算符数

	// 听牌型
	if (tanki) fu += 2;
	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 坎张
		if (s.size() == 4)
			if (s[2] == 'S' && (s[3] == '@' || s[3] == '%'))
				return true;
		return false;
	})) 
		fu += 2;

	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 边张
		if (s.size() == 4 && s[2] == 'S') {
			if (s[0] == '1') if (s[3] == '#' || s[3] == '^') return true;
			if (s[0] == '7') if (s[3] == '!' || s[3] == '$') return true;
		}
		return false;
	}))
		fu += 2;

	// 和了方式
	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 自摸
		if (s.size() == 4) {
			if (s[3] == '!' || s[3] == '@' || s[3] == '#') return true;
		}
		return false;
	}) && !pinfu)
		fu += 2;

	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 荣和
		if (s.size() == 4) {
			if (s[3] == '$' || s[3] == '%' || s[3] == '^') return true;
		}
		return false;
	}) && menzen)
		fu += 10;

	// 雀头符
	for_each(tile_group_string.begin(), tile_group_string.end(), [&fu, &self_wind, &game_wind](const string &s) {
		// 荣和
		fu += (is_yakuhai_toitsu(s, self_wind, game_wind) * 2);
	});

	//面子符

	// string s;
	// for (auto ts : tile_group_string)
	// {
	// 	s += ts;
	// 	s += " ";
	// }

	// printf("%s\n", s.c_str());

	for_each(tile_group_string.begin(), tile_group_string.end(), [&fu](const string& s) {
		if (s.size() == 3 && s[2] == 'K') { 
			if (koutsu_19(s)) fu += 8; 
			else fu += 4;			
		}
		if (s.size() == 4) {
			switch (s[2]) {
			case 'S':
				break;
			case 'K':
				switch (s[3]) {
				case '!':
				case '@':
				case '#':
					if (koutsu_19(s)) fu += 8;
					else fu += 4;
					break;
				case '$':
				case '%':
				case '^':
				case '-':
					if (koutsu_19(s)) fu += 4;
					else fu += 2;
					break;
				}
				break;
			case '|':
				if (s[3] == '-') {
					if (koutsu_19(s)) fu += 16;
					else fu += 8;
				}
				else if (s[3] == '+') {
					if (koutsu_19(s)) fu += 32;
					else fu += 16;
				}
			}
		}
	});

	// 副露平和型，前面应该一定是20符
	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 荣和
		if (s.size() == 4) {
			if (s[3] == '$' || s[3] == '%' || s[3] == '^') return true;
		}
		return false;
	}) && (!menzen)) {
		if (fu == 20) fu = 30;
	}

	// 自摸平和 20符
	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 自摸
		if (s.size() == 4) {
			if (s[3] == '!' || s[3] == '@' || s[3] == '#') return true;
		}
		return false;
	}) && (pinfu)) {
		fu = 20;
	}

	if (fu % 10 != 0) {
		fu = (fu / 10) * 10 + 10;
	}

	// 注意七对子统一25符，并且不跳符。
	if (tile_group_string.size() == 7) {
		fu = 25;
	}

	return { yakus, fu };
}

vector<pair<vector<Yaku>, int>> get_yaku_from_complete_tiles(
	CompletedTiles ct, vector<CallGroup> CallGroups, Tile *correspond_tile, BaseTile tsumo_tile, Wind self_wind, Wind game_wind, bool& yakuman_flag)
{
	bool tsumo = false;	 // 是自摸吗
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
	
	std::vector<std::vector<std::string>> tile_group_strings;	
	std::vector<std::string> raw_tile_group_string;

	if (ct.head.tiles.size() != 0)
		raw_tile_group_string.push_back(basetile_to_string(ct.head.tiles[0]) + ":"); //例如1z2
	else if (ct.body.size() != 7)
		throw runtime_error("Unknown CompletedTiles Setting. No Head and Not 7-toitsu");
	else // 七对的情况（即没有雀头，BODY_SIZE正好为7）
	{
		for (int i = 0; i < 7; ++i) {
			raw_tile_group_string.push_back(basetile_to_string(ct.body[i].tiles[0]) + ":");
		}
	}

	for (auto CallGroup : CallGroups) {
		switch (CallGroup.type) {
		case CallGroup::Chi:
			raw_tile_group_string.push_back(basetile_to_string(CallGroup.tiles[0]->tile) + "S-"); // 例如1sS- 即1s2s3s (8sS无效)
			continue;
		case CallGroup::Pon:
			raw_tile_group_string.push_back(basetile_to_string(CallGroup.tiles[0]->tile) + "K-"); // 例如1sK- 即1s1s1s
			continue;
		case CallGroup::DaiMinKan:
		case CallGroup::KaKan:
			raw_tile_group_string.push_back(basetile_to_string(CallGroup.tiles[0]->tile) + "|-"); // 例如3z4- 即西大明杠/加杠
			continue;
		case CallGroup::AnKan:
			raw_tile_group_string.push_back(basetile_to_string(CallGroup.tiles[0]->tile) + "|+"); // 例如4s4+ 即4s暗杠
			continue;
		}
	}
	for (auto tilegroup : ct.body) {
		switch (tilegroup.type) {
		case TileGroup::Shuntsu:
			raw_tile_group_string.push_back(basetile_to_string(tilegroup.tiles[0]) + "S"); //例如1sS
			continue;
		case TileGroup::Koutsu:
			raw_tile_group_string.push_back(basetile_to_string(tilegroup.tiles[0]) + "K"); // 例如1sK
			continue;
		default:
			continue;
		}
	}

	// last_tile是否存在于tile_group中
	string last_tile_string = basetile_to_string(last_tile);
	for (auto &tile_group : raw_tile_group_string) {
		auto attr = tile_group.back(); // 最后一个字符表示它的性质
		if (attr == '-' || attr == '+') {
			continue;
		}
		if (attr == 'K' || attr == ':') {
			if (tile_group[0] == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += '!'; 
				else tile_group += '$';
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
				continue;
			}
			else continue;
		}
		if (attr == 'S') {
			if (tile_group[0] == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += '!';
				else tile_group += '$';
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
				continue;
			}
			else if ((tile_group[0] + 1) == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += '@';
				else tile_group += '%';
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
				continue;
			}
			else if ((tile_group[0] + 2) == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += '#';
				else tile_group += '^';
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
				continue;
			}
			else continue;
		}
		else continue;
	}

	// 消去tile_group_strings中完全相同的元素

	sort(tile_group_strings.begin(), tile_group_strings.end());
	auto iter = unique(tile_group_strings.begin(), tile_group_strings.end());
	tile_group_strings.erase(iter, tile_group_strings.end());

	for (auto tile_group : tile_group_strings) {
		auto yaku_fu = get_yaku_from_complete_tiles(tile_group, self_wind, game_wind);
		yaku_fus.push_back(yaku_fu);		
	}
	return yaku_fus;
}

int calculate_fan(vector<Yaku> yakus)
{
	bool yakuman = false;
	for (auto yaku : yakus) {
		if (yaku > Yaku::Yaku_mangan && yaku < Yaku::Yakuman_Double) {
			yakuman = true;
			break;
		}
	}
	int fan = 0;
	if (yakuman) {
		for (auto yaku : yakus) {
			if (yaku < Yaku::Yaku_mangan) continue; // 跳过所有不是役满的
			if (yaku > Yaku::Yaku_mangan && yaku < Yaku::Yakuman) fan += 13;
			if (yaku > Yaku::Yakuman && yaku < Yaku::Yakuman_Double) fan += 26;
		}
		return fan;
	}
	else {
		for (auto yaku : yakus) {
			if (yaku > Yaku::None && yaku < Yaku::Yaku_1_han) fan += 1;
			if (yaku > Yaku::Yaku_1_han && yaku < Yaku::Yaku_2_han) fan += 2;
			if (yaku > Yaku::Yaku_2_han && yaku < Yaku::Yaku_3_han) fan += 3;
			if (yaku > Yaku::Yaku_3_han && yaku < Yaku::Yaku_5_han) fan += 5;
			if (yaku > Yaku::Yaku_5_han && yaku < Yaku::Yaku_6_han) fan += 6;
		}
		if (fan >= 13) {
			// 累计役满
			fan = 13;
		}
		return fan;
	}

}

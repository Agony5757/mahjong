#include "ScoreCounter.h"
#include "Player.h"
#include "Table.h"
#include "Rule.h"
#include "macro.h"

namespace_mahjong
using namespace std;

#define REGISTER_SCORE(oya, tsumo, score_oya, score_oya_tsumo_all, score_kodomo, score_kodomo_tsumo_oya, score_kodomo_tsumo_kodomo) \
if (oya) {if (tsumo){score1=score_oya_tsumo_all;} else{score1=score_oya;}} \
else {if (tsumo) {score1=score_kodomo_tsumo_oya; score2=score_kodomo_tsumo_kodomo;} else{score1=score_kodomo;}} return;

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
		REGISTER_SCORE(oya, tsumo, 24000, 8000, 16000, 8000, 4000);
	}
	else if (fan >= 6) {
		REGISTER_SCORE(oya, tsumo, 18000, 6000, 12000, 6000, 3000);
	}
	else if (fan == 5) {
		REGISTER_SCORE(oya, tsumo, 12000, 4000, 8000, 4000, 2000);
	}
	else if (fan == 4) {
		// 40符以上满贯
		if (fu >= 40) {
			REGISTER_SCORE(oya, tsumo, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 30) {
			REGISTER_SCORE(oya, tsumo, 11600, 3900, 7700, 3900, 2000);
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
	throw runtime_error(fmt::format("Error fan & fu cases. {} fan {} fu.", fan, fu));
}

int calculate_fan(const vector<Yaku> &yakus)
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


static std::string make_tilegroup(BaseTile t, char mark);
static std::string make_tilegroup(BaseTile t, char mark1, char mark2);
inline static std::string make_toitsu(BaseTile t) { return make_tilegroup(t, mark_toitsu); }
inline static std::string make_shuntsu(BaseTile t) { return make_tilegroup(t, mark_shuntsu); }
inline static std::string make_shuntsu_fuuro(BaseTile t) { return make_tilegroup(t, mark_shuntsu, mark_fuuro); }
inline static std::string make_koutsu(BaseTile t) { return make_tilegroup(t, mark_koutsu); }
inline static std::string make_koutsu_fuuro(BaseTile t) { return make_tilegroup(t, mark_koutsu, mark_fuuro); }
inline static std::string make_ankan(BaseTile t) { return make_tilegroup(t, mark_kantsu, mark_ankan); }
inline static std::string make_minkan(BaseTile t) { return make_tilegroup(t, mark_kantsu, mark_minkan); }

inline static bool is_shuntsu_str(const std::string& s) { return s[2] == 'S'; }
inline static bool is_koutsu_str(const std::string& s) { return s[2] == 'K'; }
inline static bool is_kantsu_str(const std::string& s) { return s[2] == '|'; }
inline static bool is_minkan_str(const std::string& s) { return s.size() == 4 && s[2] == '|' && s[3] == '-'; }
inline static bool is_minkou_str(const std::string& s) { return s.size() == 4 && s[2] == 'K' && s[3] == '-'; }
inline static bool is_minshun_str(const std::string& s) { return s.size() == 4 && s[2] == 'S' && s[3] == '-'; }
inline static bool is_ankan_str(const std::string& s) { return s.size() == 4 && s[2] == '|' && s[3] == '+'; }
inline static bool tile_group_match(const std::string& s1, const std::string& s2) { return s1[0] == s2[0] && s1[1] == s2[1] && s1[2] == s2[2]; }

/* 牌型对/顺/刻/杠，含字牌 */
inline static bool is_z_str(const std::string& s) { return s[1] == 'z'; }

/* 牌型对/顺/刻/杠，含至少1张幺九，不包括字牌，例如789s 1111m */
inline static bool is_yaochu_str(const std::string& s) {
	if (is_z_str(s)) return false;
	if (s[2] == 'K' || s[2] == ':' || s[2] == '|') return s[0] == '1' || s[0] == '9';
	if (s[2] == 'S') return s[0] == '1' || s[0] == '7';
	throw std::runtime_error(fmt::format("Bad tile group string (input = {})", s));
}

/* 牌型对/刻/杠，全幺九，不包括字牌，例如999p 1111m */
inline static bool pure_yaochu_str(const std::string& s) {
	bool no_shuntsu = (s[2] == 'K' || s[2] == ':' || s[2] == '|');
	bool all_19 = (s[0] == '1' || s[0] == '9');
	bool no_z = (!is_z_str(s));
	return no_shuntsu && all_19 && no_z;
}

/* 全绿牌 */
inline static bool pure_green_str(const std::string& s) {
	const char* green_types[] = { 
		"2sK", "3sK", "4sK",  /* 222s 333s 444s */
		"6sK", "8sK", "6zK",  /* 666s 888s 666z */
		"2sS", /* 234s */
		"2s:", "3s:", "4s:", "6s:", "8s:", "6z:", /* 2s2s, 3s3s, 4s4s, 6s6s, 8s8s, 6z6z */
		"2s|", "3s|", "4s|", "6s|", "8s|", "6z|", /* 2222s, 3333s, 4444s, 6666s, 8888s, 6666z */
	};

	return std::any_of(begin(green_types), end(green_types),
		[&s](const char* green) {return tile_group_match(s, green); });
}

/* 用于处理全带，不包括杠子 */
inline static bool has_yaochu_or_z_str(const std::string& s) { return is_z_str(s) || is_yaochu_str(s); }

/* 用于记符，对于役牌对子的计数，包括连风对子 */
inline static int is_yakuhai_toitsu(const std::string &s, Wind self_wind, Wind game_wind) {
	if (s[2] != ':') return 0; //不是对子
	if (s[1] != 'z') return 0; //不是字牌

	int cases = 0;
	int number = s[0] - '1'; // 0 1 2 3分别为东南西北
	if (number == self_wind) cases++;
	if (number == game_wind) cases++;
	if (number >= 4) cases++; // 4,5,6为白发中
	return cases;
}

string make_tilegroup(BaseTile t, char mark)
{
	string ret;	ret.reserve(4);
	const char* tile_str = basetile_to_string(t);
	ret.push_back(tile_str[0]); ret.push_back(tile_str[1]);
	ret.push_back(mark);
	return ret;
};

string make_tilegroup(BaseTile t, char mark1, char mark2)
{
	string ret;	ret.resize(4);
	const char* tile_str = basetile_to_string(t);
	ret[0] = tile_str[0]; ret[1] = tile_str[1];
	ret[2] = mark1; ret[3] = mark2;
	return ret;
};

vector<vector<string>> ScoreCounter::generate_tile_group_strings(const CompletedTiles &ct, const vector<CallGroup> &callgroups, bool tsumo, BaseTile last_tile)
{
	profiler _("ScoreCounter.cpp/generate_tgs");
	vector<vector<string>> tile_group_strings;
	vector<string> raw_tile_group_string; // without consider where is the agari tile.	  

	if (ct.head.tiles.size() != 0)
		raw_tile_group_string.push_back(make_toitsu(ct.head.tiles[0])); //例如1z2
	else if (ct.body.size() != 7)
		throw runtime_error("Unknown CompletedTiles object. No Head and not 7-toitsu");
	else // 七对的情况（即没有雀头，BODY_SIZE正好为7）
	{
		for (int i = 0; i < 7; ++i) {
			raw_tile_group_string.push_back(make_toitsu(ct.body[i].tiles[0]));
		}
	}

	for (auto callgroup : callgroups) {
		switch (callgroup.type) {
		case CallGroup::Chi:
			raw_tile_group_string.push_back(make_shuntsu_fuuro(callgroup.tiles[0]->tile)); // 例如1sS- 即1s2s3s (8sS无效)
			continue;
		case CallGroup::Pon:
			raw_tile_group_string.push_back(make_koutsu_fuuro(callgroup.tiles[0]->tile)); // 例如1sK- 即1s1s1s
			continue;
		case CallGroup::DaiMinKan:
		case CallGroup::KaKan:
			raw_tile_group_string.push_back(make_minkan(callgroup.tiles[0]->tile)); // 例如3z4- 即西大明杠/加杠
			continue;
		case CallGroup::AnKan:
			raw_tile_group_string.push_back(make_ankan(callgroup.tiles[0]->tile)); // 例如4s4+ 即4s暗杠
			continue;
		}
	}
	for (auto tilegroup : ct.body) {
		switch (tilegroup.type) {
		case TileGroup::Shuntsu:
			raw_tile_group_string.push_back(make_shuntsu(tilegroup.tiles[0])); //例如1sS
			continue;
		case TileGroup::Koutsu:
			raw_tile_group_string.push_back(make_koutsu(tilegroup.tiles[0])); // 例如1sK
			continue;
		default:
			continue;
		}
	}

	// last_tile是否存在于tile_group中
	string last_tile_string = basetile_to_string(last_tile);
	for (auto &tile_group : raw_tile_group_string) {
		auto &attr = tile_group.back(); // 最后一个字符表示它的性质

		// 只考虑在手牌中的情况，所以说最后一个必须是:SK之一，其他情况略过
		if (attr == mark_koutsu || attr == mark_toitsu) {
			if (tile_group[0] == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += mark_tsumo_1st;
				else tile_group += mark_ron_1st;
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
			}
		}
		else if (attr == mark_shuntsu) {
			// 例如7sS
			// 胡7s进入第一个情况，胡8s进入第二个情况，胡9s进入第三个情况
			if (tile_group[0] == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += mark_tsumo_1st;
				else tile_group += mark_ron_1st;
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
			}
			else if ((tile_group[0] + 1) == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += mark_tsumo_2nd;
				else tile_group += mark_ron_2nd;
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
			}
			else if ((tile_group[0] + 2) == last_tile_string[0] && tile_group[1] == last_tile_string[1]) {
				if (tsumo) tile_group += mark_tsumo_3rd;
				else tile_group += mark_ron_3rd;
				tile_group_strings.push_back(raw_tile_group_string);
				tile_group.pop_back();
			}
		}
	}

	// 消去tile_group_strings中完全相同的元素

	sort(tile_group_strings.begin(), tile_group_strings.end());
	auto iter = unique(tile_group_strings.begin(), tile_group_strings.end());
	tile_group_strings.erase(iter, tile_group_strings.end());

	return tile_group_strings;
}

/* 移除副露、胡牌等信息，创建复制 */
static inline vector<string> remove_4(const vector<string> &strs) {
	vector<string> retstr(strs);

	for (auto &ret : retstr) {
		if (ret.size() == 4) ret.pop_back();
		if (ret[2] == '|') ret[2] = 'K';		
	}
	return retstr;
}

vector<Yaku> ScoreCounter::get_hand_yakuman(const vector<string> &tile_group_string, Wind self_wind, Wind game_wind, bool &yakuman) {
	vector<Yaku> yakus;
	
	// 统计Z一色
	bool z_pure_type = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return is_z_str(s);
		});	

	// 统计所有的字牌刻子和对子
	bool z_koutsu[7] = { false };
	bool z_toitsu[7] = { false };
	for_each(tile_group_string.begin(), tile_group_string.end(), [&z_koutsu, &z_toitsu](const string& s) {
		if (s[1] == 'z') {
			if (s[2] == 'K' || s[2] == '|') {
				z_koutsu[s[0] - '1'] = true;
			}
			if (s[2] == ':') {
				z_toitsu[s[0] - '1'] = true;
			}
		}
	});
	
	// 判断单骑
	bool call_single = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string &s) {
		return s[2] == ':' && s.size() == 4; // 表示涉及到胡牌的对子
		});

	// 统计暗刻数
	int num_ankou = count_if(tile_group_string.begin(), tile_group_string.end(), [&num_ankou](const string& s) {
		return (s.size() == 3 && s[2] == 'K') ||
			(s.size() == 4 && s[2] == 'K' && (s[3] == '!' || s[3] == '@' || s[3] == '#')) ||
			(s[2] == '|' && s[3] == '+');
		});

	// 统计杠子数
	int num_kantsu = count_if(tile_group_string.begin(), tile_group_string.end(), [](const string& s) { return s[2] == '|'; });

	// 判断清老头混老头
	bool chinroutou = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return pure_yaochu_str(s); 
	});

	// 判断绿一色
	bool pure_green = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return pure_green_str(s);
		});

	/* 开始判定 */

	if (z_pure_type) {
		yakus.push_back(Yaku::Tsuiisou);
		yakuman = true;
	}

	if (z_koutsu[4] && z_koutsu[5] && z_koutsu[6]) {
		yakus.push_back(Yaku::Daisangen);
		yakuman = true;
	}

	if (z_koutsu[0] && z_koutsu[1] && z_koutsu[2] && z_koutsu[3]) {
		yakus.push_back(Yaku::Daisuushi);
		yakuman = true;
	}
	else {
		if (z_toitsu[0] && z_koutsu[1] && z_koutsu[2] && z_koutsu[3]) {
			yakus.push_back(Yaku::Shousuushi);
			yakuman = true;
		}
		if (z_koutsu[0] && z_toitsu[1] && z_koutsu[2] && z_koutsu[3]) {
			yakus.push_back(Yaku::Shousuushi);
			yakuman = true;
		}
		if (z_koutsu[0] && z_koutsu[1] && z_toitsu[2] && z_koutsu[3]) {
			yakus.push_back(Yaku::Shousuushi);
			yakuman = true;
		}
		if (z_koutsu[0] && z_koutsu[1] && z_koutsu[2] && z_toitsu[3]) {
			yakus.push_back(Yaku::Shousuushi);
			yakuman = true;
		}
	}

	if (num_ankou == 4) {
		if (call_single) {
			yakus.push_back(Yaku::Siiankou_1);
			yakuman = true;
		}
		else {
			yakus.push_back(Yaku::Siiankou);
			yakuman = true;
		}
	}

	if (num_kantsu == 4) {
		yakus.push_back(Yaku::Siikantsu);
		yakuman = true;
	}

	if (chinroutou) {
		yakus.push_back(Yaku::Chinroutou);
		yakuman = true;
	}

	if (pure_green) {
		yakus.push_back(Yaku::Ryuiisou);
		yakuman = true;
	}
	return yakus;
}

// 这个函数不判断：7对，国士无双及13面，九莲宝灯与纯正，所有宝牌役，所有场役包括立直，两立直，门清自摸，抢杠，海底，河底，一发，岭上，以及所有役满
pair<vector<Yaku>, int> ScoreCounter::get_hand_yakus(const vector<string> &tile_group_string, Wind self_wind, Wind game_wind, bool menzen) {

	vector<Yaku> yakus;
	yakus.reserve(16); // 随便分配一些空间以免后期重新分配
	int fu = 20;
	
	// 判断单骑
	bool call_single = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string &s) {
		return s[2] == ':' && s.size() == 4; // 表示涉及到胡牌的对子
	});

	// DEBUG : 判断门清。确保此处无问题可以注释掉这部分代码
	bool _menzen = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s.size() == 3) return true;
		if (s.size() == 4) return s[3] != '-';
		throw runtime_error("??");
	});

	if (_menzen != menzen) {
		throw runtime_error(fmt::format(
			"Debug: Player门清状态与牌型判定函数不符合!\n"
			"tile_group_string = {}", fmt::join(tile_group_string, " ")));
	}

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
		return is_yaochu_str(s) || is_z_str(s);
	});

	// 统计m清一色
	bool Mchinitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'm') return true;
		return false;
		});
	bool Mhonitsu = (!Mchinitsu) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'm' || s[1] == 'z') return true;
		return false;
		});

	// 统计P清一色
	bool Pchinitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'p') return true;
		return false;
	});
	bool Phonitsu = (!Pchinitsu) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'p' || s[1] == 'z') return true;
		return false;
	});

	// 统计S清一色
	bool Schinitsu = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 's') return true;
		return false;
	});
	bool Shonitsu = (!Schinitsu) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 's' || s[1] == 'z') return true;
		return false;
	});
	
	// 统计所有的字牌刻子和对子
	bool z_koutsu[7] = { false };
	bool z_toitsu[7] = { false };
	for_each(tile_group_string.begin(), tile_group_string.end(), [&z_koutsu, &z_toitsu](const string& s) {
		if (s[1] == 'z') {
			if (s[2] == 'K' || s[2] == '|') {
				z_koutsu[s[0] - '1'] = true;
			}
			if (s[2] == ':') {
				z_toitsu[s[0] - '1'] = true;
			}
		}
	});

	// 统计暗刻数
	int n_ankou = count_if(tile_group_string.begin(), tile_group_string.end(), [&n_ankou](const string& s) {
		return (s.size() == 3 && s[2] == 'K') ||
			(s.size() == 4 && s[2] == 'K' && (s[3] == '!' || s[3] == '@' || s[3] == '#')) ||
			(s[2] == '|' && s[3] == '+');
		});

	// 统计杠子数
	int n_kantsu = count_if(tile_group_string.begin(), tile_group_string.end(), [](const string& s) { return s[2] == '|'; });

	// 判断清老头混老头
	bool honroutou = all_of(tile_group_string.begin(), tile_group_string.end(), [&honroutou](const string& s) {
		return pure_yaochu_str(s) || is_z_str(s);
	});
	
	// 统计全带幺九状态
	// 纯全
	bool junchan = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return is_yaochu_str(s);
		}
	);
	// 混全
	bool chanta = (!honroutou) && (!junchan) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return is_yaochu_str(s) || is_z_str(s);
		}
	);

	// 判断平和
	bool pinfu = true;

	pinfu &= menzen;
	pinfu &= (!call_single);

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
	pinfu &= (tile_group_string.size() == 5);


	auto tile_group_string_no_4 = remove_4(tile_group_string);

	// 判断三色同顺
	bool sanshouku_shuntsu = false;
	const static string sanshouku_shuntsu_tiles[] =
	{
	  "1mS","2mS","3mS","4mS","5mS","6mS","7mS",
	  "1pS","2pS","3pS","4pS","5pS","6pS","7pS",
	  "1sS","2sS","3sS","4sS","5sS","6sS","7sS",
	};
	for (int i = 0; i < 7; ++i) {
		if (is_in(tile_group_string_no_4, sanshouku_shuntsu_tiles[i]) &&
			is_in(tile_group_string_no_4, sanshouku_shuntsu_tiles[i + 7]) &&
			is_in(tile_group_string_no_4, sanshouku_shuntsu_tiles[i + 14])) {
			sanshouku_shuntsu = true;
			break;
		}
	}

	// 判断三色同刻
	bool sanshouku_koutsu = false;
	const static string sanshouku_koutsu_tiles[] =
	{
	  "1mK","2mK","3mK","4mK","5mK","6mK","7mK","8mK","9mK",
	  "1pK","2pK","3pK","4pK","5pK","6pK","7pK","8pK","9pK",
	  "1sK","2sK","3sK","4sK","5sK","6sK","7sK","8sK","9sK",
	};
	for (int i = 0; i < 9; ++i) {
		if (is_in(tile_group_string_no_4, sanshouku_koutsu_tiles[i]) &&
			is_in(tile_group_string_no_4, sanshouku_koutsu_tiles[i + 9]) &&
			is_in(tile_group_string_no_4, sanshouku_koutsu_tiles[i + 18])) {
			sanshouku_koutsu = true;
			break;
		}
	}

	// 判断一气通贯	
	bool ittsu = false;
	const static string M_ittsu[] = { "1mS", "4mS", "7mS" };
	const static string P_ittsu[] = { "1pS", "4pS", "7pS" };
	const static string S_ittsu[] = { "1sS", "4sS", "7sS" };

	ittsu |= all_of(begin(M_ittsu), end(M_ittsu),
		[&tile_group_string_no_4](string tiles) {return is_in(tile_group_string_no_4, tiles); });
	ittsu |= all_of(begin(P_ittsu), end(P_ittsu),
		[&tile_group_string_no_4](string tiles) {return is_in(tile_group_string_no_4, tiles); });
	ittsu |= all_of(begin(S_ittsu), end(S_ittsu),
		[&tile_group_string_no_4](string tiles) {return is_in(tile_group_string_no_4, tiles); });
	
	static const string shuntsu_strs[] = {
		"1sS", "2sS" ,"3sS" ,"4sS" ,"5sS" ,"6sS" ,"7sS",
		"1pS", "2pS" ,"3pS" ,"4pS" ,"5pS" ,"6pS" ,"7pS",
		"1mS", "2mS" ,"3mS" ,"4mS" ,"5mS" ,"6mS" ,"7mS"
	};
	// 判断二杯口 && 一杯口
	int n杯口 = 0;
	if (menzen) {
		for (const string &tiles : shuntsu_strs) {
			if (count_if(tile_group_string_no_4.begin(),
				tile_group_string_no_4.end(),
				[&tiles](const string &s) {return s == tiles; })
				>= 2) n杯口++;

		}
	}

	/* 开始统计 */
	if (n杯口 == 2) yakus.push_back(Yaku::Rianpeikou);
	else if (n杯口 == 1) yakus.push_back(Yaku::Ippeikou);

	if (ittsu) {
		if (menzen) yakus.push_back(Yaku::Ikkitsuukan);
		else yakus.push_back(Yaku::Ikkitsuukan_Naki);
	}

	if (sanshouku_shuntsu) {
		if (menzen) yakus.push_back(Yaku::Sanshokudoujun);
		else yakus.push_back(Yaku::Sanshokudoujun_Naki);
	}

	if (sanshouku_koutsu) yakus.push_back(Yaku::Sanshokudoukou);

	if (Schinitsu || Mchinitsu || Pchinitsu) {
		if (menzen) yakus.push_back(Yaku::Chinitsu);
		else yakus.push_back(Yaku::Chinitsu_Naki);
	}
	else {
		if (Shonitsu || Mhonitsu || Phonitsu) {
			if (menzen) yakus.push_back(Yaku::Honitsu);
			else yakus.push_back(Yaku::Honitsu_Naki);
		}
	}

	if (n_ankou == 3) yakus.push_back(Yaku::Sanankou);
	if (n_kantsu == 3) yakus.push_back(Yaku::Sankantsu);
	if (honroutou)	yakus.push_back(Yaku::Honroutou);
	
	if (tanyao)
		yakus.push_back(Yaku::Tanyao);

	if (junchan) {
		if (menzen) yakus.push_back(Yaku::Junchantaiyaochu);
		else yakus.push_back(Yaku::Junchantaiyaochu_Naki);
	}
	else if (chanta && !honroutou) {
		if (menzen) yakus.push_back(Yaku::Honchantaiyaochu);
		else yakus.push_back(Yaku::Honchantaiyaochu_Naki);
	}

	// 小三元
	if (z_koutsu[4] && z_koutsu[5] && z_toitsu[6]) {
		yakus.push_back(Yaku::Shousangen);
	}
	else if (z_koutsu[4] && z_toitsu[5] && z_koutsu[6]) {
		yakus.push_back(Yaku::Shousangen);
	}
	else if (z_toitsu[4] && z_koutsu[5] && z_koutsu[6]) {
		yakus.push_back(Yaku::Shousangen);
	}
	
	// 判断役牌
	if (z_koutsu[4])
		yakus.push_back(Yaku::Yakuhai_Haku);
	if (z_koutsu[5])
		yakus.push_back(Yaku::Yakuhai_Hatsu);
	if (z_koutsu[6])
		yakus.push_back(Yaku::Yakuhai_Chu);

	if (game_wind == Wind::East)
		if (z_koutsu[0]) yakus.push_back(Yaku::Bakaze_Ton);
	if (game_wind == Wind::South)
		if (z_koutsu[1]) yakus.push_back(Yaku::Bakaze_Nan);
	if (game_wind == Wind::West)
		if (z_koutsu[2]) yakus.push_back(Yaku::Bakaze_Sha);
	if (game_wind == Wind::North)
		if (z_koutsu[3]) yakus.push_back(Yaku::Bakaze_Pei);

	if (self_wind == Wind::East)
		if (z_koutsu[0]) yakus.push_back(Yaku::Jikaze_Ton);
	if (self_wind == Wind::South)
		if (z_koutsu[1]) yakus.push_back(Yaku::Jikaze_Nan);
	if (self_wind == Wind::West)
		if (z_koutsu[2]) yakus.push_back(Yaku::Jikaze_Sha);
	if (self_wind == Wind::North)
		if (z_koutsu[3]) yakus.push_back(Yaku::Jikaze_Pei);

	if (pinfu) yakus.push_back(Yaku::Pinfu);

	// 计算符数

	// 听牌型
	if (call_single) fu += 2;
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
	for_each(tile_group_string.begin(), tile_group_string.end(), [&fu](const string& s) {
		if (s.size() == 3 && s[2] == 'K') { 
			if (has_yaochu_or_z_str(s)) fu += 8; 
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
					if (has_yaochu_or_z_str(s)) fu += 8;
					else fu += 4;
					break;
				case '$':
				case '%':
				case '^':
				case '-':
					if (has_yaochu_or_z_str(s)) fu += 4;
					else fu += 2;
					break;
				}
				break;
			case '|':
				if (s[3] == '-') {
					if (has_yaochu_or_z_str(s)) fu += 16;
					else fu += 8;
				}
				else if (s[3] == '+') {
					if (has_yaochu_or_z_str(s)) fu += 32;
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

pair<vector<Yaku>, int> ScoreCounter::get_max_hand_yakus(
	const CompletedTiles &ct, const vector<CallGroup> &callgroups, Tile *correspond_tile, BaseTile tsumo_tile, Wind self_wind, Wind game_wind, bool menzen, bool& yakuman)
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

	pair<vector<Yaku>, int> max_yaku_fus = { {}, 0 };
	int max_fan = 0;
	// 当这个 荣和/自摸 的牌存在于不同的地方的时候，也有可能会导致解释不同
	// 这个牌一定在ct里面
	// 对于每一种情况，都是vector中的一个元素

	auto tile_group_strings = generate_tile_group_strings(ct, callgroups, tsumo, last_tile);

	for (auto tile_group : tile_group_strings) {
		const auto& yakus = get_hand_yakuman(tile_group, self_wind, game_wind, yakuman);
		if (yakuman) {
			int fan = calculate_fan(yakus);
			if (fan > max_fan) {
				max_yaku_fus = { yakus, 20 };
				max_fan = fan;
			}			
		}
		else {
			const auto &yaku_fu = get_hand_yakus(tile_group, self_wind, game_wind, menzen);
			max_yaku_fus = max(max_yaku_fus, yaku_fu, &compare_yaku_fu);
		}

	}
	return max_yaku_fus;
}

bool ScoreCounter::get_tenhou_chihou() {
	if (player->first_round && tsumo) {
		have_yaku = true;
		if (player->oya)
		{
			tenhou_chihou_yakus.push_back(Yaku::Tenhou);
			yakuman = true;
			yakuman_fold += 1;
		}
		else {
			tenhou_chihou_yakus.push_back(Yaku::Chihou);
		}
		yakuman = true;
		yakuman_fold += 1;
		return true;
	}
	else {
		return false;
	}
}

bool ScoreCounter::get_kokushi() {
	if (menzen) {
		if (is_kokushi_shape(basetiles)) {
			// 判定13面
			{
				auto copybasetiles = basetiles;
				copybasetiles.pop_back();
				const static std::vector<BaseTile> raw
				{ _1m, _9m, _1s, _9s, _1p, _9p, _1z, _2z, _3z, _4z, _5z, _6z, _7z };

				sort(copybasetiles.begin(), copybasetiles.end());
				if (is_same_container(raw, basetiles))
				{
					max_hand_yakus_fan_fu.first.push_back(Yaku::Koukushimusou_13);
					kokushi_13 = true;
				}
				else {
					max_hand_yakus_fan_fu.first.push_back(Yaku::Kokushimusou);
					kokushi = true;
				}
			}
			yakuman = true;
		}
	}
	return false;
}

void ScoreCounter::get_pure_type() {
	mpsz_pure_type = basetiles[0] / 9;
	for (size_t i = 1; i < 14; ++i)
		if (basetiles[i] / 9 != mpsz_pure_type) {
			// 清一色都不是
			mpsz_pure_type = -1;
			break;
		}
}

bool ScoreCounter::get_churen() {
	if (!menzen) return false;
	if (mpsz_pure_type < 0 && mpsz_pure_type > 2) return false;
	if (is_churen_9_shape(basetiles)) {
		churen_pure = true;
		max_hand_yakus_fan_fu.first.push_back(Yaku::Chuurenpoutou_9);
		yakuman = true;
		return true;
	}
	else if (is_churen_shape(basetiles)) {
		churen = true;
		max_hand_yakus_fan_fu.first.push_back(Yaku::Chuurenpoutou);
		yakuman = true;
		return true;
	}
	return false;
}

void ScoreCounter::get_riichi() {
	if (player->double_riichi)
		state_yakus.push_back(Yaku::Dabururiichi);
	else if (player->riichi)
		state_yakus.push_back(Yaku::Riichi);
}

void ScoreCounter::get_haitei_hotei() {
	/* 海底的条件是1. remain_tile == 0, 2. 上一手不是杠相关 */
	if (tsumo && table->get_remain_tile() == 0 &&
		table->last_action != BaseAction::AnKan &&
		table->last_action != BaseAction::Kan &&
		table->last_action != BaseAction::KaKan) {
		state_yakus.push_back(Yaku::Haiteiraoyue);
	}
	if (!tsumo && table->get_remain_tile() == 0) {
		state_yakus.push_back(Yaku::Houteiraoyu);
	}
}

void ScoreCounter::get_chankan() {
	/* 如果是抢杠，那么计算抢杠 */
	if (chankan) {
		state_yakus.push_back(Yaku::Chankan);
	}
}

void ScoreCounter::get_rinshan() {
	/* 如果上一轮动作是杠，这一轮是tsumo，那么就是岭上 */
	if (table->last_action == BaseAction::AnKan ||
		table->last_action == BaseAction::Kan ||
		table->last_action == BaseAction::KaKan) {
		if (tsumo) {
			state_yakus.push_back(Yaku::Rinshankaihou);
		}
	}
}

inline void ScoreCounter::get_menzentsumo() {
	/*门清自摸*/
	if (tsumo && player->menzen) {
		state_yakus.push_back(Yaku::Menzentsumo);
	}
}

void ScoreCounter::get_ippatsu() {
	/* 如果保存有一发状态 */
	if (player->ippatsu) {
		state_yakus.push_back(Yaku::Ippatsu);
	}
}

void ScoreCounter::get_aka_dora() {
	// 接下来统计红宝牌数量
	for (auto tile : tiles) {
		if (tile->red_dora == true) {
			dora_yakus.push_back(Yaku::Akadora);
		}
	}

	for (auto fulu : player->call_groups) {
		for (auto tile : fulu.tiles) {
			if (tile->red_dora == true) {
				dora_yakus.push_back(Yaku::Akadora);
			}
		}
	}

	/*if (win_tile && win_tile->red_dora == true) {
		Dora役.push_back(Yaku::赤宝牌);
	}*/
}

void ScoreCounter::get_dora() {
	// 统计宝牌数量
	auto doratiles = table->get_dora();
	for (auto doratile : doratiles) {
		for (auto tile : tiles) {
			if (tile->tile == doratile) {
				dora_yakus.push_back(Yaku::Dora);
			}
		}

		for (auto fulu : player->call_groups) {
			for (auto tile : fulu.tiles) {
				if (tile->tile == doratile) {
					dora_yakus.push_back(Yaku::Dora);
				}
			}
		}

		/*if (correspond_tile && correspond_tile->tile == doratile) {
			Dora役.push_back(Yaku::宝牌);
		}*/
	}
}

void ScoreCounter::get_ura_dora() {
	// 如果是立直和牌，继续统计里宝牌
	if (player->is_riichi()) {
		const auto& doratiles = table->get_ura_dora();
		for (const auto& doratile : doratiles) {
			for (const auto& tile : tiles) {
				if (tile->tile == doratile) {
					dora_yakus.push_back(Yaku::Uradora);
				}
			}

			for (const auto& fulu : player->call_groups) {
				for (const auto& tile : fulu.tiles) {
					if (tile->tile == doratile) {
						dora_yakus.push_back(Yaku::Uradora);
					}
				}
			}

			/*if (correspond_tile && correspond_tile->tile == doratile) {
				Dora役.push_back(Yaku::里宝牌);
			}*/
		}
	}
}

CounterResult ScoreCounter::yaku_counter()
{
	// 首先 假设进入到这个counter阶段的，至少满足了和牌条件的牌型
	// 以及，是否有某种役是不确定的

	CounterResult final_result;

	yakuman = false;

	/* 天地和的条件是，在第一巡，且没人鸣牌*/
	if (player->first_round && tsumo) {
		if (table->oya == table->turn) {
			tenhou_chihou_yakus.push_back(Yaku::Tenhou);
			yakuman = true;
		}
		else {
			tenhou_chihou_yakus.push_back(Yaku::Chihou);
			yakuman = true;
		}
	}

	get_kokushi();
	if (!kokushi && !kokushi_13)
		get_churen();

	if (!kokushi && !kokushi_13 && !churen && !churen_pure)	{
		/* 并非以上情况的手役判断 */
		sort(basetiles.begin(), basetiles.end());
		// 对牌进行拆解 （已经unique）
		auto&& complete_tiles_list = get_completed_tiles(basetiles);

		/* 统计七对子*/
		if (is_7toitsu_shape(basetiles)) {
			// 即使是役满这里也要纳入考虑，因为存在大七星
			CompletedTiles ct;
			sort(basetiles.begin(), basetiles.end());
			for (int i = 0; i < 14; i += 2) {
				TileGroup tg;
				tg.type = TileGroup::Toitsu;
				tg.set_tiles({ basetiles[i], basetiles[i] });
				ct.body.push_back(tg);
			}
			complete_tiles_list.push_back(ct);
		}
		// 接下来

		for (const auto &complete_tiles : complete_tiles_list) {
			auto yaku_fus = get_max_hand_yakus(complete_tiles, player->call_groups, win_tile, player->hand.back()->tile, self_wind, game_wind, menzen, yakuman);
			max_hand_yakus_fan_fu = max(max_hand_yakus_fan_fu, yaku_fus, &compare_yaku_fu);
		}
	}

	if (yakuman) {
		// 役满情况下，不判断状态役和dora役
		merge_into(max_hand_yakus_fan_fu.first, tenhou_chihou_yakus);
	}	
	else {
		get_state_yaku_dora_yaku();
		merge_into(max_hand_yakus_fan_fu.first, state_yakus);
		merge_into(max_hand_yakus_fan_fu.first, dora_yakus);
	}	

	if (!can_agari(max_hand_yakus_fan_fu.first)) {
		// 说明无役
		final_result.yakus.push_back(Yaku::None);
	}
	else {
		final_result.yakus = max_hand_yakus_fan_fu.first;
		final_result.fan = calculate_fan(final_result.yakus);
		final_result.fu = max_hand_yakus_fan_fu.second;
		final_result.calculate_score(player->oya, tsumo);
	}
	return final_result;
}

ScoreCounter::ScoreCounter(const Table* t, const Player* p, Tile* win, bool chankan_, bool chanankan_)
	: chankan(chankan_), chanankan(chanankan_), menzen(p->menzen)
{
	table = t;
	player = p;
	win_tile = win;
	tiles = p->hand;
	if (win_tile == nullptr)
		tsumo = true;
	else {
		tsumo = false;
		win_tile = win;
		tiles.push_back(win_tile);
	}
	basetiles = convert_tiles_to_basetiles(tiles);
	self_wind = p->wind;
	game_wind = t->game_wind;
}

namespace_mahjong_end


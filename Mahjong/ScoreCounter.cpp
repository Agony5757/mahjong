#include "ScoreCounter.h"
#include "Player.h"
#include "Table.h"
#include "Rule.h"
#include "macro.h"

namespace_mahjong
using namespace std;

#define REGISTER_SCORE(亲, 自摸, score_铳亲, score_亲自摸_all, score_铳子, score_子自摸_亲, score_子自摸_子) \
if (亲) {if (自摸){score1=score_亲自摸_all;} else{score1=score_铳亲;}} \
else {if (自摸) {score1=score_子自摸_亲; score2=score_子自摸_子;} else{score1=score_铳子;}} return;

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
		REGISTER_SCORE(亲, 自摸, 24000, 8000, 16000, 8000, 4000);
	}
	else if (fan >= 6) {
		REGISTER_SCORE(亲, 自摸, 18000, 6000, 12000, 6000, 3000);
	}
	else if (fan == 5) {
		REGISTER_SCORE(亲, 自摸, 12000, 4000, 8000, 4000, 2000);
	}
	else if (fan == 4) {
		// 40符以上满贯
		if (fu >= 40) {
			REGISTER_SCORE(亲, 自摸, 12000, 4000, 8000, 4000, 2000);
		}
		else if (fu == 30) {
			REGISTER_SCORE(亲, 自摸, 11600, 3900, 7700, 3900, 2000);
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
			REGISTER_SCORE(亲, 自摸, 11600, 3900, 7700, 3900, 2000);
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
	throw runtime_error(fmt::format("Error fan & fu cases. {} fan {} fu.", fan, fu));
}

int calculate_fan(const vector<Yaku> &yakus)
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

constexpr char mark_toitsu		= ':';
constexpr char mark_shuntsu		= 'S';
constexpr char mark_koutsu		= 'K';
constexpr char mark_kantsu		= '|';
constexpr char mark_ankan		= '+';
constexpr char mark_minkan		= '-';
constexpr char mark_fuuro		= '-';
constexpr char mark_tsumo_1st	= '!';
constexpr char mark_tsumo_2nd	= '@';
constexpr char mark_tsumo_3rd	= '#';
constexpr char mark_ron_1st		= '$';
constexpr char mark_ron_2nd		= '%';
constexpr char mark_ron_3rd		= '^';

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

string make_toitsu(BaseTile t)			{ return make_tilegroup(t, mark_toitsu); }
string make_shuntsu(BaseTile t)			{ return make_tilegroup(t, mark_shuntsu); }
string make_shuntsu_fuuro(BaseTile t)	{ return make_tilegroup(t, mark_shuntsu, mark_fuuro); }
string make_koutsu(BaseTile t)			{ return make_tilegroup(t, mark_koutsu); }
string make_koutsu_fuuro(BaseTile t)	{ return make_tilegroup(t, mark_koutsu, mark_fuuro); }
string make_ankan(BaseTile t)			{ return make_tilegroup(t, mark_kantsu, mark_ankan); }
string make_minkan(BaseTile t)			{ return make_tilegroup(t, mark_kantsu, mark_minkan); }

static std::vector<std::vector<std::string>> generate_tile_group_strings(const CompletedTiles &ct, const vector<Fulu> &fulus, bool tsumo, BaseTile last_tile)
{
	profiler _("ScoreCounter.cpp/generate_tgs");
	std::vector<std::vector<std::string>> tile_group_strings;
	std::vector<std::string> raw_tile_group_string; // without consider where is the agari tile.	  

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

	for (auto fulu : fulus) {
		switch (fulu.type) {
		case Fulu::Chi:
			raw_tile_group_string.push_back(make_shuntsu_fuuro(fulu.tiles[0]->tile)); // 例如1sS- 即1s2s3s (8sS无效)
			continue;
		case Fulu::Pon:
			raw_tile_group_string.push_back(make_koutsu_fuuro(fulu.tiles[0]->tile)); // 例如1sK- 即1s1s1s
			continue;
		case Fulu::大明杠:
		case Fulu::加杠:
			raw_tile_group_string.push_back(make_minkan(fulu.tiles[0]->tile)); // 例如3z4- 即西大明杠/加杠
			continue;
		case Fulu::暗杠:
			raw_tile_group_string.push_back(make_ankan(fulu.tiles[0]->tile)); // 例如4s4+ 即4s暗杠
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

bool is_shuntsu_str(const string &s) { return s[2] == 'S'; }
bool is_koutsu_str(const string &s) { return s[2] == 'K'; }
bool is_kantsu_str(const string &s) { return s[2] == '|'; }
bool is_minkan_str(const string &s) { return s.size() == 4 && s[2] == '|' && s[3] == '-'; }
bool is_minkou_str(const string &s) { return s.size() == 4 && s[2] == 'K' && s[3] == '-'; }
bool is_minshun_str(const string &s) { return s.size() == 4 && s[2] == 'S' && s[3] == '-'; }
bool is_ankan_str(const string &s) { return s.size() == 4 && s[2] == '|' && s[3] == '+'; }
bool tile_group_match(const string& s1, const string& s2) { return s1[0] == s2[0] && s1[1] == s2[1] && s1[2] == s2[2]; }

/* 牌型对/顺/刻/杠，含字牌 */
bool 带字牌(const string &s) {
	return s[1] == 'z';
}

/* 牌型对/顺/刻/杠，含至少1张幺九，不包括字牌，例如789s 1111m */
bool 带幺九(const string &s) {
	if (带字牌(s)) return false;
	if (s[2] == 'K' || s[2] == ':' || s[2] == '|') return s[0] == '1' || s[0] == '9';
	if (s[2] == 'S') return s[0] == '1' || s[0] == '7';
	throw runtime_error(fmt::format("Bad tile group string (input = {})", s));
}

/* 牌型对/刻/杠，全幺九，不包括字牌，例如999p 1111m */
bool 纯老头(const string &s) {
	if (s[2] == 'K' || s[2] == ':' || s[2] == '|') return s[0] == '1' || s[0] == '9';
	return false;
}

bool 纯绿牌(const string &s) {
	const char* green_types[] = {"2sK", "3sK", "4sK", "2sS", "6sK", "8sK", "6zK",
		"2s:", "3s:", "4s:", "6s:", "8s:", "6z:" };

	return all_of(begin(green_types), end(green_types), 
		[&s](const char* green) {return tile_group_match(s, green); });
}

/* 用于处理全带，不包括杠子 */
bool 带幺九字(const string &s) {
	return 带字牌(s) || 带幺九(s);
}

/* 用于记符，对于役牌对子的计数，包括连风对子 */
int is役牌对子(string s, Wind 自风, Wind 场风) {
	if (s[2] != ':') return 0; //不是对子
	if (s[1] != 'z') return 0; //不是字牌

	int cases = 0;
	int number = s[0] - '1'; // 0 1 2 3分别为东南西北
	if (number == 自风) cases++;
	if (number == 场风) cases++;
	if (number >= 4) cases++; // 4,5,6为白发中
	return cases;
}

/* 移除副露、胡牌等信息，创建复制 */
vector<string> remove_4(const vector<string> &strs) {
	vector<string> retstr(strs);

	for (auto &ret : retstr) {
		if (ret.size() == 4) ret.pop_back();
		if (ret[2] == '|') ret[2] = 'K';		
	}
	return retstr;
}

pair<vector<Yaku>, int> get_手役_from_complete_tiles_固定位置_役满(const vector<string> &tile_group_string, Wind 自风, Wind 场风, bool &役满) {
	vector<Yaku> yakus;
	
	// 统计Z一色
	bool 字一色 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return 带字牌(s);
		});	

	// 统计所有的字牌刻子和对子
	bool 字牌刻子[7] = { false };
	bool 字牌对子[7] = { false };
	for_each(tile_group_string.begin(), tile_group_string.end(), [&字牌刻子, &字牌对子](const string& s) {
		if (s[1] == 'z') {
			if (s[2] == 'K' || s[2] == '|') {
				字牌刻子[s[0] - '1'] = true;
			}
			if (s[2] == ':') {
				字牌对子[s[0] - '1'] = true;
			}
		}
	});
	
	// 判断单骑
	bool 单骑 = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string &s) {
		return s[2] == ':' && s.size() == 4; // 表示涉及到胡牌的对子
		});

	// 统计暗刻数
	int num_暗刻 = count_if(tile_group_string.begin(), tile_group_string.end(), [&num_暗刻](const string& s) {
		return (s.size() == 3 && s[2] == 'K') ||
			(s.size() == 4 && s[2] == 'K' && (s[3] == '!' || s[3] == '@' || s[3] == '#')) ||
			(s[2] == '|' && s[3] == '+');
		});

	// 统计杠子数
	int num_杠子 = count_if(tile_group_string.begin(), tile_group_string.end(), [](const string& s) { return s[2] == '|'; });


	// 判断清老头混老头
	bool 清老头 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return 纯老头(s); 
	});

	// 判断绿一色
	bool 绿一色 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return 纯绿牌(s);
		});

	/* 开始判定 */

	if (字一色) {
		yakus.push_back(Yaku::字一色);
		役满 = true;
	}

	if (字牌刻子[4] && 字牌刻子[5] && 字牌刻子[6]) {
		yakus.push_back(Yaku::大三元);
		役满 = true;
	}

	if (字牌刻子[0] && 字牌刻子[1] && 字牌刻子[2] && 字牌刻子[3]) {
		yakus.push_back(Yaku::大四喜);
		役满 = true;
	}
	else {
		if (字牌对子[0] && 字牌刻子[1] && 字牌刻子[2] && 字牌刻子[3]) {
			yakus.push_back(Yaku::小四喜);
			役满 = true;
		}
		if (字牌刻子[0] && 字牌对子[1] && 字牌刻子[2] && 字牌刻子[3]) {
			yakus.push_back(Yaku::小四喜);
			役满 = true;
		}
		if (字牌刻子[0] && 字牌刻子[1] && 字牌对子[2] && 字牌刻子[3]) {
			yakus.push_back(Yaku::小四喜);
			役满 = true;
		}
		if (字牌刻子[0] && 字牌刻子[1] && 字牌刻子[2] && 字牌对子[3]) {
			yakus.push_back(Yaku::小四喜);
			役满 = true;
		}
	}

	if (num_暗刻 == 4) {
		if (单骑) {
			yakus.push_back(Yaku::四暗刻单骑);
			役满 = true;
		}
		else {
			yakus.push_back(Yaku::四暗刻);
			役满 = true;
		}
	}

	if (num_杠子 == 4) {
		yakus.push_back(Yaku::四杠子);
		役满 = true;
	}

	if (清老头) {
		yakus.push_back(Yaku::清老头);
		役满 = true;
	}

	if (绿一色) {
		yakus.push_back(Yaku::绿一色);
		役满 = true;
	}
	return { yakus, 0 };
}

// 这个函数不判断：7对，国士无双及13面，九莲宝灯与纯正，所有宝牌役，所有场役包括立直，两立直，门清自摸，抢杠，海底，河底，一发，岭上，以及所有役满
static pair<vector<Yaku>, int> get_手役_from_complete_tiles_固定位置(vector<string> tile_group_string, Wind 自风, Wind 场风, bool 门清) {

	vector<Yaku> yakus;
	yakus.reserve(16); // 随便分配一些空间以免后期重新分配
	int fu = 20;
	
	// 判断单骑
	bool 单骑 = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string &s) {
		return s[2] == ':' && s.size() == 4; // 表示涉及到胡牌的对子
	});

	// DEBUG : 判断门清。确保此处无问题可以注释掉这部分代码
	bool _门清 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s.size() == 3) return true;
		if (s.size() == 4) return s[3] != '-';
		throw runtime_error("??");
	});

	if (_门清 != 门清) {
		throw runtime_error(fmt::format(
			"Debug: Player门清状态与牌型判定函数不符合!\n"
			"tile_group_string = {}", fmt::join(tile_group_string, " ")));
	}

	// 判断7对
	if (tile_group_string.size() == 7) {
		yakus.push_back(Yaku::七对子);
	}

	// 判断有没有顺子
	bool has顺子 = any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[2] == 'S') return true;
		else return false;
	});
	if (!has顺子 && tile_group_string.size() != 7) {
		yakus.push_back(Yaku::对对和);
	}

	// 判断是不是断幺九
	bool 断幺九 = none_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return 带幺九(s) || 带字牌(s);
	});

	// 统计m清一色
	bool M清一色 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'm') return true;
		return false;
		});
	bool M混一色 = (!M清一色) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'm' || s[1] == 'z') return true;
		return false;
		});

	// 统计P清一色
	bool P清一色 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'p') return true;
		return false;
	});
	bool P混一色 = (!P清一色) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 'p' || s[1] == 'z') return true;
		return false;
	});

	// 统计S清一色
	bool S清一色 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 's') return true;
		return false;
	});
	bool S混一色 = (!S清一色) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		if (s[1] == 's' || s[1] == 'z') return true;
		return false;
	});
	
	// 统计所有的字牌刻子和对子
	bool 字牌刻子[7] = { false };
	bool 字牌对子[7] = { false };
	for_each(tile_group_string.begin(), tile_group_string.end(), [&字牌刻子, &字牌对子](const string& s) {
		if (s[1] == 'z') {
			if (s[2] == 'K' || s[2] == '|') {
				字牌刻子[s[0] - '1'] = true;
			}
			if (s[2] == ':') {
				字牌对子[s[0] - '1'] = true;
			}
		}
	});

	// 统计暗刻数
	int num_暗刻 = count_if(tile_group_string.begin(), tile_group_string.end(), [&num_暗刻](const string& s) {
		return (s.size() == 3 && s[2] == 'K') ||
			(s.size() == 4 && s[2] == 'K' && (s[3] == '!' || s[3] == '@' || s[3] == '#')) ||
			(s[2] == '|' && s[3] == '+');
		});

	// 统计杠子数
	int num_杠子 = count_if(tile_group_string.begin(), tile_group_string.end(), [](const string& s) { return s[2] == '|'; });

	// 判断清老头混老头
	bool 混老头 = all_of(tile_group_string.begin(), tile_group_string.end(), [&混老头](const string& s) {
		return 纯老头(s) || 带字牌(s);
	});
	
	// 统计幺九状态
	bool 纯全带幺九 = all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return 带幺九(s);
		}
	);
	bool 混全带幺九 = (!混老头) && (!纯全带幺九) && all_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		return 带幺九(s) || 带字牌(s);
		}
	);

	// 判断平和
	bool 平和 = true;

	平和 &= 门清;
	平和 &= (!单骑);

	// 对子不是役牌
	平和 &= none_of(tile_group_string.begin(), tile_group_string.end(), [&自风, &场风](const string& s) {
		return is役牌对子(s, 自风, 场风);
		});

	// 对子 顺子
	平和 &= all_of(tile_group_string.begin(), tile_group_string.end(), [&自风, &场风](const string& s) {
		if (s[2] == ':') return true;
		if (s[2] == 'S') return true;
		return false;
		});

	// 和牌型
	平和 &= all_of(tile_group_string.begin(), tile_group_string.end(), [&自风, &场风](const string &s) {
		if (s.size() == 3) return true;
		if (s[3] == '@') return false;
		if (s[3] == '%') return false;
		if (s[2] == ':' && s[3] == '$') return false;
		if ((s[3] == '#' || s[3] == '^') && s[0] == '1') return false;
		if ((s[3] == '!' || s[3] == '$') && s[0] == '7') return false;
		return true;
		});
	平和 &= (tile_group_string.size() == 5);


	auto tile_group_string_no_4 = remove_4(tile_group_string);

	// 判断三色同顺
	bool 三色同顺 = false;
	const static string 三色同顺tiles[] =
	{
	  "1mS","2mS","3mS","4mS","5mS","6mS","7mS",
	  "1pS","2pS","3pS","4pS","5pS","6pS","7pS",
	  "1sS","2sS","3sS","4sS","5sS","6sS","7sS",
	};
	for (int i = 0; i < 7; ++i) {
		if (is_in(tile_group_string_no_4, 三色同顺tiles[i]) &&
			is_in(tile_group_string_no_4, 三色同顺tiles[i + 7]) &&
			is_in(tile_group_string_no_4, 三色同顺tiles[i + 14])) {
			三色同顺 = true;
			break;
		}
	}

	// 判断三色同刻
	bool 三色同刻 = false;
	const static string 三色同刻tiles[] =
	{
	  "1mK","2mK","3mK","4mK","5mK","6mK","7mK","8mK","9mK",
	  "1pK","2pK","3pK","4pK","5pK","6pK","7pK","8pK","9pK",
	  "1sK","2sK","3sK","4sK","5sK","6sK","7sK","8sK","9sK",
	};
	for (int i = 0; i < 9; ++i) {
		if (is_in(tile_group_string_no_4, 三色同刻tiles[i]) &&
			is_in(tile_group_string_no_4, 三色同刻tiles[i + 9]) &&
			is_in(tile_group_string_no_4, 三色同刻tiles[i + 18])) {
			三色同刻 = true;
			break;
		}
	}

	// 判断一气通贯	
	bool 一气通贯 = false;
	const static string 一气通贯M[] = { "1mS", "4mS", "7mS" };
	const static string 一气通贯P[] = { "1pS", "4pS", "7pS" };
	const static string 一气通贯S[] = { "1sS", "4sS", "7sS" };

	一气通贯 |= all_of(begin(一气通贯M), end(一气通贯M),
		[&tile_group_string_no_4](string tiles) {return is_in(tile_group_string_no_4, tiles); });
	一气通贯 |= all_of(begin(一气通贯P), end(一气通贯P),
		[&tile_group_string_no_4](string tiles) {return is_in(tile_group_string_no_4, tiles); });
	一气通贯 |= all_of(begin(一气通贯S), end(一气通贯S),
		[&tile_group_string_no_4](string tiles) {return is_in(tile_group_string_no_4, tiles); });
	
	static const string 顺子牌型[] = {
		"1sS", "2sS" ,"3sS" ,"4sS" ,"5sS" ,"6sS" ,"7sS",
		"1pS", "2pS" ,"3pS" ,"4pS" ,"5pS" ,"6pS" ,"7pS",
		"1mS", "2mS" ,"3mS" ,"4mS" ,"5mS" ,"6mS" ,"7mS"
	};
	// 判断二杯口 && 一杯口
	int n杯口 = 0;
	if (门清) {
		for (const string &tiles : 顺子牌型) {
			if (count_if(tile_group_string_no_4.begin(),
				tile_group_string_no_4.end(),
				[&tiles](const string &s) {return s == tiles; })
				>= 2) n杯口++;

		}
	}

	/* 开始统计 */
	if (n杯口 == 2) yakus.push_back(Yaku::二杯口);
	else if (n杯口 == 1) yakus.push_back(Yaku::一杯口);

	if (一气通贯) {
		if (门清) yakus.push_back(Yaku::一气通贯);
		else yakus.push_back(Yaku::一气通贯副露版);
	}

	if (三色同顺) {
		if (门清) yakus.push_back(Yaku::三色同顺);
		else yakus.push_back(Yaku::三色同顺副露版);
	}

	if (三色同刻) yakus.push_back(Yaku::三色同刻);

	if (S清一色 || M清一色 || P清一色) {
		if (门清) yakus.push_back(Yaku::清一色);
		else yakus.push_back(Yaku::清一色副露版);
	}
	else {
		if (S混一色 || M混一色 || P混一色) {
			if (门清) yakus.push_back(Yaku::混一色);
			else yakus.push_back(Yaku::混一色副露版);
		}
	}

	if (num_暗刻 == 3) yakus.push_back(Yaku::三暗刻);
	if (num_杠子 == 3) yakus.push_back(Yaku::三杠子);
	if (混老头)	yakus.push_back(Yaku::混老头);
	
	if (断幺九)
		yakus.push_back(Yaku::断幺九);

	if (纯全带幺九) {
		if (门清) yakus.push_back(Yaku::纯全带幺九);
		else yakus.push_back(Yaku::纯全带幺九副露版);
	}
	else if (混全带幺九 && !混老头) {
		if (门清) yakus.push_back(Yaku::混全带幺九);
		else yakus.push_back(Yaku::混全带幺九副露版);
	}

	// 小三元
	if (字牌刻子[4] && 字牌刻子[5] && 字牌对子[6]) {
		yakus.push_back(Yaku::小三元);
	}
	else if (字牌刻子[4] && 字牌对子[5] && 字牌刻子[6]) {
		yakus.push_back(Yaku::小三元);
	}
	else if (字牌对子[4] && 字牌刻子[5] && 字牌刻子[6]) {
		yakus.push_back(Yaku::小三元);
	}
	
	// 判断役牌
	if (字牌刻子[4])
		yakus.push_back(Yaku::役牌_白);
	if (字牌刻子[5])
		yakus.push_back(Yaku::役牌_发);
	if (字牌刻子[6])
		yakus.push_back(Yaku::役牌_中);

	if (场风 == Wind::East)
		if (字牌刻子[0]) yakus.push_back(Yaku::场风_东);
	if (场风 == Wind::South)
		if (字牌刻子[1]) yakus.push_back(Yaku::场风_南);
	if (场风 == Wind::West)
		if (字牌刻子[2]) yakus.push_back(Yaku::场风_西);
	if (场风 == Wind::North)
		if (字牌刻子[3]) yakus.push_back(Yaku::场风_北);

	if (自风 == Wind::East)
		if (字牌刻子[0]) yakus.push_back(Yaku::自风_东);
	if (自风 == Wind::South)
		if (字牌刻子[1]) yakus.push_back(Yaku::自风_南);
	if (自风 == Wind::West)
		if (字牌刻子[2]) yakus.push_back(Yaku::自风_西);
	if (自风 == Wind::North)
		if (字牌刻子[3]) yakus.push_back(Yaku::自风_北);

	if (平和) yakus.push_back(Yaku::平和);

	// 计算符数

	// 听牌型
	if (单骑) fu += 2;
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
	}) && !平和)
		fu += 2;

	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 荣和
		if (s.size() == 4) {
			if (s[3] == '$' || s[3] == '%' || s[3] == '^') return true;
		}
		return false;
	}) && 门清)
		fu += 10;

	// 雀头符
	for_each(tile_group_string.begin(), tile_group_string.end(), [&fu, &自风, &场风](const string &s) {
		// 荣和
		fu += (is役牌对子(s, 自风, 场风) * 2);
	});

	//面子符	
	for_each(tile_group_string.begin(), tile_group_string.end(), [&fu](const string& s) {
		if (s.size() == 3 && s[2] == 'K') { 
			if (带幺九字(s)) fu += 8; 
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
					if (带幺九字(s)) fu += 8;
					else fu += 4;
					break;
				case '$':
				case '%':
				case '^':
				case '-':
					if (带幺九字(s)) fu += 4;
					else fu += 2;
					break;
				}
				break;
			case '|':
				if (s[3] == '-') {
					if (带幺九字(s)) fu += 16;
					else fu += 8;
				}
				else if (s[3] == '+') {
					if (带幺九字(s)) fu += 32;
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
	}) && (!门清)) {
		if (fu == 20) fu = 30;
	}

	// 自摸平和 20符
	if (any_of(tile_group_string.begin(), tile_group_string.end(), [](const string& s) {
		// 自摸
		if (s.size() == 4) {
			if (s[3] == '!' || s[3] == '@' || s[3] == '#') return true;
		}
		return false;
	}) && (平和)) {
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

static vector<pair<vector<Yaku>, int>> get_手役_from_complete_tiles(
	const CompletedTiles &ct, const vector<Fulu> &fulus, Tile *correspond_tile, BaseTile tsumo_tile, Wind 自风, Wind 场风, bool 门清, bool& 役满)
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

	auto tile_group_strings = generate_tile_group_strings(ct, fulus, tsumo, last_tile);

	for (auto tile_group : tile_group_strings) {
		auto yaku_fu = get_手役_from_complete_tiles_固定位置_役满(tile_group, 自风, 场风, 役满);

		if (!役满) {
			yaku_fu = get_手役_from_complete_tiles_固定位置(tile_group, 自风, 场风, 门清);
		}
		yaku_fus.push_back(yaku_fu);
	}
	return yaku_fus;
}

CounterResult yaku_counter(Table *table, Player &player, Tile *correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风)
{
	// 首先 假设进入到这个counter阶段的，至少满足了和牌条件的牌型
	// 以及，是否有某种役是不确定的

	// 从最简单的场役开始计算

	bool tsumo = (correspond_tile == nullptr);
	bool 门清 = player.门清;

	// 役 = 手役+场役+Dora。手役根据牌的解释不同而不同。
	vector<pair<vector<Yaku>, int>> all_yaku_fu_cases;
	CounterResult final_result;

	auto handcopy = player.hand;
	if (correspond_tile != nullptr)
		handcopy.push_back(correspond_tile);

	auto hand_basetile = convert_tiles_to_basetiles(handcopy);

	bool 役满 = false;
	vector<Yaku> 天地和;
	vector<Yaku> 场役;
	vector<Yaku> Dora役;
	vector<pair<vector<Yaku>, int>> &all_手役 = all_yaku_fu_cases; // 所有手役可能性

	/* 天地和的条件是，在第一巡，且没人鸣牌*/
	if (player.first_round && tsumo) {
		if (table->庄家 == table->turn) {
			天地和.push_back(Yaku::天和);
			役满 = true;
		}
		else {
			天地和.push_back(Yaku::地和);
			役满 = true;
		}
	}

	// 接下来统计国士无双&九莲（定牌型）
	bool 国士 = false;
	bool 国士13 = false;
	bool 九莲 = false;
	bool 九莲纯 = false;

	if (handcopy.size() == 14) {
		// 过滤一次门清条件
		do {
			if (is国士无双和牌型(hand_basetile)) {
				// 判定13面
				{
					auto tiles = player.hand;
					if (correspond_tile == nullptr) tiles.pop_back();
					vector<BaseTile> raw
					{ _1m, _9m, _1s, _9s, _1p, _9p, _1z, _2z, _3z, _4z, _5z, _6z, _7z };

					sort(tiles.begin(), tiles.end());
					if (is_same_container(raw, convert_tiles_to_basetiles(tiles)))
						国士13 = true;
					else 
						国士 = true;
				}
				役满 = true;
				break; // 等同于jump出去，因为国/九莲肯定牌型不同，不需要继续判断九莲了
			}

			// 九莲
			int mpsz一色 = handcopy[0]->tile / 9;
			if (mpsz一色 >= 0 && mpsz一色 <= 2) {
				for (size_t i = 1; i < 14; ++i) {
					if (handcopy[i]->tile / 9 != mpsz一色) {
						// 清一色都不是
						mpsz一色 = -1;
						break;
					}
				}
			}
			if (mpsz一色 < 0 && mpsz一色 > 2) break;//不满足基本条件直接跳出 

			if (is纯九莲和牌型(hand_basetile)) {
				九莲纯 = true;
				役满 = true;
			}
			else if (is九莲和牌型(hand_basetile)) {
				九莲 = true;
				役满 = true;
			}
		} while (false);
	}

	if (国士13) {
		all_手役.push_back({ { Yaku::国士无双十三面 }, 0 });
	}
	else if (国士) {
		all_手役.push_back({ { Yaku::国士无双 }, 0 });
	}
	else if (九莲纯) {
		all_手役.push_back({ { Yaku::纯正九莲宝灯 }, 0 });
	}
	else if (九莲) {
		all_手役.push_back({ { Yaku::九莲宝灯 }, 0 });
	}
	else {
		/* 并非以上情况的手役判断 */
		
		// 接下来对牌进行拆解
		auto complete_tiles_list = get_completed_tiles(hand_basetile);

		/* 移除多余的complete_tiles */
		sort(complete_tiles_list.begin(), complete_tiles_list.end(),
			[](CompletedTiles c1, CompletedTiles c2) {
				return c1 < c2;
			});
		complete_tiles_list.erase(unique(complete_tiles_list.begin(), complete_tiles_list.end()), complete_tiles_list.end());

		/* 统计七对子*/
		if (is七对和牌型(hand_basetile)) {
			// 即使是役满这里也要纳入考虑，因为存在大七星
			CompletedTiles ct;
			for (int i = 0; i < 14; i += 2) {
				TileGroup tg;
				tg.type = TileGroup::Toitsu;
				tg.set_tiles({ handcopy[i]->tile, handcopy[i]->tile });
				ct.body.push_back(tg);
			}
			complete_tiles_list.push_back(ct);
		}
		// 接下来

		for (auto &complete_tiles : complete_tiles_list) {
			auto yaku_fus = get_手役_from_complete_tiles(complete_tiles, player.副露s, correspond_tile, player.hand.back()->tile, 自风, 场风, 门清, 役满);
			merge_into(all_手役, yaku_fus);
		}
	}

	if (!役满) { // 所有可能性中都没有役满的话，继续判定场役
		/* riichi 和 double riichi 不重复计算 */
		if (player.double_riichi)
			场役.push_back(Yaku::两立直);
		else if (player.riichi)
			场役.push_back(Yaku::立直);

		/* 海底的条件是1. remain_tile == 0, 2. 上一手不是杠相关 */
		if (tsumo && table->get_remain_tile() == 0 &&
			table->last_action != BaseAction::暗杠 &&
			table->last_action != BaseAction::杠 &&
			table->last_action != BaseAction::加杠) {
			场役.push_back(Yaku::海底捞月);
		}
		if (!tsumo && table->get_remain_tile() == 0) {
			场役.push_back(Yaku::河底捞鱼);
		}

		/* 如果是抢杠，那么计算抢杠 */
		if (抢杠 || 抢暗杠) {
			场役.push_back(Yaku::抢杠);
		}

		/* 如果上一轮动作是杠，这一轮是tsumo，那么就是岭上 */
		if (table->last_action == BaseAction::暗杠 ||
			table->last_action == BaseAction::加杠 ||
			table->last_action == BaseAction::杠) {
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

		/* dora役 */
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

		if (correspond_tile && correspond_tile->red_dora == true) {
			Dora役.push_back(Yaku::赤宝牌);
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

			if (correspond_tile && correspond_tile->tile == doratile) {
				Dora役.push_back(Yaku::宝牌);
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

				if (correspond_tile && correspond_tile->tile == doratile) {
					Dora役.push_back(Yaku::里宝牌);
				}
			}
		}
	}
	for (auto& yaku_fu : all_yaku_fu_cases) {
		if (役满) {
			merge_into(yaku_fu.first, 天地和);			
		}
		else {
			merge_into(yaku_fu.first, 场役);
			merge_into(yaku_fu.first, Dora役);
		}
	}

	//对于AllYakusAndFu，判定番最高的，番相同的，判定符最高的	
	auto iter = max_element(all_yaku_fu_cases.begin(), all_yaku_fu_cases.end(), 
		[](const pair<vector<Yaku>, int> &yaku_fu1, const pair<vector<Yaku>, int> &yaku_fu2) {
		auto fan1 = calculate_fan(yaku_fu1.first);
		auto fan2 = calculate_fan(yaku_fu2.first);
		if (fan1 < fan2) return true;
		if (fan1 > fan2) return false;
		// 如果番数一样则判断符
		return yaku_fu1.second < yaku_fu2.second;
		});

	if (iter == all_yaku_fu_cases.end()) {
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
		if (table->庄家 == table->turn) 亲家 = true;

		final_result.calculate_score(亲家, tsumo);
	}
	return final_result;
}

//CounterResult yaku_counter_v2(Table *table, Player &player, Tile* correspond_tile, bool 抢杠, bool 抢暗杠, Wind 自风, Wind 场风)
//{
//	// from 2022.3.19
//
//	/* step 0 : 初始化 */
//	bool tsumo;	 // 是自摸吗
//	bool menchin = player.门清;
//	BaseTile last_tile;  // 最后取得的牌，既可以是荣和，也可以是自摸
//	vector<BaseTile> final_hand = convert_tiles_to_basetiles(player.hand);
//
//	if (correspond_tile == nullptr) {
//		tsumo = true;
//		last_tile = player.hand.back()->tile;
//	}
//	else {
//		tsumo = false;
//		last_tile = correspond_tile->tile;
//	}
//
//	/* step 1 : 处理国士 */
//
//}

namespace_mahjong_end


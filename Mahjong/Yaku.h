#ifndef YAKU_H
#define YAKU_H
#include <vector>
#include <algorithm>
#include <string>
#include <sstream>
#include "Tile.h"

namespace_mahjong

enum class Yaku {	

	// 特指无役
	None,

	立直,
	断幺九,
	门前清自摸和,
	自风_东,
	自风_南,
	自风_西,
	自风_北,
	场风_东,
	场风_南,
	场风_西,
	场风_北,
	役牌_白,
	役牌_发,
	役牌_中,
	平和,
	一杯口,
	抢杠,
	岭上开花,
	海底捞月,
	河底捞鱼,
	一发,
	宝牌,
	里宝牌,
	赤宝牌,
	北宝牌, //仅3人麻将
	混全带幺九副露版,
	一气通贯副露版,
	三色同顺副露版,

	一番,

	两立直,
	三色同刻,
	三杠子,
	对对和,
	三暗刻,
	小三元,
	混老头,		
	七对子,
	混全带幺九,
	一气通贯,
	三色同顺,
	纯全带幺九副露版,
	混一色副露版,

	二番,

	二杯口,
	纯全带幺九,
	混一色, 

	三番,
	
	清一色副露版,

	五番,

	清一色,

	六番,

	流局满贯,

	满贯,

	天和,
	地和,
	大三元,
	四暗刻,
	字一色,
	绿一色,
	清老头,
	国士无双,
	小四喜,
	四杠子,
	九莲宝灯,

	役满,

	四暗刻单骑,
	国士无双十三面,
	纯正九莲宝灯,
	大四喜,

	双倍役满,
};

inline bool can_agari(std::vector<Yaku> yakus) {
	return !all_of(yakus.begin(), yakus.end(), [](Yaku yaku) {
		if (yaku == Yaku::None) return true;
		if (yaku == Yaku::宝牌) return true;
		if (yaku == Yaku::赤宝牌) return true;
		if (yaku == Yaku::里宝牌) return true;
		if (yaku == Yaku::北宝牌) return true;
		return false;
	});
}

inline std::string yaku_to_string(Yaku yaku) {
	static std::vector<std::string> yaku_name = {
		// 特指无役
		"无役",

		"立直",
		"断幺九",
		"门前清自摸和",
		"自风_东",
		"自风_南",
		"自风_西",
		"自风_北",
		"场风_东",
		"场风_南",
		"场风_西",
		"场风_北",
		"役牌_白",
		"役牌_发",
		"役牌_中",
		"平和",
		"一杯口",
		"抢杠",
		"岭上开花",
		"海底捞月",
		"河底捞鱼",
		"一发",
		"宝牌",
		"里宝牌",
		"赤宝牌",
		"北宝牌",
		"混全带幺九副露版",
		"一气通贯副露版",
		"三色同顺副露版",

		"一番",

		"两立直",
		"三色同刻",
		"三杠子",
		"对对和",
		"三暗刻",
		"小三元",
		"混老头",
		"七对子",
		"混全带幺九",
		"一气通贯",
		"三色同顺",
		"纯全带幺九副露版",
		"混一色副露版",

		"二番",

		"二杯口",
		"纯全带幺九",
		"混一色",

		"三番",

		"清一色副露版",

		"五番",

		"清一色",

		"六番",

		"流局满贯",

		"满贯",

		"天和",
		"地和",
		"大三元",
		"四暗刻",
		"字一色",
		"绿一色",
		"清老头",
		"国士无双",
		"小四喜",
		"四杠子",
		"九莲宝灯",

		"役满",

		"四暗刻单骑",
		"国士无双十三面",
		"纯正九莲宝灯",
		"大四喜",

		"双倍役满"
	};
	return yaku_name[(int)yaku];
}

inline std::string yakus_to_string(std::vector<Yaku> yakus) {
	std::stringstream ss;
	ss << "|";
	for (auto yaku : yakus) {
		ss << yaku_to_string(yaku)<<"|";
	}
	return ss.str();
}

namespace_mahjong_end

#endif

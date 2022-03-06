#ifndef YAKU_H
#define YAKU_H
#include <vector>
#include <algorithm>
#include <string>
enum class Yaku {	

	// 特指无役
	None,

	Riichi,
	Tanyao,
	Menzentsumo,
	Jikaze_Ton,
	Jikaze_Nan,
	Jikaze_Sha,
	Jikaze_Pei,
	Bakaze_Ton,
	Bakaze_Nan,
	Bakaze_Sha,
	Bakaze_Pei,
	Yakuhai_Haku,
	Yakuhai_Hatsu,
	Yakuhai_Chu,
	Pinfu,
	Ippeikou,
	Chankan,
	Rinshankaihou,
	Haiteiraoyue,
	Houteiraoyu,
	Ippatsu,
	Dora,
	Uradora,
	Akadora,
	Peidora, //仅3人麻将
	Honchantaiyaochu_Naki,
	Ikkitsuukan_Naki,
	Sanshokudoujun_Naki,

	Yaku_1_han,

	Dabururiichi,
	Sanshokudoukou,
	Sankantsu,
	Toitoiho,
	Sanankou,
	Shousangen,
	Honroutou,		
	Chiitoitsu,
	Honchantaiyaochu,
	Ikkitsuukan,
	Sanshokudoujun,
	Junchantaiyaochu_Naki,
	Honitsu_Naki,

	Yaku_2_han,

	Rianpeikou,
	Junchantaiyaochu,
	Honitsu, 

	Yaku_3_han,
	
	Chinitsu_Naki,

	Yaku_5_han,

	Chinitsu,

	Yaku_6_han,

	Nagashimangan,

	Yaku_mangan,

	Tenhou,
	Chihou,
	Daisangen,
	Siiankou,
	Tsuiisou,
	Ryuiisou,
	Chinroutou,
	Kokushimusou,
	Shousuushi,
	Siikantsu,
	Chuurenpoutou,

	Yakuman,

	Siiankou_1,
	Koukushimusou_13,
	Chuurenpoutou_9,
	Daisuushi,

	Yakuman_Double,
};

inline bool can_agari(std::vector<Yaku> yakus) {
	return !all_of(yakus.begin(), yakus.end(), [](Yaku yaku) {
		if (yaku == Yaku::None) return true;
		if (yaku == Yaku::Dora) return true;
		if (yaku == Yaku::Akadora) return true;
		if (yaku == Yaku::Uradora) return true;
		if (yaku == Yaku::Peidora) return true;
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

#include <sstream>
inline std::string yakus_to_string(std::vector<Yaku> yakus) {
	std::stringstream ss;
	ss << "|";
	for (auto yaku : yakus) {
		ss << yaku_to_string(yaku)<<"|";
	}
	return ss.str();
}

#endif

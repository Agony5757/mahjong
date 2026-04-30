#ifndef YAKU_DETECTOR_H
#define YAKU_DETECTOR_H

#include <vector>
#include "Yaku.h"
#include "macro.h"

namespace_mahjong

/**
 * YakuDetector — pure-function yaku (役) detectors.
 *
 * Extracted from get_hand_yakus() and get_hand_yakuman().
 * All functions are pure: they accept only tile group strings and
 * wind information, with no side effects.
 *
 * Design: returns Yaku directly; Yaku::None signals "not applicable".
 * This avoids std::optional (C++17) while keeping a clean interface.
 *
 * Tile group string format (from ScoreCounter.h):
 *   {digit}{suit}{mark}            e.g. "1mS", "5zK", "1z:"
 *   {digit}{suit}{mark}{pos}       e.g. "1mS!", "5zK$", "2z:+"
 *   Marks: S=shuntsu, K=koutsu, :=toitsu, |=kantsu
 *   Pos:   !@#=tsumo 1st/2nd/3rd, $%^=ron 1st/2nd/3rd, -=minkan, +=ankan
 *
 * Wind indices: 0=E, 1=S, 2=W, 3=N, 4=White, 5=Green, 6=Red
 *
 * Reference: https://en.wikipedia.org/wiki/Yaku_(mahjong)
 */

namespace yaku_detector {

// ─── Statistics helpers ─────────────────────────────────────────────────────

/**
 * Fill z_koutsu_out[7] with true where a koutsu/kantsu of honor z[i] exists.
 * z_koutsu_out must be pre-allocated (size 7).
 */
void count_z_koutsu(const std::vector<std::string>& tgs, bool z_koutsu_out[7]);

/**
 * Fill z_toitsu_out[7] with true where a toitsu of honor z[i] exists.
 * z_toitsu_out must be pre-allocated (size 7).
 */
void count_z_toitsu(const std::vector<std::string>& tgs, bool z_toitsu_out[7]);

/**
 * Returns true if every tile group consists only of honor tiles (z).
 */
bool is_all_honor(const std::vector<std::string>& tgs);

/**
 * Returns true if every tile group consists only of terminal tiles (1/9).
 * (Excludes honor tiles.) Used for chinroutou.
 */
bool is_all_terminals(const std::vector<std::string>& tgs);

/**
 * Returns true if every tile group is either an honor tile
 * or a terminal-only koutsu/kantsu. Used for honroutou.
 */
bool is_honroutou(const std::vector<std::string>& tgs);

/**
 * Returns true if all tgs are green tiles (绿一色).
 * Green tiles: 2-4-6-8s + 6z (green dragon).
 */
bool is_pure_green(const std::vector<std::string>& tgs);

/**
 * Returns true if tgs has a single-wait (单骑).
 * Detected by: a toitsu (':') with a position mark (size==4).
 */
bool has_single_wait(const std::vector<std::string>& tgs);

/**
 * Count closed koutsu in tgs.
 * Closed koutsu: size==3 with 'K', or koutsu with tsumo mark, or ankan (+).
 */
int count_closed_koutsu(const std::vector<std::string>& tgs);

/**
 * Count kantsu (杠子) in tgs.
 */
int count_kantsu(const std::vector<std::string>& tgs);

/**
 * Returns true if tgs has no terminals (1/9) and no honor tiles (z).
 * Used for tanyao (断幺九).
 */
bool has_no_terminals_or_honors(const std::vector<std::string>& tgs);

/**
 * Returns true if all tgs are in the same suit (万/筒/索).
 * Checks suit char at position [1] of each tgs.
 */
bool is_same_suit(const std::vector<std::string>& tgs, char suit);

/**
 * Count shuntsu groups in tgs.
 */
int count_shuntsu(const std::vector<std::string>& tgs);

// ─── Individual yaku detectors ─────────────────────────────────────────────────
// All return Yaku directly; Yaku::None means "not applicable".
// For yakuhai (which can have multiple values), see detect_yakuhai() below.

/** 七对子 (Chiitoitsu) — seven pairs. Fan: 2 */
Yaku detect_chiitoitsu(const std::vector<std::string>& tgs);

/** 对对和 (Toitoiho) — all koutsu/kantsu, no shuntsu. Fan: 2 */
Yaku detect_toitoiho(const std::vector<std::string>& tgs);

/** 断幺九 (Tanyao) — no terminals/honors. Fan: 1 */
Yaku detect_tanyao(const std::vector<std::string>& tgs);

/**
 * 清一色 (Chinitsu) — all tiles in one suit, no honors.
 * Fan: 6 (closed) / 5 (called)
 */
Yaku detect_chinitsu(const std::vector<std::string>& tgs, bool menzen);

/**
 * 混一色 (Honitsu) — all tiles in one suit + honors.
 * Fan: 3 (closed) / 2 (called)
 */
Yaku detect_honitsu(const std::vector<std::string>& tgs, bool menzen);

/**
 * 三色同顺 (Sanshokudoujun) — same sequence across m/p/s.
 * Fan: 2 (closed) / 1 (called)
 */
Yaku detect_sanshoku_doujun(const std::vector<std::string>& tgs, bool menzen);

/** 三色同刻 (Sanshokudoukou) — same koutsu across m/p/s. Fan: 2 */
Yaku detect_sanshoku_doukou(const std::vector<std::string>& tgs);

/**
 * 一气通贯 (Ikkitsuukan) — 1-4-7 in one suit.
 * Fan: 2 (closed) / 1 (called)
 */
Yaku detect_ittsuu(const std::vector<std::string>& tgs, bool menzen);

/**
 * 一杯口 / 二杯口 (Ippeikou / Rianpeikou).
 * Fan: 1 / 3.  Requires menzen.
 */
Yaku detect_peikou(const std::vector<std::string>& tgs, bool menzen);

/** 三暗刻 (Sanankou) — 3 closed koutsu. Fan: 2 */
Yaku detect_sanankou(const std::vector<std::string>& tgs);

/** 三杠子 (Sankantsu) — 3 kantsu. Fan: 2 */
Yaku detect_sankantsu(const std::vector<std::string>& tgs);

/** 混老头 (Honroutou) — all terminals + honors. Fan: 2 */
Yaku detect_honroutou(const std::vector<std::string>& tgs);

/**
 * 纯全带幺 (Junchan) — all groups have 1 or 9.
 * Fan: 3 (closed) / 2 (called)
 */
Yaku detect_junchan(const std::vector<std::string>& tgs, bool menzen);

/**
 * 混全带幺 (Chanta) — all groups have 1/9 or honors.
 * Fan: 2 (closed) / 1 (called)
 */
Yaku detect_chanta(const std::vector<std::string>& tgs, bool menzen);

/**
 * 小三元 (Shousangen) — 2 koutsu of dragons + 1 toitsu of the remaining dragon.
 * Fan: 2
 */
Yaku detect_shousangen(const bool z_koutsu[7], const bool z_toitsu[7]);

/**
 * 役牌 (Yakuhai) — dragon koutsu + seat/game wind koutsu.
 * Fan: 1 each.  Returns all applicable yakus.
 */
void detect_yakuhai(const bool z_koutsu[7], Wind self_wind, Wind game_wind,
                    Yaku yakus_out[7], int& yakus_out_count);

/**
 * 平和 (Pinfu) — all shuntsu + non-yakuhai toitsu + ryanmen/tanki wait.
 * Fan: 1.  Requires menzen.
 */
Yaku detect_pinfu(const std::vector<std::string>& tgs, Wind self_wind, Wind game_wind);

// ─── Yakuman detectors ────────────────────────────────────────────────────────

/** 字一色 (Tsuiisou) — all honor tiles. Yakuman */
Yaku detect_tsuiisou(bool all_honor);

/** 大三元 (Daisangen) — all 3 dragon koutsu. Yakuman */
Yaku detect_daisangen(const bool z_koutsu[7]);

/** 大四喜 (Daisuushi) — all 4 wind koutsu. Yakuman */
Yaku detect_daisuushi(const bool z_koutsu[7]);

/** 小四喜 (Shousuushi) — 3 wind koutsu + 1 wind toitsu. Yakuman */
Yaku detect_shousuushi(const bool z_koutsu[7], const bool z_toitsu[7]);

/** 四暗刻 (Suuankou) — 4 closed koutsu. Yakuman */
Yaku detect_suuankou(int closed_koutsu_count, bool single_wait);

/** 四杠子 (Suukantsu) — 4 kantsu. Yakuman */
Yaku detect_suukantsu(int kantsu_count);

/** 清老头 (Chinroutou) — all terminals, no honors. Yakuman */
Yaku detect_chinroutou(bool all_terminals);

/** 绿一色 (Ryuiisou) — all green tiles. Yakuman */
Yaku detect_ryuiisou(bool pure_green);

/**
 * Detect all yakuman applicable to the hand.
 * @param tgs         tile group strings
 * @param self_wind   player's seat wind
 * @param game_wind   current game wind
 * @param yakuman_out [out] true if any yakuman was found
 * @param yakus_out   [out] array of yakuman yakus found (capacity 8)
 * @return            count of yakuman yakus found
 */
int detect_all_yakuman(const std::vector<std::string>& tgs,
                       Wind self_wind, Wind game_wind,
                       bool& yakuman_out,
                       Yaku yakus_out[8]);

// ─── Aggregated detector ──────────────────────────────────────────────────────

/**
 * Given a complete tile group string, append all applicable non-yakuman
 * hand yakus to the yakus_out vector (does NOT clear it).
 * Fan-based yaku only; no dora or state yakus.
 */
void detect_all_hand_yakus(const std::vector<std::string>& tgs,
                           Wind self_wind, Wind game_wind, bool menzen,
                           std::vector<Yaku>& yakus_out);

}  // namespace yaku_detector

namespace_mahjong_end

#endif  // YAKU_DETECTOR_H

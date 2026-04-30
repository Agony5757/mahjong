#ifndef FU_CALCULATOR_H
#define FU_CALCULATOR_H

#include <vector>
#include "macro.h"

namespace_mahjong

/**
 * FuCalculator — pure-function fu (符) calculator.
 *
 * Extracted from get_hand_yakus() to isolate the fu calculation logic.
 * All functions are pure (no side effects).
 *
 * Fu breakdown (standard Riichi Mahjong):
 *   Base fu:    20 (menzen) or 20 (fuuro) — both start at 20
 *   Wait type:  tanki (+2), penchan (+2), kanchan (+2)
 *   Win method: tsumo (+2, non-pinfu), ron (+10, fuuro)
 *   Head:       yakuhai toitsu (+2 per)
 *   Melds:      koutsu  yaochu(+8) / others(+4)
 *               minkou  yaochu(+4) / others(+2)
 *               ankou   yaochu(+8) / others(+4)  -- tsumo pon
 *               minkan  yaochu(+16)/ others(+8)
 *               ankan   yaochu(+32)/ others(+16)
 *   Round up:   fu = ((fu + 9) / 10) * 10   (not applied to chiitoitsu)
 *
 * Reference: https://en.wikipedia.org/wiki/Fu_(mahjong)
 */

namespace fu_calculator {

/**
 * Calculate fu for a completed hand.
 *
 * @param tgs           tile group strings (with position marks)
 * @param self_wind     player's seat wind
 * @param game_wind     current game wind
 * @param menzen        true if hand is closed (no fuuro calls)
 * @param is_pinfu      true if pinfu yaku was detected (affects tsumo fu)
 * @return              fu value, already rounded to nearest 10
 */
int calculate_fu(
    const std::vector<std::string>& tgs,
    Wind self_wind, Wind game_wind,
    bool menzen, bool is_pinfu
);

/**
 * Fu from agari shape (tanki / penchan / kanchan).
 */
int fu_from_wait_shape(const std::vector<std::string>& tgs);

/**
 * Fu from winning method (tsumo / ron).
 * @param tgs       tile group strings
 * @param menzen    hand is closed
 * @param is_pinfu  pinfu detected (tsumo gives no fu if pinfu)
 */
int fu_from_winning_method(
    const std::vector<std::string>& tgs,
    bool menzen, bool is_pinfu
);

/**
 * Fu from head (toitsu) — yakuhai toitsu gives +2 fu each.
 */
int fu_from_head(
    const std::vector<std::string>& tgs,
    Wind self_wind, Wind game_wind
);

/**
 * Fu from melds (koutsu / shuntsu / kantsu).
 * Handles both closed (ankou) and called (minkou/minkan) melds.
 */
int fu_from_melds(const std::vector<std::string>& tgs);

/**
 * Round fu up to the nearest 10.
 * Returns fu unchanged if already a multiple of 10.
 * NOTE: chiitoitsu (7 toitsu) uses fixed 25 fu, not rounded.
 */
int round_up_fu(int fu);

/**
 * Returns true if the hand is chiitoitsu (七对子, 7 toitsu).
 */
bool is_chiitoitsu(const std::vector<std::string>& tgs);

/**
 * Returns true if the hand has a kanchan wait (隔 Loret).
 * A kanchan is a middle wait on a shuntsu: e.g. waiting on 5 in 3-4-5.
 * Detected by: shuntsu with mark '@' (tsumo 2nd) or '%' (ron 2nd).
 */
bool has_kanchan_wait(const std::vector<std::string>& tgs);

/**
 * Returns true if the hand has a penchan wait (边张).
 * A penchan is a wait on 1-2-3 or 7-8-9: waiting on 1 or 3 in 1-2-3.
 * Detected by: shuntsu starting with 1 or 7 with mark '#', '^', '!', '$'.
 */
bool has_penchan_wait(const std::vector<std::string>& tgs);

}  // namespace fu_calculator

namespace_mahjong_end

#endif  // FU_CALCULATOR_H

#ifndef SCORE_TABLE_H
#define SCORE_TABLE_H

#include <cstddef>
#include "macro.h"

namespace_mahjong

/**
 * ScoreTable — data-driven score lookup.
 *
 * Replaces the if-else cascade in CounterResult::calculate_score()
 * with O(1) table lookups.
 *
 * 符计算公式：
 *   score1 = oya_ron           (亲荣和)
 *   score1 = oya_tsumo         (亲自摸，全员支付)
 *   score1 = child_ron         (子荣和)
 *   score1 = child_tsumo_oya   (子自摸，亲支付)
 *   score2 = child_tsumo_child (子自摸，子支付)
 *
 * For tsumo, score2 is only non-zero for child payers.
 * A value of -1 means "invalid for this fan/fu combination".
 */

struct ScoreEntry {
    int fan_min;                // inclusive lower bound on fan
    int fan_max;                // inclusive upper bound on fan
    int fu_min;                 // inclusive lower bound on fu
    int fu_max;                 // inclusive upper bound on fu
    int oya_ron;
    int oya_tsumo;
    int child_ron;
    int child_tsumo_oya;        // child tsumo: oya pays this
    int child_tsumo_child;     // child tsumo: each child pays this
};

namespace score_table {

/**
 * Look up score for a (fan, fu, oya, tsumo) combination.
 * Writes to score1 (and score2 for child tsumo).
 * Throws std::runtime_error if the combination is not found.
 */
void calculate_score(int fan, int fu, bool oya, bool tsumo,
                    int& score1, int& score2);

/**
 * Human-readable name for a fan level.
 */
const char* fan_level_name(int fan);

}  // namespace score_table

namespace_mahjong_end

#endif  // SCORE_TABLE_H

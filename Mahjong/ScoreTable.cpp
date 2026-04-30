#include "ScoreTable.h"
#include <climits>
#include <limits>
#include <stdexcept>

namespace_mahjong
namespace score_table {

// ─── Score data ────────────────────────────────────────────────────────────────
//
// Each entry gives the score values:
//   oya_ron           — oya wins by ron
//   oya_tsumo         — oya wins by tsumo (all players pay oya_ron)
//   child_ron         — child wins by ron (oya pays child_ron)
//   child_tsumo_oya   — child tsumo: oya pays this
//   child_tsumo_child — child tsumo: each child pays this
//
// A value of -1 means "invalid / use oya_ron/2 rounded up".
// Entries are ordered by fan_min descending (checked first-match).
// For fan 1-4, fu sub-tables are ordered by fu_max descending.

static const ScoreEntry FAN_TABLE[] = {
    // fan >= 13: yakuman (1x through kx)
    {13, INT_MAX, 20, INT_MAX, 48000, 16000, 32000, 16000, 8000},
    // fan 11-12: sanbai mangan
    {11, 12, 20, INT_MAX, 36000, 12000, 24000, 12000, 6000},
    // fan 8-10: hanbaiman
    { 8, 10, 20, INT_MAX, 24000,  8000, 16000,  8000, 4000},
    // fan 6-7: baiman
    { 6,  7, 20, INT_MAX, 18000,  6000, 12000,  6000, 3000},
    // fan 5: hanmangan
    { 5,  5, 20, INT_MAX, 12000,  4000,  8000,  4000, 2000},
};

static const size_t FAN_TABLE_SIZE = sizeof(FAN_TABLE) / sizeof(FAN_TABLE[0]);

// Fu sub-tables for fan 4, 3, 2, 1 (ordered by fu_max descending)

static const ScoreEntry FU_4_TABLE[] = {
    {40, INT_MAX, 12000, 4000, 8000, 4000, 2000},   // mangan
    {30, 39,     11600, 3900, 7700, 3900, 2000},
    {25, 29,      9600, 3200, 6400, 3200, 1600},
    {20, 24,      7700, 2600, 5200, 2600, 1300},
};

static const ScoreEntry FU_3_TABLE[] = {
    {70, INT_MAX, 12000, 4000, 8000, 4000, 2000},   // mangan
    {60, 69,     11600, 3900, 7700, 3900, 2000},
    {50, 59,      9600, 3200, 6400, 3200, 1600},
    {40, 49,      7700, 2600, 5200, 2600, 1300},
    {30, 39,      5800, 2000, 3900, 2000, 1000},
    {25, 29,      4800, 1600, 3200, 1600,  800},
    {20, 24,      3900, 1300, 2600, 1300,  700},
};

static const ScoreEntry FU_2_TABLE[] = {
    {110, INT_MAX, 10600, 3600, 7100, 3600, 1800},
    {100, 109,     9600, 3200, 6400, 3200, 1600},
    { 90,  99,     8700, 2900, 5800, 2900, 1500},
    { 80,  89,     7700, 2600, 5200, 2600, 1300},
    { 70,  79,     6800, 2300, 4500, 2300, 1200},
    { 60,  69,     5800, 2000, 3900, 2000, 1000},
    { 50,  59,     4800, 1600, 3200, 1600,  800},
    { 40,  49,     3900, 1300, 2600, 1300,  700},
    { 30,  39,     2900, 1000, 2000, 1000,  500},
    { 25,  29,     2400,  800, 1600,  800,  400},
    { 20,  24,     2000,  700, 1300,  700,  400},
};

static const ScoreEntry FU_1_TABLE[] = {
    {110, INT_MAX,  5300, 1800, 3600, 1800, 900},
    {100, 109,      4800, 1600, 3200, 1600, 800},
    { 90,  99,      4400, 1500, 2900, 1500, 800},
    { 80,  89,      3900, 1300, 2600, 1300, 700},
    { 70,  79,      3400, 1200, 2300, 1200, 600},
    { 60,  69,      2900, 1000, 2000, 1000, 500},
    { 50,  59,      2400,  800, 1600,  800, 400},
    { 40,  49,      2000,  700, 1300,  700, 400},
    { 30,  39,      1500,  500, 1000,  500, 300},
    { 20,  29,      1000,  500,  700,  500, 300},  // fu=20: oya_tsumo = 500 (1000/2 rounded up)
};

static const size_t FU_1_SIZE = sizeof(FU_1_TABLE) / sizeof(FU_1_TABLE[0]);
static const size_t FU_2_SIZE = sizeof(FU_2_TABLE) / sizeof(FU_2_TABLE[0]);
static const size_t FU_3_SIZE = sizeof(FU_3_TABLE) / sizeof(FU_3_TABLE[0]);
static const size_t FU_4_SIZE = sizeof(FU_4_TABLE) / sizeof(FU_4_TABLE[0]);

static const ScoreEntry* fu_table_for_fan(int fan, size_t* out_size) {
    switch (fan) {
        case 4: *out_size = FU_4_SIZE; return FU_4_TABLE;
        case 3: *out_size = FU_3_SIZE; return FU_3_TABLE;
        case 2: *out_size = FU_2_SIZE; return FU_2_TABLE;
        case 1: *out_size = FU_1_SIZE; return FU_1_TABLE;
        default: *out_size = 0; return nullptr;
    }
}

// Round up x to the nearest 100.  Used for child tsumo payments.
static int round100(int x) {
    if (x % 100 == 0) return x;
    return (x / 100 + 1) * 100;
}

void calculate_score(int fan, int fu, bool oya, bool tsumo,
                    int& score1_out, int& score2_out) {
    int score1 = 0, score2 = 0;

    // ── 1. Fan-based table (covers mangan and above, fan >= 5) ──────────────
    for (size_t i = 0; i < FAN_TABLE_SIZE; ++i) {
        const ScoreEntry& e = FAN_TABLE[i];
        if (fan >= e.fan_min) {
            int mult = (fan >= 13) ? (fan / 13) : 1;
            if (oya) {
                score1 = tsumo ? (e.oya_tsumo * mult) : (e.oya_ron * mult);
            } else {
                score1 = tsumo ? (e.child_tsumo_oya * mult) : (e.child_ron * mult);
                score2 = tsumo ? (e.child_tsumo_child * mult) : 0;
            }
            score1_out = score1;
            score2_out = score2;
            return;
        }
    }

    // ── 2. Fu sub-table (fan 1-4) ────────────────────────────────────────────
    size_t table_size = 0;
    const ScoreEntry* table = fu_table_for_fan(fan, &table_size);
    if (!table) {
        throw std::runtime_error(
            fmt::format("Error fan & fu cases. {} fan {} fu.", fan, fu));
    }

    const ScoreEntry* entry = nullptr;
    for (size_t i = 0; i < table_size; ++i) {
        if (fu <= table[i].fu_max) {
            entry = &table[i];
            break;
        }
    }

    if (!entry) {
        throw std::runtime_error(
            fmt::format("Error fan & fu cases. {} fan {} fu.", fan, fu));
    }

    int oya_ron = entry->oya_ron;

    if (oya) {
        // Oya: score1 = oya_ron (ron) or oya_tsumo (tsumo)
        if (tsumo) {
            if (entry->oya_tsumo < 0) {
                // Round up oya_ron/2 to nearest 100
                score1 = round100((oya_ron + 1) / 2);
            } else {
                score1 = entry->oya_tsumo;
            }
        } else {
            score1 = oya_ron;
        }
        score2_out = 0;
        score1_out = score1;
        return;
    }

    // Child payer
    if (tsumo) {
        // child tsumo: oya pays child_tsumo_oya, each child pays child_tsumo_child
        if (entry->child_tsumo_oya < 0) {
            // Round up oya_ron/2 to nearest 100
            score1 = round100((oya_ron + 1) / 2);  // oya pays
        } else {
            score1 = entry->child_tsumo_oya;
        }
        if (entry->child_tsumo_child < 0) {
            // Round up oya_ron/2 to nearest 100
            score2 = round100((oya_ron + 1) / 2);  // each child pays
        } else {
            score2 = entry->child_tsumo_child;
        }
    } else {
        // child ron: oya pays child_ron
        score1 = entry->child_ron;
        score2 = 0;
    }

    score1_out = score1;
    score2_out = score2;
}

const char* fan_level_name(int fan) {
    if (fan >= 13) return "役满";
    if (fan >= 11) return "数倍役满";
    if (fan >=  8) return "三倍满";
    if (fan >=  6) return "倍满";
    if (fan >=  5) return "跳满";
    if (fan >=  4) return "满贯";
    if (fan >=  3) return "满贯";
    return "满贯以下";
}

}  // namespace score_table
namespace_mahjong_end

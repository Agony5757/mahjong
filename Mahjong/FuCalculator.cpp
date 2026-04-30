#include "FuCalculator.h"
#include <algorithm>

namespace_mahjong
namespace fu_calculator {

// ─── Helper predicates ─────────────────────────────────────────────────────────

// Returns true if a tgs contains at least one terminal or honor tile.
// Used to distinguish yaochu from chunchan melds.
static bool has_yaochu_or_z(const std::string& s) {
    if (s.size() < 2) return false;
    if (s[1] == 'z') return true;
    if (s[0] == '1' || s[0] == '9') return true;
    return false;
}

// Returns the number of cases for a yakuhai toitsu (役牌对子).
// 1 if seat wind, 1 if game wind, 1 if dragon (total up to 3).
static int yakuhai_toitsu_cases(const std::string& s, Wind self_wind, Wind game_wind) {
    if (s.size() < 3 || s[2] != ':' || s[1] != 'z') return 0;
    int n = s[0] - '1';  // 0-3: winds; 4-6: dragons
    int cases = 0;
    if (n == self_wind) cases++;
    if (n == game_wind) cases++;
    if (n >= 4) cases++;  // dragons always count
    return cases;
}

// ─── Wait shape helpers ───────────────────────────────────────────────────────

bool has_single_wait(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs) {
        if (s.size() == 4 && s[2] == ':') return true;
    }
    return false;
}

bool has_kanchan_wait(const std::vector<std::string>& tgs) {
    // Kanchan: waiting on the middle tile of a shuntsu.
    // Marked as '@' (tsumo 2nd) or '%' (ron 2nd).
    for (const auto& s : tgs) {
        if (s.size() == 4 && s[2] == 'S') {
            if (s[3] == '@' || s[3] == '%') return true;
        }
    }
    return false;
}

bool has_penchan_wait(const std::vector<std::string>& tgs) {
    // Penchan: waiting on 1 or 7 in 1-2-3 or 7-8-9 sequence.
    // Marked as: '#', '^' (tsumo/ron 3rd for 123) or '!', '$' (1st for 123/789).
    for (const auto& s : tgs) {
        if (s.size() == 4 && s[2] == 'S') {
            if (s[0] == '1' && (s[3] == '#' || s[3] == '^' ||
                                  s[3] == '!' || s[3] == '$')) return true;
            if (s[0] == '7' && (s[3] == '!' || s[3] == '$')) return true;
        }
    }
    return false;
}

// ─── Sub-step: wait shape fu ─────────────────────────────────────────────────

int fu_from_wait_shape(const std::vector<std::string>& tgs) {
    int fu = 0;
    if (has_single_wait(tgs)) fu += 2;   // tanki (单骑)
    if (has_kanchan_wait(tgs)) fu += 2;  // kanchan (坎张)
    if (has_penchan_wait(tgs)) fu += 2;  // penchan (边张)
    return fu;
}

// ─── Sub-step: winning method fu ──────────────────────────────────────────────

bool is_tsumo_wait(const std::vector<std::string>& tgs) {
    // Any tgs has a tsumo position mark ('!', '@', '#')
    for (const auto& s : tgs) {
        if (s.size() == 4) {
            if (s[3] == '!' || s[3] == '@' || s[3] == '#') return true;
        }
    }
    return false;
}

bool is_ron_wait(const std::vector<std::string>& tgs) {
    // Any tgs has a ron position mark ('$', '%', '^')
    for (const auto& s : tgs) {
        if (s.size() == 4) {
            if (s[3] == '$' || s[3] == '%' || s[3] == '^') return true;
        }
    }
    return false;
}

int fu_from_winning_method(const std::vector<std::string>& tgs,
                           bool menzen, bool is_pinfu) {
    int fu = 0;
    if (is_tsumo_wait(tgs) && !is_pinfu) {
        fu += 2;  // tsumo (non-pinfu)
    }
    if (is_ron_wait(tgs) && menzen) {
        fu += 10;  // ron in closed hand
    }
    return fu;
}

// ─── Sub-step: head fu ───────────────────────────────────────────────────────

int fu_from_head(const std::vector<std::string>& tgs,
                 Wind self_wind, Wind game_wind) {
    int fu = 0;
    for (const auto& s : tgs) {
        fu += yakuhai_toitsu_cases(s, self_wind, game_wind) * 2;
    }
    return fu;
}

// ─── Sub-step: meld fu ───────────────────────────────────────────────────────
//
// For koutsu (刻子):  yaochu=8fu, chunchan=4fu
// For minkou (明刻/副露碰): yaochu=4fu, chunchan=2fu
// For ankou/kan (暗刻):    yaochu=8fu, chunchan=4fu
// For minkan (大明杠):    yaochu=16fu, chunchan=8fu
// For ankan (暗杠):        yaochu=32fu, chunchan=16fu
//
// A kantsu with '-' is minkan, '+' is ankan.

static int fu_for_koutsu(bool yaochu) { return yaochu ? 8 : 4; }
static int fu_for_minkou(bool yaochu) { return yaochu ? 4 : 2; }
static int fu_for_minkan(bool yaochu) { return yaochu ? 16 : 8; }
static int fu_for_ankan(bool yaochu)  { return yaochu ? 32 : 16; }

int fu_from_melds(const std::vector<std::string>& tgs) {
    int fu = 0;
    for (const auto& s : tgs) {
        if (s.size() == 3 && s[2] == 'K') {
            // Closed koutsu (暗刻 or 明刻)
            fu += fu_for_koutsu(has_yaochu_or_z(s));
        }
        else if (s.size() == 4) {
            switch (s[2]) {
            case 'S':
                // Shuntsu: no fu
                break;
            case 'K':
                // Pon: either tsumo pon (!@#) or fuuro pon (-)
                if (s[3] == '!' || s[3] == '@' || s[3] == '#') {
                    // Tsumo pon — counted as closed koutsu (ankou)
                    fu += fu_for_koutsu(has_yaochu_or_z(s));
                }
                else if (s[3] == '$' || s[3] == '%' || s[3] == '^' || s[3] == '-') {
                    // Ron pon (including fuuro pon '-')
                    fu += fu_for_minkou(has_yaochu_or_z(s));
                }
                break;
            case '|':
                if (s[3] == '-') {
                    // Minkan (大明杠)
                    fu += fu_for_minkan(has_yaochu_or_z(s));
                }
                else if (s[3] == '+') {
                    // Ankan (暗杠)
                    fu += fu_for_ankan(has_yaochu_or_z(s));
                }
                break;
            }
        }
    }
    return fu;
}

// ─── Round up ─────────────────────────────────────────────────────────────────

int round_up_fu(int fu) {
    if (fu == 25) return fu;  // chiitoitsu: fixed 25 fu, no rounding
    if (fu % 10 == 0) return fu;
    return (fu / 10 + 1) * 10;
}

// ─── Special hand type ────────────────────────────────────────────────────────

bool is_chiitoitsu(const std::vector<std::string>& tgs) {
    return tgs.size() == 7;
}

// ─── Main entry point ────────────────────────────────────────────────────────

int calculate_fu(const std::vector<std::string>& tgs,
                 Wind self_wind, Wind game_wind,
                 bool menzen, bool is_pinfu) {
    int fu = 20;  // base fu

    fu += fu_from_wait_shape(tgs);
    fu += fu_from_winning_method(tgs, menzen, is_pinfu);
    fu += fu_from_head(tgs, self_wind, game_wind);
    fu += fu_from_melds(tgs);

    // Fuuro pinfu: if ron in non-menzen with fu==20, bump to 30
    // (This is the "extra fu" for ron in a hand that would otherwise be 20-fu pinfu)
    if (is_ron_wait(tgs) && !menzen && fu == 20) {
        fu = 30;
    }

    // Pinfu tsumo: always 20 fu
    if (is_pinfu && is_tsumo_wait(tgs)) {
        fu = 20;
    }

    // Chiitoitsu: fixed 25 fu
    if (is_chiitoitsu(tgs)) {
        return 25;
    }

    return round_up_fu(fu);
}

}  // namespace fu_calculator
namespace_mahjong_end

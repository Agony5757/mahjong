#include "YakuDetector.h"
#include <algorithm>

namespace_mahjong
namespace yaku_detector {

// ─── Helpers ─────────────────────────────────────────────────────────────────

static bool is_in_tgs(const std::vector<std::string>& tgs, const char* tile) {
    for (const auto& s : tgs) {
        if (s.size() >= 3 && tile[0] == s[0] && tile[1] == s[1] && tile[2] == s[2])
            return true;
    }
    return false;
}

static bool is_yakuhai_toitsu(const std::string& s, Wind self_wind, Wind game_wind) {
    if (s.size() < 3 || s[2] != ':' || s[1] != 'z') return false;
    int n = s[0] - '1';  // 0-3 for winds, 4-6 for dragons
    int cases = 0;
    if (n == self_wind) cases++;
    if (n == game_wind) cases++;
    if (n >= 4) cases++;  // dragons always count
    return cases > 0;
}

// ─── Statistics helpers ─────────────────────────────────────────────────────

void count_z_koutsu(const std::vector<std::string>& tgs, bool z_koutsu_out[7]) {
    for (int i = 0; i < 7; ++i) z_koutsu_out[i] = false;
    for (const auto& s : tgs) {
        if (s.size() >= 2 && s[1] == 'z') {
            if (s[2] == 'K' || s[2] == '|') {
                z_koutsu_out[s[0] - '1'] = true;
            }
        }
    }
}

void count_z_toitsu(const std::vector<std::string>& tgs, bool z_toitsu_out[7]) {
    for (int i = 0; i < 7; ++i) z_toitsu_out[i] = false;
    for (const auto& s : tgs) {
        if (s.size() >= 2 && s[1] == 'z' && s[2] == ':') {
            z_toitsu_out[s[0] - '1'] = true;
        }
    }
}

bool is_all_honor(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs) {
        if (s.size() < 2 || s[1] != 'z') return false;
    }
    return !tgs.empty();
}

bool is_all_terminals(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs) {
        if (s.size() < 2 || s[1] == 'z') return false;
        if (s[0] != '1' && s[0] != '9') return false;
    }
    return !tgs.empty();
}

bool is_honroutou(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs) {
        if (s.size() < 2) return false;
        if (s[1] == 'z') continue;
        if (s[0] != '1' && s[0] != '9') return false;
    }
    return !tgs.empty();
}

static bool is_green_str(const std::string& s) {
    static const char* green[] = {
        "2sK","3sK","4sK","6sK","8sK","6zK",
        "2sS",
        "2s:", "3s:", "4s:", "6s:", "8s:", "6z:",
        "2s|","3s|","4s|","6s|","8s|","6z|",
    };
    for (const char* g : green) {
        if (s[0] == g[0] && s[1] == g[1] && s[2] == g[2]) return true;
    }
    return false;
}

bool is_pure_green(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs)
        if (!is_green_str(s)) return false;
    return !tgs.empty();
}

bool has_single_wait(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs)
        if (s.size() == 4 && s[2] == ':') return true;
    return false;
}

int count_closed_koutsu(const std::vector<std::string>& tgs) {
    int n = 0;
    for (const auto& s : tgs) {
        if (s.size() == 3 && s[2] == 'K') {
            n++;  // closed koutsu
        } else if (s.size() == 4 && s[2] == 'K' &&
                   (s[3] == '!' || s[3] == '@' || s[3] == '#')) {
            n++;  // tsumo pon
        } else if (s.size() == 4 && s[2] == '|' && s[3] == '+') {
            n++;  // ankan
        }
    }
    return n;
}

int count_kantsu(const std::vector<std::string>& tgs) {
    int n = 0;
    for (const auto& s : tgs)
        if (s[2] == '|') n++;
    return n;
}

bool has_no_terminals_or_honors(const std::vector<std::string>& tgs) {
    for (const auto& s : tgs) {
        if (s[1] == 'z') return false;
        if (s[0] == '1' || s[0] == '9') return false;
    }
    return true;
}

bool is_same_suit(const std::vector<std::string>& tgs, char suit) {
    for (const auto& s : tgs)
        if (s[1] != suit) return false;
    return !tgs.empty();
}

int count_shuntsu(const std::vector<std::string>& tgs) {
    int n = 0;
    for (const auto& s : tgs)
        if (s[2] == 'S') n++;
    return n;
}

// ─── Individual yaku detectors ────────────────────────────────────────────────

Yaku detect_chiitoitsu(const std::vector<std::string>& tgs) {
    if (tgs.size() == 7) return Yaku::Chiitoitsu;
    return Yaku::None;
}

Yaku detect_toitoiho(const std::vector<std::string>& tgs) {
    if (tgs.size() == 7) return Yaku::None;  // chiitoitsu, not toitoiho
    if (count_shuntsu(tgs) > 0) return Yaku::None;
    return Yaku::Toitoiho;
}

Yaku detect_tanyao(const std::vector<std::string>& tgs) {
    if (has_no_terminals_or_honors(tgs)) return Yaku::Tanyao;
    return Yaku::None;
}

Yaku detect_chinitsu(const std::vector<std::string>& tgs, bool menzen) {
    bool m_ok = is_same_suit(tgs, 'm');
    bool p_ok = is_same_suit(tgs, 'p');
    bool s_ok = is_same_suit(tgs, 's');
    if (!m_ok && !p_ok && !s_ok) return Yaku::None;
    return menzen ? Yaku::Chinitsu : Yaku::Chinitsu_Naki;
}

Yaku detect_honitsu(const std::vector<std::string>& tgs, bool menzen) {
    bool m_ok = is_same_suit(tgs, 'm');
    bool p_ok = is_same_suit(tgs, 'p');
    bool s_ok = is_same_suit(tgs, 's');
    bool has_z = false;
    for (const auto& s : tgs) {
        if (s[1] == 'z') { has_z = true; break; }
    }
    if ((m_ok || p_ok || s_ok) && has_z)
        return menzen ? Yaku::Honitsu : Yaku::Honitsu_Naki;
    return Yaku::None;
}

Yaku detect_sanshoku_doujun(const std::vector<std::string>& tgs, bool menzen) {
    for (int i = 0; i < 7; ++i) {
        const char* m_tiles[7] = {"1mS","2mS","3mS","4mS","5mS","6mS","7mS"};
        const char* p_tiles[7] = {"1pS","2pS","3pS","4pS","5pS","6pS","7pS"};
        const char* s_tiles[7] = {"1sS","2sS","3sS","4sS","5sS","6sS","7sS"};
        if (is_in_tgs(tgs, m_tiles[i]) &&
            is_in_tgs(tgs, p_tiles[i]) &&
            is_in_tgs(tgs, s_tiles[i])) {
            return menzen ? Yaku::Sanshokudoujun : Yaku::Sanshokudoujun_Naki;
        }
    }
    return Yaku::None;
}

Yaku detect_sanshoku_doukou(const std::vector<std::string>& tgs) {
    for (int i = 0; i < 9; ++i) {
        const char* m_tiles[9] = {"1mK","2mK","3mK","4mK","5mK","6mK","7mK","8mK","9mK"};
        const char* p_tiles[9] = {"1pK","2pK","3pK","4pK","5pK","6pK","7pK","8pK","9pK"};
        const char* s_tiles[9] = {"1sK","2sK","3sK","4sK","5sK","6sK","7sK","8sK","9sK"};
        if (is_in_tgs(tgs, m_tiles[i]) &&
            is_in_tgs(tgs, p_tiles[i]) &&
            is_in_tgs(tgs, s_tiles[i])) {
            return Yaku::Sanshokudoukou;
        }
    }
    return Yaku::None;
}

Yaku detect_ittsuu(const std::vector<std::string>& tgs, bool menzen) {
    static const char* M_ittsu[3] = {"1mS","4mS","7mS"};
    static const char* P_ittsu[3] = {"1pS","4pS","7pS"};
    static const char* S_ittsu[3] = {"1sS","4sS","7sS"};

    bool m_ok = true, p_ok = true, s_ok = true;
    for (int i = 0; i < 3; ++i) {
        if (!is_in_tgs(tgs, M_ittsu[i])) m_ok = false;
        if (!is_in_tgs(tgs, P_ittsu[i])) p_ok = false;
        if (!is_in_tgs(tgs, S_ittsu[i])) s_ok = false;
    }
    if (m_ok || p_ok || s_ok)
        return menzen ? Yaku::Ikkitsuukan : Yaku::Ikkitsuukan_Naki;
    return Yaku::None;
}

Yaku detect_peikou(const std::vector<std::string>& tgs, bool menzen) {
    if (!menzen) return Yaku::None;
    int n = 0;
    for (const auto& s : tgs) {
        if (s.size() == 3 && s[2] == 'S') {
            int cnt = 0;
            for (const auto& g : tgs)
                if (g.size() == 3 && g[2] == 'S' && g[0] == s[0] && g[1] == s[1]) cnt++;
            if (cnt >= 2) n++;
        }
    }
    if (n >= 2) return Yaku::Rianpeikou;
    if (n == 1) return Yaku::Ippeikou;
    return Yaku::None;
}

Yaku detect_sanankou(const std::vector<std::string>& tgs) {
    if (count_closed_koutsu(tgs) >= 3) return Yaku::Sanankou;
    return Yaku::None;
}

Yaku detect_sankantsu(const std::vector<std::string>& tgs) {
    if (count_kantsu(tgs) >= 3) return Yaku::Sankantsu;
    return Yaku::None;
}

Yaku detect_honroutou(const std::vector<std::string>& tgs) {
    if (is_honroutou(tgs)) return Yaku::Honroutou;
    return Yaku::None;
}

Yaku detect_junchan(const std::vector<std::string>& tgs, bool menzen) {
    for (const auto& s : tgs) {
        if (s.size() < 2) return Yaku::None;
        if (s[1] == 'z') return Yaku::None;  // chanta handles z
        if (s[2] == 'S') {
            if (s[0] != '1' && s[0] != '7') return Yaku::None;
        } else {
            if (s[0] != '1' && s[0] != '9') return Yaku::None;
        }
    }
    return menzen ? Yaku::Junchantaiyaochu : Yaku::Junchantaiyaochu_Naki;
}

Yaku detect_chanta(const std::vector<std::string>& tgs, bool menzen) {
    // Already handled junchan above; here we need honroutou case excluded
    bool all_yaochu_or_z = true;
    for (const auto& s : tgs) {
        if (s.size() < 2) { all_yaochu_or_z = false; break; }
        if (s[1] == 'z') continue;
        if (s[2] == 'S') {
            if (s[0] != '1' && s[0] != '7') { all_yaochu_or_z = false; break; }
        } else {
            if (s[0] != '1' && s[0] != '9') { all_yaochu_or_z = false; break; }
        }
    }
    if (all_yaochu_or_z)
        return menzen ? Yaku::Honchantaiyaochu : Yaku::Honchantaiyaochu_Naki;
    return Yaku::None;
}

Yaku detect_shousangen(const bool z_koutsu[7], const bool z_toitsu[7]) {
    int koutsu_count = 0;
    int toitsu_idx = -1;
    for (int i = 4; i <= 6; ++i) {
        if (z_koutsu[i]) koutsu_count++;
        if (z_toitsu[i]) toitsu_idx = i;
    }
    if (koutsu_count == 2 && toitsu_idx >= 4) return Yaku::Shousangen;
    return Yaku::None;
}

void detect_yakuhai(const bool z_koutsu[7], Wind self_wind, Wind game_wind,
                    Yaku yakus_out[7], int& yakus_out_count) {
    int n = 0;
    if (z_koutsu[4]) yakus_out[n++] = Yaku::Yakuhai_Haku;
    if (z_koutsu[5]) yakus_out[n++] = Yaku::Yakuhai_Hatsu;
    if (z_koutsu[6]) yakus_out[n++] = Yaku::Yakuhai_Chu;
    if (game_wind == Wind::East  && z_koutsu[0]) yakus_out[n++] = Yaku::Bakaze_Ton;
    if (game_wind == Wind::South && z_koutsu[1]) yakus_out[n++] = Yaku::Bakaze_Nan;
    if (game_wind == Wind::West  && z_koutsu[2]) yakus_out[n++] = Yaku::Bakaze_Sha;
    if (game_wind == Wind::North && z_koutsu[3]) yakus_out[n++] = Yaku::Bakaze_Pei;
    if (self_wind == Wind::East  && z_koutsu[0]) yakus_out[n++] = Yaku::Jikaze_Ton;
    if (self_wind == Wind::South && z_koutsu[1]) yakus_out[n++] = Yaku::Jikaze_Nan;
    if (self_wind == Wind::West  && z_koutsu[2]) yakus_out[n++] = Yaku::Jikaze_Sha;
    if (self_wind == Wind::North && z_koutsu[3]) yakus_out[n++] = Yaku::Jikaze_Pei;
    yakus_out_count = n;
}

Yaku detect_pinfu(const std::vector<std::string>& tgs, Wind self_wind, Wind game_wind) {
    // All groups must be shuntsu or non-yakuhai toitsu
    for (const auto& s : tgs) {
        if (s[2] == ':' && is_yakuhai_toitsu(s, self_wind, game_wind)) return Yaku::None;
        if (s[2] != ':' && s[2] != 'S') return Yaku::None;
    }
    // No single wait
    if (has_single_wait(tgs)) return Yaku::None;
    // No kanchan / penchan
    for (const auto& s : tgs) {
        if (s.size() == 4 && s[2] == 'S') {
            if (s[3] == '@' || s[3] == '%') return Yaku::None;  // kanchan
            if (s[0] == '1' && (s[3] == '!' || s[3] == '$')) return Yaku::None;
            if (s[0] == '7' && (s[3] == '!' || s[3] == '$')) return Yaku::None;
        }
    }
    if (tgs.size() != 5) return Yaku::None;
    return Yaku::Pinfu;
}

// ─── Yakuman detectors ────────────────────────────────────────────────────────

Yaku detect_tsuiisou(bool all_honor) {
    return all_honor ? Yaku::Tsuiisou : Yaku::None;
}

Yaku detect_daisangen(const bool z_koutsu[7]) {
    if (z_koutsu[4] && z_koutsu[5] && z_koutsu[6]) return Yaku::Daisangen;
    return Yaku::None;
}

Yaku detect_daisuushi(const bool z_koutsu[7]) {
    if (z_koutsu[0] && z_koutsu[1] && z_koutsu[2] && z_koutsu[3])
        return Yaku::Daisuushi;
    return Yaku::None;
}

Yaku detect_shousuushi(const bool z_koutsu[7], const bool z_toitsu[7]) {
    int wind_koutsu = 0;
    for (int i = 0; i < 4; ++i)
        if (z_koutsu[i]) wind_koutsu++;
    if (wind_koutsu != 3) return Yaku::None;
    for (int i = 0; i < 4; ++i)
        if (z_koutsu[i] && z_toitsu[i]) return Yaku::Shousuushi;
    return Yaku::None;
}

Yaku detect_suuankou(int closed_koutsu_count, bool single_wait) {
    if (closed_koutsu_count < 4) return Yaku::None;
    return single_wait ? Yaku::Siiankou_1 : Yaku::Siiankou;
}

Yaku detect_suukantsu(int kantsu_count) {
    if (kantsu_count >= 4) return Yaku::Siikantsu;
    return Yaku::None;
}

Yaku detect_chinroutou(bool all_terminals) {
    return all_terminals ? Yaku::Chinroutou : Yaku::None;
}

Yaku detect_ryuiisou(bool pure_green) {
    return pure_green ? Yaku::Ryuiisou : Yaku::None;
}

int detect_all_yakuman(const std::vector<std::string>& tgs,
                       Wind self_wind, Wind game_wind,
                       bool& yakuman_out,
                       Yaku yakus_out[8]) {
    yakuman_out = false;
    int n = 0;

    bool z_koutsu[7] = {false};
    bool z_toitsu[7] = {false};
    count_z_koutsu(tgs, z_koutsu);
    count_z_toitsu(tgs, z_toitsu);

    if (auto y = detect_tsuiisou(is_all_honor(tgs)); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_daisangen(z_koutsu); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_daisuushi(z_koutsu); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_shousuushi(z_koutsu, z_toitsu); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_suuankou(count_closed_koutsu(tgs), has_single_wait(tgs)); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_suukantsu(count_kantsu(tgs)); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_chinroutou(is_all_terminals(tgs)); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;
    if (auto y = detect_ryuiisou(is_pure_green(tgs)); y != Yaku::None)
        yakus_out[n++] = y, yakuman_out = true;

    return n;
}

// ─── Aggregated detector ───────────────────────────────────────────────────────

void detect_all_hand_yakus(const std::vector<std::string>& tgs,
                            Wind self_wind, Wind game_wind, bool menzen,
                            std::vector<Yaku>& yakus_out) {
    yakus_out.reserve(16);

    bool z_koutsu[7] = {false};
    bool z_toitsu[7] = {false};
    count_z_koutsu(tgs, z_koutsu);
    count_z_toitsu(tgs, z_toitsu);

    if (auto y = detect_chiitoitsu(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_toitoiho(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_tanyao(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_chinitsu(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    if (yakus_out.empty() || yakus_out.back() != Yaku::Chinitsu) {
        if (auto y = detect_honitsu(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    }
    if (auto y = detect_sanshoku_doujun(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_sanshoku_doukou(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_ittsuu(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_peikou(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_sanankou(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_sankantsu(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_honroutou(tgs); y != Yaku::None) yakus_out.push_back(y);
    if (auto y = detect_junchan(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    if (yakus_out.empty() ||
        (yakus_out.back() != Yaku::Junchantaiyaochu &&
         yakus_out.back() != Yaku::Junchantaiyaochu_Naki)) {
        if (auto y = detect_chanta(tgs, menzen); y != Yaku::None) yakus_out.push_back(y);
    }
    if (auto y = detect_shousangen(z_koutsu, z_toitsu); y != Yaku::None) yakus_out.push_back(y);

    // yakuhai (can be multiple)
    Yaku yh[7];
    int yh_count = 0;
    detect_yakuhai(z_koutsu, self_wind, game_wind, yh, yh_count);
    for (int i = 0; i < yh_count; ++i) yakus_out.push_back(yh[i]);

    if (auto y = detect_pinfu(tgs, self_wind, game_wind); y != Yaku::None) yakus_out.push_back(y);
}

}  // namespace yaku_detector
namespace_mahjong_end

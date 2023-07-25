#include "RoundToWin.h"
#include <fstream>
#include <tuple>
#include <array>

namespace_mahjong

// little endian
constexpr static std::array<uint32_t, 9> tile_to_bit = {
        0b000000000000000000000000001, // _1
        0b000000000000000000000001000, // _2
        0b000000000000000000001000000,
        0b000000000000000001000000000,
        0b000000000000001000000000000,
        0b000000000001000000000000000,
        0b000000001000000000000000000,
        0b000001000000000000000000000,
        0b001000000000000000000000000, // _9
};

std::string Syanten::code_to_string(uint32_t code) {
    std::string result;
    for (int i = 0; i < 9; i++) {
        result += std::to_string(0b111 & code);
        code >>= 3;
    }
    return result;
}

void Syanten::load_syanten_map() {
    auto& result = syanten_map;
    std::fstream f;
    f.open("../resource/syanten.dat", std::ios::in);
    if (!f.good()) {
        throw std::runtime_error("open syanten.dat error.\nPlease put \"syanten.dat\" to current path.");
    }
    std::string line;
    while (getline(f, line)) {
        std::string code_str;
        std::stringstream ss;
        ss << line;
        ss >> code_str;
        uint32_t key = 0;
        int value[4];
        for (int i = 0; i < 9; i++) {
            key += tile_to_bit[i] * (code_str[i] - '0');
        }
        ss >> value[0] >> value[1] >> value[2] >> value[3];
        result[key] = std::make_tuple(value[0], value[1], value[2], value[3]);
    }
    f.close();
    // for(auto iter=result.cbegin();iter!=result.cend();iter++){
    //     int value[4];
    //     std::tie(value[0], value[1], value[2], value[3]) = iter->second;
    //     std:: cout << code_to_string(iter->first) << ' ' << value[0] << ' ' << value[1]
    //     << ' ' << value[2] << ' ' << value[3] << std::endl;
    // }
    if (result.size() != 405350) {
        throw std::runtime_error("syanten.dat broken!");
    }
    // return result;
}

void Syanten::hand_to_code(const std::vector<Tile*>& hand, uint32_t* code){
    // 1m 2m 6m 9m 1s 3s 5s 7s 1p 1p 1p 1p 1z => [110001001, 101010100, 400000000, 100000000]
    memset(code, 0, 4*sizeof(uint32_t));
    for (auto iter = hand.cbegin(); iter != hand.cend(); iter++) {
        BaseTile t = (*iter)->tile;
        code[t / (_1p - _1m)] += tile_to_bit[t % (_1p - _1m)];
    }
}

int Syanten::_check_normal(const uint32_t* hand_code, int n_call_groups) {
    int ptm = 0, ptt = 0;
    for (int j = 0; j < 3; j++) {
        int pt1m, pt1t, pt2m, pt2t;
        std::tie(pt1m, pt1t, pt2m, pt2t) = syanten_map[hand_code[j]];
        if (pt1m * 2 + pt1t >= pt2m * 2 + pt2t) {
            ptm += pt1m;
            ptt += pt1t;
        }
        else {
            ptm += pt2m;
            ptt += pt2t;
        }
    }

    for (int i = 0; i < 7; i++) {
        int num = 0b111 & (hand_code[3] >> (3 * i));
        if (num >= 3) {
            ptm++; // 面子
        }
        else if (num >= 2) {
            ptt++; // 雀头
        }
    }
    while (ptm + ptt > 4 - n_call_groups && ptt > 0) ptt--;
    while (ptm + ptt > 4 - n_call_groups) ptm--;
    return 9 - ptm * 2 - ptt - n_call_groups * 2;
}

int Syanten::normal_round_to_win(const std::vector<Tile*>& hand, int n_call_groups) {
    if (!is_loaded)
        load_syanten_map();
    int result = 14;
    uint32_t hand_code[4];
    hand_to_code(hand, hand_code);
    for (int i = _1m; i <= _7z; i++) {
        int num = 0b111 & (hand_code[i / (_1p - _1m)] >> (3 * (i % (_1p - _1m))));
        if (num >= 2) {
            hand_code[i / (_1p - _1m)] -= 2 * tile_to_bit[i % (_1p - _1m)];
            result = std::min(result, _check_normal(hand_code, n_call_groups) - 1);
            hand_code[i / (_1p - _1m)] += 2 * tile_to_bit[i % (_1p - _1m)];
        }
    }
    result = std::min(result, _check_normal(hand_code, n_call_groups));
    return result;
}

namespace_mahjong_end
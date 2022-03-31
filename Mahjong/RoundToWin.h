#ifndef ROUNDTOWIN_H
#define ROUNDTOWIN_H

#include "Tile.h"
#include <map>

namespace_mahjong

class Syanten {
    std::map<uint32_t, std::tuple<int, int, int, int>> syanten_map;
    void hand_to_code(const std::vector<Tile*>& hand, /*OUT*/ uint32_t* code);
    std::string code_to_string(uint32_t code);
    int _check_normal(const uint32_t* hand_code, int num_副露);
    void load_syanten_map();
    bool is_loaded = false;
    Syanten() = default;
public:
    static Syanten& instance() {
        static Syanten inst;
        return inst;
    }
    int normal_round_to_win(const std::vector<Tile*>& hand, int num_副露);
};

namespace_mahjong_end
#endif // end #ifndef ROUNDTOWIN_H
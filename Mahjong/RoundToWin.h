#ifndef ROUNDTOWIN_H
#define ROUNDTOWIN_H

#include "Tile.h"
#include <array>

namespace_mahjong

class Syanten {
    std::array<int, 34> hand_to_counts(const std::vector<Tile*>& hand);
    int normal_shanten(const std::array<int, 34>& tile_counts, int num_副露);
    Syanten() = default;
public:
    static Syanten& instance() {
        static Syanten inst;
        return inst;
    }
    int normal_round_to_win(const std::array<int, 34>& tile_counts, int num_副露);
    int normal_round_to_win(const std::vector<Tile*>& hand, int num_副露);
};

namespace_mahjong_end
#endif // end #ifndef ROUNDTOWIN_H

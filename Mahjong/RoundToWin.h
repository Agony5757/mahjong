#ifndef ROUNDTOWIN_H
#define ROUNDTOWIN_H
#include "Player.h"
#include <map>
namespace_mahjong

// #define SYANTEN
namespace syanten {
    extern std::map<uint32_t, std::tuple<int, int, int, int>> syanten_map;
    void hand_to_code(const std::vector<Tile*>& hand, /*OUT*/ uint32_t* code);
    std::string code_to_string(uint32_t code);
    int _checkNormal(const uint32_t* hand_code, int num_副露);
    int normalRoundToWin(const std::vector<Tile*>& hand, int num_副露);
    std::map<uint32_t, std::tuple<int, int, int, int>> load_syanten_map();
} // end namespace syanten
namespace_mahjong_end
#endif // end #ifndef ROUNDTOWIN_H
#include "RoundToWin.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <unordered_map>

namespace_mahjong

namespace {

struct SearchKey {
    std::array<uint8_t, 34> counts{};
    uint8_t melds = 0;
    uint8_t taatsu = 0;
    uint8_t has_pair = 0;

    bool operator==(const SearchKey& other) const {
        return counts == other.counts &&
            melds == other.melds &&
            taatsu == other.taatsu &&
            has_pair == other.has_pair;
    }
};

struct SearchKeyHash {
    size_t operator()(const SearchKey& key) const {
        size_t hash = key.melds;
        hash = hash * 131 + key.taatsu;
        hash = hash * 131 + key.has_pair;
        for (uint8_t count : key.counts) {
            hash = hash * 5 + count;
        }
        return hash;
    }
};

inline bool is_number_tile(int tile) {
    return tile < _1z;
}

inline bool can_make_sequence(int tile) {
    return is_number_tile(tile) && tile % 9 <= 6;
}

inline bool can_make_adjacent_taatsu(int tile) {
    return is_number_tile(tile) && tile % 9 <= 7;
}

class ExactNormalShantenSolver {
public:
    explicit ExactNormalShantenSolver(int n_call_groups)
        : n_call_groups_(n_call_groups),
        max_closed_groups_(4 - n_call_groups) {
        if (n_call_groups_ < 0 || n_call_groups_ > 4) {
            throw std::invalid_argument("The number of open melds must be between 0 and 4.");
        }
    }

    int solve(const std::array<int, 34>& tile_counts) {
        std::array<uint8_t, 34> counts{};
        for (size_t i = 0; i < tile_counts.size(); ++i) {
            if (tile_counts[i] < 0 || tile_counts[i] > 4) {
                throw std::invalid_argument("Each tile count must be between 0 and 4.");
            }
            counts[i] = static_cast<uint8_t>(tile_counts[i]);
        }
        return dfs(counts, 0, 0, false);
    }

private:
    int n_call_groups_;
    int max_closed_groups_;
    std::unordered_map<SearchKey, int, SearchKeyHash> memo_;

    int evaluate(int melds, int taatsu, bool has_pair) const {
        // Extra taatsu above the remaining meld capacity do not reduce shanten.
        int capped_taatsu = std::min(taatsu, std::max(0, max_closed_groups_ - melds));
        return 8 - 2 * (n_call_groups_ + melds) - capped_taatsu - (has_pair ? 1 : 0);
    }

    int dfs(std::array<uint8_t, 34>& counts, int melds, int taatsu, bool has_pair) {
        SearchKey key{ counts, static_cast<uint8_t>(melds), static_cast<uint8_t>(taatsu), static_cast<uint8_t>(has_pair) };
        auto memo_it = memo_.find(key);
        if (memo_it != memo_.end()) {
            return memo_it->second;
        }

        int tile = 0;
        while (tile < 34 && counts[tile] == 0) {
            ++tile;
        }
        if (tile == 34) {
            int shanten = evaluate(melds, taatsu, has_pair);
            memo_[key] = shanten;
            return shanten;
        }

        int best = evaluate(melds, taatsu, has_pair);

        // Try consuming the first remaining tile into every productive block type.
        if (melds < max_closed_groups_) {
            if (counts[tile] >= 3) {
                counts[tile] -= 3;
                best = std::min(best, dfs(counts, melds + 1, taatsu, has_pair));
                counts[tile] += 3;
            }

            if (can_make_sequence(tile) && counts[tile + 1] > 0 && counts[tile + 2] > 0) {
                --counts[tile];
                --counts[tile + 1];
                --counts[tile + 2];
                best = std::min(best, dfs(counts, melds + 1, taatsu, has_pair));
                ++counts[tile];
                ++counts[tile + 1];
                ++counts[tile + 2];
            }
        }

        if (counts[tile] >= 2) {
            counts[tile] -= 2;
            if (!has_pair) {
                best = std::min(best, dfs(counts, melds, taatsu, true));
            }
            if (taatsu < max_closed_groups_) {
                best = std::min(best, dfs(counts, melds, taatsu + 1, has_pair));
            }
            counts[tile] += 2;
        }

        if (taatsu < max_closed_groups_) {
            if (can_make_adjacent_taatsu(tile) && counts[tile + 1] > 0) {
                --counts[tile];
                --counts[tile + 1];
                best = std::min(best, dfs(counts, melds, taatsu + 1, has_pair));
                ++counts[tile];
                ++counts[tile + 1];
            }

            if (can_make_sequence(tile) && counts[tile + 2] > 0) {
                --counts[tile];
                --counts[tile + 2];
                best = std::min(best, dfs(counts, melds, taatsu + 1, has_pair));
                ++counts[tile];
                ++counts[tile + 2];
            }
        }

        --counts[tile];
        best = std::min(best, dfs(counts, melds, taatsu, has_pair));
        ++counts[tile];

        memo_[key] = best;
        return best;
    }
};

}  // namespace

std::array<int, 34> Syanten::hand_to_counts(const std::vector<Tile*>& hand) {
    std::array<int, 34> counts{};
    for (const Tile* tile : hand) {
        ++counts[tile->tile];
    }
    return counts;
}

int Syanten::normal_shanten(const std::array<int, 34>& tile_counts, int n_call_groups) {
    ExactNormalShantenSolver solver(n_call_groups);
    return solver.solve(tile_counts);
}

int Syanten::normal_round_to_win(const std::array<int, 34>& tile_counts, int n_call_groups) {
    // Historical API contract:
    // 0 => agari, 1 => tenpai, 2 => 1-shanten, ...
    return normal_shanten(tile_counts, n_call_groups) + 1;
}

int Syanten::normal_round_to_win(const std::vector<Tile*>& hand, int n_call_groups) {
    return normal_round_to_win(hand_to_counts(hand), n_call_groups);
}

namespace_mahjong_end

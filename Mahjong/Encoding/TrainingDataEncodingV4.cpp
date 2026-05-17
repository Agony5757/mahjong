#include "TrainingDataEncodingV4.h"
#include "fmt/core.h"
#include <algorithm>

namespace_mahjong

namespace TrainingDataEncoding {
namespace v4 {

// ---------------------------------------------------------------
// HandTrackEncoder
// ---------------------------------------------------------------

HandTrackEncoder::HandTrackEncoder(Table* t, int viewer)
    : table_(t), viewer_(viewer) {}

void HandTrackEncoder::clear() {
    events_.clear();
    decide_points_.clear();
}

int HandTrackEncoder::to_relative(int absolute_player) const {
    int rel = absolute_player - viewer_;
    if (rel < 0) rel += 4;
    return rel;
}

void HandTrackEncoder::encode_context_and_score() {
    // GAME_CONTEXT: game_wind, self_wind, oya_relative
    {
        EventFeatures f;
        f.set_event_type(EventType::GAME_CONTEXT);
        f.set_game_wind(static_cast<int>(table_->game_wind));
        f.set_self_wind(static_cast<int>(table_->players[viewer_].wind));
        f.set_oya_rel(to_relative(table_->oya));
        events_.push_back(f);
    }

    // PLAYER_SCORE × 4
    auto scores = table_->get_scores();
    for (int p = 0; p < 4; ++p) {
        EventFeatures f;
        f.set_event_type(EventType::PLAYER_SCORE);
        f.set_who(to_relative(p));
        f.set_score((scores[p] - 25000) / 100);
        f.set_honba(table_->honba);
        events_.push_back(f);
    }
}

void HandTrackEncoder::encode_dora_indicator() {
    // DORA_INDICATOR — only currently revealed dora
    for (int i = 0; i < table_->n_active_dora && i < (int)table_->dora_indicator.size(); ++i) {
        auto* dora = table_->dora_indicator[i];
        EventFeatures f;
        f.set_event_type(EventType::DORA_INDICATOR);
        f.set_tile(static_cast<int>(dora->tile));
        if (dora->red_dora) f.set_aka();
        events_.push_back(f);
    }
}

void HandTrackEncoder::fire_init_hand(int n) {
    // Fire INIT_HAND events directly from the hand tiles.
    // n = number of tiles to fire (default 13, capped at hand.size())
    // Does NOT modify init_phase_ or n_init_hand_.
    auto& hand = table_->players[viewer_].hand;
    int n_fire = n;
    if (n_fire < 0 || n_fire > static_cast<int>(hand.size()))
        n_fire = static_cast<int>(hand.size());
    if (n_fire > 13) n_fire = 13;
    for (int i = 0; i < n_fire; ++i) {
        auto* tile = hand[i];
        EventFeatures f;
        f.set_event_type(EventType::INIT_HAND);
        f.set_tile(static_cast<int>(tile->tile));
        if (tile->red_dora) f.set_aka();
        events_.push_back(f);
    }
}

void HandTrackEncoder::encode_game_context_and_dora() {
    // Convenience: GAME_CONTEXT + PLAYER_SCORE + INIT_HAND (up to 13 from hand)
    // + DORA_INDICATOR.  Marks init_phase_ = true so subsequent draw callbacks
    // encode INIT_HAND instead of DRAW.
    encode_context_and_score();
    fire_init_hand(n_init_hand_ >= 0 ? n_init_hand_ : 13);
    encode_dora_indicator();
    init_phase_ = true;
    n_init_hand_ = -1;
}

void HandTrackEncoder::encode_init() {
    // Full init: game context + dora + INIT_HAND.  Also marks init phase.
    encode_game_context_and_dora();
    // encode_game_context_and_dora() already sets init_phase_ = true.
}

void HandTrackEncoder::on_draw(BaseTile tile, bool aka) {
    if (init_phase_) {
        // During Table::game_init / game_init_for_replay: encode INIT_HAND.
        // Each draw from draw_normal() adds one tile to the hand.
        // After this fires, init_phase_ stays true until set_init_phase(false)
        // is called by encode_init() below.
        EventFeatures f;
        f.set_event_type(EventType::INIT_HAND);
        f.set_tile(static_cast<int>(tile));
        if (aka) f.set_aka();
        events_.push_back(f);
    } else {
        // Normal game-loop draw: encode DRAW.
        EventFeatures f;
        f.set_event_type(EventType::DRAW);
        f.set_tile(static_cast<int>(tile));
        if (aka) f.set_aka();
        events_.push_back(f);
    }
}

void HandTrackEncoder::on_discard(int absolute_player, BaseTile tile, bool aka, int flags) {
    EventFeatures f;
    f.set_event_type(EventType::DISCARD);
    f.set_tile(static_cast<int>(tile));
    if (aka) f.set_aka();
    f.set_who(to_relative(absolute_player));
    if (flags & 0x01) f.set_riichi_flag();
    if (flags & 0x02) f.set_from_hand();
    events_.push_back(f);
}

void HandTrackEncoder::on_chi(int absolute_player, BaseTile lowest, int chi_type,
                               int absolute_from_who, int aka_bits) {
    EventFeatures f;
    f.set_event_type(EventType::CHI);
    f.set_tile(static_cast<int>(lowest));
    if (aka_bits & 0x01) f.set_aka();
    f.set_who(to_relative(absolute_player));
    f.set_chi_type(chi_type);
    events_.push_back(f);
}

void HandTrackEncoder::on_pon(int absolute_player, BaseTile tile,
                               int absolute_from_who, bool aka) {
    EventFeatures f;
    f.set_event_type(EventType::PON);
    f.set_tile(static_cast<int>(tile));
    if (aka) f.set_aka();
    f.set_who(to_relative(absolute_player));
    events_.push_back(f);
}

void HandTrackEncoder::on_daiminkan(int absolute_player, BaseTile tile,
                                     int absolute_from_who, bool aka) {
    EventFeatures f;
    f.set_event_type(EventType::DAIMINKAN);
    f.set_tile(static_cast<int>(tile));
    if (aka) f.set_aka();
    f.set_who(to_relative(absolute_player));
    events_.push_back(f);
}

void HandTrackEncoder::on_ankan(int absolute_player, BaseTile tile) {
    EventFeatures f;
    f.set_event_type(EventType::ANKAN);
    f.set_tile(static_cast<int>(tile));
    f.set_who(to_relative(absolute_player));
    events_.push_back(f);
}

void HandTrackEncoder::on_kakan(int absolute_player, BaseTile tile, bool aka) {
    EventFeatures f;
    f.set_event_type(EventType::KAKAN);
    f.set_tile(static_cast<int>(tile));
    if (aka) f.set_aka();
    f.set_who(to_relative(absolute_player));
    events_.push_back(f);
}

void HandTrackEncoder::on_riichi(int absolute_player, BaseTile tile, bool aka, bool from_hand) {
    EventFeatures f;
    f.set_event_type(EventType::RIICHI_DECLARE);
    f.set_tile(static_cast<int>(tile));
    if (aka) f.set_aka();
    f.set_who(to_relative(absolute_player));
    f.set_riichi_flag();  // Always a riichi discard
    if (from_hand) f.set_from_hand();
    events_.push_back(f);
}

void HandTrackEncoder::on_riichi_success(int absolute_player) {
    EventFeatures f;
    f.set_event_type(EventType::RIICHI_SUCCESS);
    f.set_who(to_relative(absolute_player));
    events_.push_back(f);
}

void HandTrackEncoder::on_dora_reveal(BaseTile tile, bool aka) {
    EventFeatures f;
    f.set_event_type(EventType::DORA_REVEAL);
    f.set_tile(static_cast<int>(tile));
    if (aka) f.set_aka();
    events_.push_back(f);
}

void HandTrackEncoder::on_ron(int absolute_winner, int absolute_from_who) {
    EventFeatures f;
    f.set_event_type(EventType::RON);
    f.set_who(to_relative(absolute_winner));
    events_.push_back(f);
}

void HandTrackEncoder::on_tsumo(int absolute_winner) {
    EventFeatures f;
    f.set_event_type(EventType::TSUMO);
    f.set_who(to_relative(absolute_winner));
    events_.push_back(f);
}

void HandTrackEncoder::on_ryuukyoku() {
    EventFeatures f;
    f.set_event_type(EventType::RYUUKYOKU);
    events_.push_back(f);
}

void HandTrackEncoder::on_decide(
    const std::array<uint8_t, N_ACTION_DIM>& action_mask,
    int action_label)
{
    // Filter: skip if fewer than 2 valid actions
    int n_valid = 0;
    for (size_t i = 0; i < N_ACTION_DIM; ++i)
        if (action_mask[i]) ++n_valid;
    if (n_valid < 2) return;

    DecidePoint dp;
    dp.track_pos = static_cast<int>(events_.size());
    dp.action_mask = action_mask;
    dp.action_label = action_label;
    decide_points_.push_back(dp);
}

// ---------------------------------------------------------------
// HandEncoder — routes events to all 4 tracks
// ---------------------------------------------------------------

HandEncoder::HandEncoder(Table* t)
    : table_(t)
    , tracks_{{HandTrackEncoder(t, 0), HandTrackEncoder(t, 1),
               HandTrackEncoder(t, 2), HandTrackEncoder(t, 3)}}
{}

void HandEncoder::clear() {
    for (auto& tr : tracks_) tr.clear();
}

void HandEncoder::encode_init() {
    for (auto& tr : tracks_) tr.encode_init();
}

// Private: only the drawing player's track
void HandEncoder::on_draw(int player, BaseTile tile, bool aka) {
    tracks_[player].on_draw(tile, aka);
}

// Public: all 4 tracks
void HandEncoder::on_discard(int player, BaseTile tile, bool aka, int flags) {
    for (auto& tr : tracks_) tr.on_discard(player, tile, aka, flags);
}

void HandEncoder::on_chi(int player, BaseTile lowest, int chi_type,
                          int from_who, int aka_bits) {
    for (auto& tr : tracks_) tr.on_chi(player, lowest, chi_type, from_who, aka_bits);
}

void HandEncoder::on_pon(int player, BaseTile tile, int from_who, bool aka) {
    for (auto& tr : tracks_) tr.on_pon(player, tile, from_who, aka);
}

void HandEncoder::on_daiminkan(int player, BaseTile tile, int from_who, bool aka) {
    for (auto& tr : tracks_) tr.on_daiminkan(player, tile, from_who, aka);
}

void HandEncoder::on_ankan(int player, BaseTile tile) {
    for (auto& tr : tracks_) tr.on_ankan(player, tile);
}

void HandEncoder::on_kakan(int player, BaseTile tile, bool aka) {
    for (auto& tr : tracks_) tr.on_kakan(player, tile, aka);
}

void HandEncoder::on_riichi(int player, BaseTile tile, bool aka, bool from_hand) {
    for (auto& tr : tracks_) tr.on_riichi(player, tile, aka, from_hand);
}

void HandEncoder::on_riichi_success(int player) {
    for (auto& tr : tracks_) tr.on_riichi_success(player);
}

void HandEncoder::on_dora_reveal(BaseTile tile, bool aka) {
    for (auto& tr : tracks_) tr.on_dora_reveal(tile, aka);
}

void HandEncoder::on_ron(int winner, int from_who) {
    for (auto& tr : tracks_) tr.on_ron(winner, from_who);
}

void HandEncoder::on_tsumo(int winner) {
    for (auto& tr : tracks_) tr.on_tsumo(winner);
}

void HandEncoder::on_ryuukyoku() {
    for (auto& tr : tracks_) tr.on_ryuukyoku();
}

// Decision: only the deciding player's track
void HandEncoder::on_decide(int player,
                             const std::array<uint8_t, N_ACTION_DIM>& mask,
                             int label) {
    tracks_[player].on_decide(mask, label);
}

}  // namespace v4
}  // namespace TrainingDataEncoding

namespace_mahjong_end

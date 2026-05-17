#ifndef TRAINING_DATA_ENCODING_V4_H
#define TRAINING_DATA_ENCODING_V4_H

#include <bitset>
#include <vector>
#include <array>
#include "Table.h"

namespace_mahjong

namespace TrainingDataEncoding {
	namespace v4
	{
		// ---------------------------------------------------------------
		// Feature vector layout — wide one-hot BOOL-packed per event
		// ---------------------------------------------------------------
		// Total ~100 BOOL dims per event, stored packed (~13 bytes).
		// Training converts to float32.

		constexpr size_t FEAT_EVENT_TYPE   = 19;   // one-hot over EventType
		constexpr size_t FEAT_TILE         = 34;   // one-hot over BaseTile (0-33)
		constexpr size_t FEAT_AKA          = 1;    // is this aka (red five)?
		constexpr size_t FEAT_WHO          = 4;    // one-hot: self=0, next=1, across=2, prev=3
		constexpr size_t FEAT_SCORE        = 16;   // (score-25000)/100 as uint16 bits
		constexpr size_t FEAT_GAME_WIND    = 4;    // one-hot E/S/W/N
		constexpr size_t FEAT_SELF_WIND    = 4;    // one-hot E/S/W/N
		constexpr size_t FEAT_OYA_REL      = 4;    // one-hot relative oya position
		constexpr size_t FEAT_RIICHI_ST    = 4;    // BOOL×4 riichi status per player
		constexpr size_t FEAT_CHI_TYPE     = 3;    // one-hot chi take position
		constexpr size_t FEAT_RIICHI_FLAG  = 1;    // discard was riichi-declaration
		constexpr size_t FEAT_FROM_HAND    = 1;    // hand-discard vs tsumo-discard
		constexpr size_t FEAT_HONBA        = 4;    // binary 0-15
		constexpr size_t FEAT_SIGN         = 1;    // gain(0) / loss(1)

		// Offset accumulators (computed at compile time)
		constexpr size_t OFF_EVENT_TYPE  = 0;
		constexpr size_t OFF_TILE        = OFF_EVENT_TYPE + FEAT_EVENT_TYPE;
		constexpr size_t OFF_AKA         = OFF_TILE     + FEAT_TILE;
		constexpr size_t OFF_WHO         = OFF_AKA      + FEAT_AKA;
		constexpr size_t OFF_SCORE       = OFF_WHO      + FEAT_WHO;
		constexpr size_t OFF_GAME_WIND   = OFF_SCORE    + FEAT_SCORE;
		constexpr size_t OFF_SELF_WIND   = OFF_GAME_WIND+ FEAT_GAME_WIND;
		constexpr size_t OFF_OYA_REL     = OFF_SELF_WIND+ FEAT_SELF_WIND;
		constexpr size_t OFF_RIICHI_ST   = OFF_OYA_REL  + FEAT_OYA_REL;
		constexpr size_t OFF_CHI_TYPE    = OFF_RIICHI_ST+ FEAT_RIICHI_ST;
		constexpr size_t OFF_RIICHI_FLAG = OFF_CHI_TYPE + FEAT_CHI_TYPE;
		constexpr size_t OFF_FROM_HAND   = OFF_RIICHI_FLAG + FEAT_RIICHI_FLAG;
		constexpr size_t OFF_HONBA       = OFF_FROM_HAND + FEAT_FROM_HAND;
		constexpr size_t OFF_SIGN        = OFF_HONBA    + FEAT_HONBA;

		constexpr size_t EVENT_DIM = OFF_SIGN + FEAT_SIGN;  // ~100
		constexpr size_t N_ACTION_DIM = 54;
		constexpr size_t MAX_SEQ_LEN = 512;

		enum class EventType : uint8_t {
			PAD = 0,
			GAME_CONTEXT   = 1,
			PLAYER_SCORE   = 2,
			INIT_HAND      = 3,
			DORA_INDICATOR = 4,
			DRAW           = 5,
			DISCARD        = 6,
			CHI            = 7,
			PON            = 8,
			DAIMINKAN      = 9,
			ANKAN          = 10,
			KAKAN          = 11,
			RIICHI_DECLARE = 12,
			RIICHI_SUCCESS = 13,
			RON            = 14,
			TSUMO          = 15,
			RYUUKYOKU      = 16,
			SCORE_CHANGE   = 17,
			DORA_REVEAL    = 18,
		};

		struct EventFeatures {
			std::bitset<EVENT_DIM> bits;

			void set_event_type(EventType t) {
				bits.set(OFF_EVENT_TYPE + static_cast<size_t>(t));
			}

			void set_tile(int tile_id) {
				bits.set(OFF_TILE + tile_id);
			}

			void set_aka() {
				bits.set(OFF_AKA);
			}

			void set_who(int relative_who) {
				bits.set(OFF_WHO + relative_who);
			}

			void set_score(int score_units) {
				uint16_t val = static_cast<uint16_t>(score_units);
				for (size_t i = 0; i < FEAT_SCORE; ++i)
					if (val & (1u << i))
						bits.set(OFF_SCORE + i);
			}

			void set_game_wind(int wind) {
				bits.set(OFF_GAME_WIND + wind);
			}

			void set_self_wind(int wind) {
				bits.set(OFF_SELF_WIND + wind);
			}

			void set_oya_rel(int rel) {
				bits.set(OFF_OYA_REL + rel);
			}

			void set_riichi_status(int player_rel, bool status) {
				if (status) bits.set(OFF_RIICHI_ST + player_rel);
			}

			void set_chi_type(int chi_type) {
				bits.set(OFF_CHI_TYPE + chi_type);
			}

			void set_riichi_flag() {
				bits.set(OFF_RIICHI_FLAG);
			}

			void set_from_hand() {
				bits.set(OFF_FROM_HAND);
			}

			void set_honba(int honba) {
				for (size_t i = 0; i < FEAT_HONBA; ++i)
					if (honba & (1 << (int)i))
						bits.set(OFF_HONBA + i);
			}

			void set_sign(bool loss) {
				if (loss) bits.set(OFF_SIGN);
			}
		};

		struct DecidePoint {
			int track_pos;
			std::array<uint8_t, N_ACTION_DIM> action_mask;
			int action_label;
		};

		// ---------------------------------------------------------------
		// Single-track encoder (one player's POV)
		// ---------------------------------------------------------------
		class HandTrackEncoder {
		public:
			explicit HandTrackEncoder(Table* t, int viewer);

			// Encode GAME_CONTEXT + PLAYER_SCORE (no INIT_HAND, no DORA_INDICATOR).
			// Does NOT modify init_phase_ or n_init_hand_.
			void encode_context_and_score();
			// Encode DORA_INDICATOR from current table state.
			void encode_dora_indicator();
			// Fire INIT_HAND events directly from hand tiles (up to n, default 13).
			// Does NOT modify init_phase_ or n_init_hand_.
			void fire_init_hand(int n = 13);
			// Convenience: GAME_CONTEXT + PLAYER_SCORE + INIT_HAND (up to n) + DORA_INDICATOR.
			// Also sets init_phase_ = true.
			void encode_game_context_and_dora();
			void encode_init();

			// Called by draw callback during Table::game_init / game_init_for_replay.
			// While init_phase_ is true, encodes INIT_HAND (one per draw).
			// After set_init_phase(false), encodes DRAW.
			void on_draw(BaseTile tile, bool aka);
			void set_init_phase(bool v) { init_phase_ = v; }
			void set_n_init_hand(int n) { n_init_hand_ = n; }

			// Public events — added to ALL tracks by HandEncoder
			void on_discard(int absolute_player, BaseTile tile, bool aka, int flags);
			void on_chi(int absolute_player, BaseTile lowest, int chi_type,
			            int absolute_from_who, int aka_bits);
			void on_pon(int absolute_player, BaseTile tile, int absolute_from_who, bool aka);
			void on_daiminkan(int absolute_player, BaseTile tile, int absolute_from_who, bool aka);
			void on_ankan(int absolute_player, BaseTile tile);
			void on_kakan(int absolute_player, BaseTile tile, bool aka);
			void on_riichi(int absolute_player, BaseTile tile, bool aka, bool from_hand);
			void on_riichi_success(int absolute_player);
			void on_dora_reveal(BaseTile tile, bool aka);
			void on_ron(int absolute_winner, int absolute_from_who);
			void on_tsumo(int absolute_winner);
			void on_ryuukyoku();

			// Decision point — records position, does NOT insert into events
			// Skipped if action_mask has < 2 valid actions.
			void on_decide(const std::array<uint8_t, N_ACTION_DIM>& action_mask,
			               int action_label);

			const std::vector<EventFeatures>& events() const { return events_; }
			const std::vector<DecidePoint>& decide_points() const { return decide_points_; }
			int viewer() const { return viewer_; }
			void clear();

		private:
			// Convert absolute player index to relative (self=0, next=1, ...)
			int to_relative(int absolute_player) const;

			Table* table_;
			int viewer_;
			std::vector<EventFeatures> events_;
			std::vector<DecidePoint> decide_points_;
			bool init_phase_ = false;  // true until encode_init() / set_init_phase(false)
			int n_init_hand_ = -1;  // -1 = auto (hand.size(), capped at 13)
		};

		// ---------------------------------------------------------------
		// Hand encoder — manages 4 parallel tracks
		// ---------------------------------------------------------------
		class HandEncoder {
		public:
			explicit HandEncoder(Table* t);

			void encode_init();

			void on_draw(int player, BaseTile tile, bool aka);
			void on_discard(int player, BaseTile tile, bool aka, int flags);
			void on_chi(int player, BaseTile lowest, int chi_type,
			            int from_who, int aka_bits);
			void on_pon(int player, BaseTile tile, int from_who, bool aka);
			void on_daiminkan(int player, BaseTile tile, int from_who, bool aka);
			void on_ankan(int player, BaseTile tile);
			void on_kakan(int player, BaseTile tile, bool aka);
			void on_riichi(int player, BaseTile tile, bool aka, bool from_hand);
			void on_riichi_success(int player);
			void on_dora_reveal(BaseTile tile, bool aka);
			void on_ron(int winner, int from_who);
			void on_tsumo(int winner);
			void on_ryuukyoku();

			void on_decide(int player,
			               const std::array<uint8_t, N_ACTION_DIM>& mask,
			               int label);

			const HandTrackEncoder& track(int player) const { return tracks_[player]; }
			void set_init_phase(bool v) {
			    for (auto& tr : tracks_) tr.set_init_phase(v);
			}
			// Set the number of INIT_HAND events to fire in encode_game_context_and_dora / fire_init_hand.
			// -1 (default) = auto (use hand.size(), capped at 13).
			// Set to 13 to fire exactly 13 INIT_HAND events regardless of hand size.
			void set_n_init_hand(int n) {
			    for (auto& tr : tracks_) tr.set_n_init_hand(n);
			}
			// Encode GAME_CONTEXT + PLAYER_SCORE (no INIT_HAND, no DORA_INDICATOR).
			void encode_context_and_score() {
			    for (auto& tr : tracks_) tr.encode_context_and_score();
			}
			// Encode DORA_INDICATOR from current table state.
			void encode_dora_indicator() {
			    for (auto& tr : tracks_) tr.encode_dora_indicator();
			}
			// Fire INIT_HAND events directly from hand tiles (up to n, default 13).
			void fire_init_hand(int n = 13) {
			    for (auto& tr : tracks_) tr.fire_init_hand(n);
			}
			// Fire GAME_CONTEXT + PLAYER_SCORE + INIT_HAND (up to n) + DORA_INDICATOR.
			// Also sets init_phase_ = true (subsequent draws encode INIT_HAND).
			void encode_game_context_and_dora() {
			    for (auto& tr : tracks_) tr.encode_game_context_and_dora();
			}
			void clear();

		private:
			Table* table_;
			std::array<HandTrackEncoder, 4> tracks_;
		};
	}
}

namespace_mahjong_end
#endif

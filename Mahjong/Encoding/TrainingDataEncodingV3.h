#ifndef TRAINING_DATA_ENCODING_V3_H
#define TRAINING_DATA_ENCODING_V3_H

#include <cstdint>
#include <cstring>
#include <array>
#include <vector>
#include "Table.h"

namespace_mahjong

namespace TrainingDataEncoding {
	namespace v3 {

		// ------------------------------------------------------------------
		// Constants (mirror pymahjong/rl/tokenization.py exactly)
		// ------------------------------------------------------------------

		constexpr int NUM_BASE_TILES = 34;
		constexpr int TILE_PAD = 34;
		constexpr int TILE_VOCAB_SIZE = 35;

		constexpr int MAX_SEQ_LEN = 360;
		constexpr int TOKEN_FEATURES = 5;   // (segment, tile, count, who, extra)
		constexpr int SCALAR_DIM = 4;
		constexpr int ACTION_DIM = 54;

		// ------------------------------------------------------------------
		// SegmentType (30 types, identical to Python)
		// ------------------------------------------------------------------

		enum class SegmentType : uint8_t {
			PAD = 0,
			SELF_HAND = 1,
			SELF_TSUMO = 2,
			SELF_FUURO = 3,
			OPP_FUURO = 4,
			SELF_RIVER = 5,
			OPP_RIVER = 6,
			DORA_INDICATOR = 7,
			URA_DORA_INDICATOR = 8,
			ACTUAL_DORA = 9,
			PLAYER_RIICHI = 10,
			PLAYER_IPPATSU = 11,
			PLAYER_MENZEN = 12,
			PLAYER_SCORE = 13,
			GAME_WIND = 14,
			SELF_WIND = 15,
			HONBA = 16,
			KYOUTAKU = 17,
			REMAINING_TILES = 18,
			SELF_TSUMO_TILE = 19,
			LAST_DISCARDED_TILE = 20,
			PHASE = 21,
			ACTION_HINT = 22,
			VISIBLE_COUNT = 23,
			FURITEN_AREA = 24,
			ROUND_INDEX = 25,
			DEALER_SEAT = 26,
			FUURO_FROM = 27,
			GAME_NUMBER = 28,
			TURN_INDEX = 29,
		};

		constexpr int NUM_SEGMENTS = 30;

		// ------------------------------------------------------------------
		// Action space (54 discrete actions, identical to Python)
		// ------------------------------------------------------------------

		constexpr int A_DISCARD_BASE = 0;       // 0..33
		constexpr int A_DISCARD_RED5M = 34;
		constexpr int A_DISCARD_RED5P = 35;
		constexpr int A_DISCARD_RED5S = 36;
		constexpr int A_CHILEFT = 37;
		constexpr int A_CHIMIDDLE = 38;
		constexpr int A_CHIRIGHT = 39;
		constexpr int A_CHILEFT_USERED = 40;
		constexpr int A_CHIMIDDLE_USERED = 41;
		constexpr int A_CHIRIGHT_USERED = 42;
		constexpr int A_PON = 43;
		constexpr int A_PON_USERED = 44;
		constexpr int A_ANKAN = 45;
		constexpr int A_MINKAN = 46;
		constexpr int A_KAKAN = 47;
		constexpr int A_RIICHI = 48;
		constexpr int A_RON = 49;
		constexpr int A_TSUMO = 50;
		constexpr int A_PUSH = 51;
		constexpr int A_PASS_RIICHI = 52;
		constexpr int A_PASS_RESPONSE = 53;

		// Meld type constants (must match CallGroup::Type in Tile.h)
		constexpr int MELD_CHI = 0;
		constexpr int MELD_PON = 1;
		constexpr int MELD_DAIMINKAN = 2;
		constexpr int MELD_KAKAN = 3;
		constexpr int MELD_ANKAN = 4;

		// ------------------------------------------------------------------
		// Result struct
		// ------------------------------------------------------------------

		struct TokenizedObservation {
			uint8_t  tokens[MAX_SEQ_LEN][TOKEN_FEATURES];
			float    scalars[MAX_SEQ_LEN][SCALAR_DIM];
			bool     attention_mask[MAX_SEQ_LEN];
			bool     action_mask[ACTION_DIM];
			int      seq_len;
			int      current_player;
			int      phase;
		};

		// ------------------------------------------------------------------
		// TableTokenizer — snapshot encoder for a single game state
		// ------------------------------------------------------------------

		class TableTokenizer {
		public:
			explicit TableTokenizer(Table* table, int max_seq_len = MAX_SEQ_LEN,
			                        bool include_oracle = false);

			TokenizedObservation encode(int current_player, bool riichi_stage2 = false);

		private:
			Table* table_;
			int max_seq_len_;
			bool include_oracle_;

			// Pre-allocated buffers (cleared on each encode() call)
			uint8_t  tokens_[MAX_SEQ_LEN][TOKEN_FEATURES];
			float    scalars_[MAX_SEQ_LEN][SCALAR_DIM];
			bool     mask_[MAX_SEQ_LEN];
			bool     action_mask_[ACTION_DIM];

			int push(int idx, int seg, int tile, int count, int who, int extra,
			         float s0 = 0.f, float s1 = 0.f, float s2 = 0.f, float s3 = 0.f);

			// Section encoders (return updated idx)
			int encode_hand(int idx, int cp, int phase, int acting,
			                /*out*/ Tile*& tsumo_tile);
			int encode_fuuros(int idx, int cp);
			int encode_rivers(int idx, int cp);
			int encode_dora(int idx);
			int encode_player_flags(int idx, int cp);
			int encode_global_context(int idx, int cp);
			int encode_context_tiles(int idx, int cp, int phase,
			                          bool in_response, Tile* tsumo_tile);
			int encode_visible_counts(int idx, int cp);
			int encode_furiten(int idx, int cp);
			int encode_oracle(int idx, int cp);

			void fill_action_mask(int cp, bool riichi_stage2, Tile* sel_tile);
			void mask_one_self(const SelfAction& sel, int chi_tile_id);
			void mask_one_response(const ResponseAction& sel, int chi_tile_id);

			// Helpers
			static int rel(int seat, int cp);
			static inline bool is_self_phase(int phase)   { return phase >= 0 && phase < 4; }
			static inline bool is_response_phase(int phase){ return phase >= 4 && phase < 8; }
			static inline bool is_chankan_phase(int phase) { return phase >= 8 && phase < 16; }
			static inline int  acting_player(int phase)    { return phase % 4; }
			static int fuuro_from_r(int meld_type, int take);
			static float norm_score(int score);
			static int bucket_score(int score);
			static int classify_chi(int chi_tile_id, const std::vector<Tile*>& hand_tiles);
		};

	}
}

namespace_mahjong_end
#endif

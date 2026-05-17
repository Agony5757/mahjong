#include "TrainingDataEncodingV3.h"
#include <algorithm>
#include <cstring>

namespace_mahjong

namespace TrainingDataEncoding {
namespace v3 {

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

int TableTokenizer::rel(int seat, int cp) {
	return (seat - cp + 4) % 4;
}

int TableTokenizer::fuuro_from_r(int meld_type, int take) {
	if (meld_type == MELD_CHI) return 3;
	if (meld_type == MELD_ANKAN) return 4;
	// Pon / DaiMinKan / KaKan: take ∈ {0,1,2} → r ∈ {3,2,1}
	if (take == 0) return 3;
	if (take == 1) return 2;
	if (take == 2) return 1;
	return 4;
}

float TableTokenizer::norm_score(int score) {
	return (static_cast<float>(score) - 25000.f) / 25000.f;
}

int TableTokenizer::bucket_score(int score) {
	int s = std::max(-10000, std::min(score, 70000));
	return (s + 10000) / 5000;
}

int TableTokenizer::classify_chi(int chi_tile_id, const std::vector<Tile*>& hand_tiles) {
	// hand_tiles are 2 Tile* from correspond_tiles (sorted by BaseTile)
	int h0 = static_cast<int>(hand_tiles[0]->tile);
	int h1 = static_cast<int>(hand_tiles[1]->tile);
	if (chi_tile_id < h0) return 0;  // left
	if (chi_tile_id > h1) return 2;  // right
	return 1;                        // middle
}

// ------------------------------------------------------------------
// TableTokenizer — construction
// ------------------------------------------------------------------

TableTokenizer::TableTokenizer(Table* table, int max_seq_len, bool include_oracle)
	: table_(table)
	, max_seq_len_(max_seq_len)
	, include_oracle_(include_oracle)
{
	std::memset(tokens_, 0, sizeof(tokens_));
	std::memset(scalars_, 0, sizeof(scalars_));
	std::memset(mask_, 0, sizeof(mask_));
	std::memset(action_mask_, 0, sizeof(action_mask_));
}

// ------------------------------------------------------------------
// push — low-level token writer
// ------------------------------------------------------------------

int TableTokenizer::push(int idx, int seg, int tile, int count, int who, int extra,
                         float s0, float s1, float s2, float s3) {
	if (idx >= max_seq_len_) return idx;
	auto* t = tokens_[idx];
	t[0] = static_cast<uint8_t>(seg);
	t[1] = static_cast<uint8_t>(tile);
	t[2] = static_cast<uint8_t>(count);
	t[3] = static_cast<uint8_t>(who);
	t[4] = static_cast<uint8_t>(extra);
	scalars_[idx][0] = s0;
	scalars_[idx][1] = s1;
	scalars_[idx][2] = s2;
	scalars_[idx][3] = s3;
	mask_[idx] = true;
	return idx + 1;
}

// ------------------------------------------------------------------
// encode — main entry point
// ------------------------------------------------------------------

TokenizedObservation TableTokenizer::encode(int current_player, bool riichi_stage2) {
	// Clear buffers
	std::memset(tokens_, 0, sizeof(tokens_));
	std::memset(scalars_, 0, sizeof(scalars_));
	std::memset(mask_, 0, sizeof(mask_));
	std::memset(action_mask_, 0, sizeof(action_mask_));
	int idx = 0;

	auto& me = table_->players[current_player];
	int phase = static_cast<int>(table_->get_phase());
	bool in_response = is_response_phase(phase) || is_chankan_phase(phase);

	// 1. SELF HAND (separate the just-drawn tsumo tile)
	Tile* tsumo_tile = nullptr;
	int acting = acting_player(phase);
	idx = encode_hand(idx, current_player, phase, acting, tsumo_tile);

	// 2. FUUROS
	idx = encode_fuuros(idx, current_player);

	// 3. RIVERS
	idx = encode_rivers(idx, current_player);

	// 4. DORA INDICATORS / ACTUAL DORA / URA
	idx = encode_dora(idx);

	// 5. PER-PLAYER FLAGS / SCORES
	idx = encode_player_flags(idx, current_player);

	// 6. GLOBAL CONTEXT
	idx = encode_global_context(idx, current_player);

	// 7. CONTEXT TILES (last discarded / self tsumo tile)
	idx = encode_context_tiles(idx, current_player, phase, in_response, tsumo_tile);

	// PHASE token
	idx = push(idx, static_cast<int>(SegmentType::PHASE), TILE_PAD,
	           phase, 4, riichi_stage2 ? 1 : 0);

	// ACTION_HINT
	int action_hint = is_self_phase(phase) ? 0
	                : is_response_phase(phase) ? 1
	                : is_chankan_phase(phase) ? 2 : 3;
	idx = push(idx, static_cast<int>(SegmentType::ACTION_HINT), TILE_PAD, action_hint, 4, 0);

	// 8. VISIBLE COUNTS
	idx = encode_visible_counts(idx, current_player);

	// 9. FURITEN AREA
	idx = encode_furiten(idx, current_player);

	// 10. ORACLE (optional)
	if (include_oracle_) {
		idx = encode_oracle(idx, current_player);
	}

	// 11. ACTION MASK
	fill_action_mask(current_player, riichi_stage2,
	                 table_->get_selected_action_tile());

	// Build result
	TokenizedObservation obs;
	std::memcpy(obs.tokens, tokens_, sizeof(tokens_));
	std::memcpy(obs.scalars, scalars_, sizeof(scalars_));
	std::memcpy(obs.attention_mask, mask_, sizeof(mask_));
	std::memcpy(obs.action_mask, action_mask_, sizeof(action_mask_));
	obs.seq_len = idx;
	obs.current_player = current_player;
	obs.phase = phase;
	return obs;
}

// ------------------------------------------------------------------
// Section 1: SELF HAND
// ------------------------------------------------------------------

int TableTokenizer::encode_hand(int idx, int cp, int phase, int acting,
                                Tile*& tsumo_tile) {
	auto& hand = table_->players[cp].hand;
	std::vector<Tile*> hand_tiles;
	hand_tiles.reserve(hand.size());
	for (auto* t : hand) hand_tiles.push_back(t);

	// Determine tsumo tile: last tile when hand size = 3k+2 and it's our self-action
	if (cp == acting && is_self_phase(phase) &&
	    static_cast<int>(hand_tiles.size()) % 3 == 2 && !hand_tiles.empty()) {
		tsumo_tile = hand_tiles.back();
		hand_tiles.pop_back();
	}

	// Count hand tiles by (base_tile, aka)
	int hand_counts[NUM_BASE_TILES][2] = {};
	for (auto* t : hand_tiles) {
		int b = static_cast<int>(t->tile);
		int a = t->red_dora ? 1 : 0;
		hand_counts[b][a]++;
	}
	for (int b = 0; b < NUM_BASE_TILES; ++b) {
		for (int a = 0; a <= 1; ++a) {
			int c = hand_counts[b][a];
			if (c > 0) {
				idx = push(idx, static_cast<int>(SegmentType::SELF_HAND), b, c, 0, a);
			}
		}
	}

	if (tsumo_tile != nullptr) {
		int b = static_cast<int>(tsumo_tile->tile);
		int a = tsumo_tile->red_dora ? 1 : 0;
		idx = push(idx, static_cast<int>(SegmentType::SELF_TSUMO), b, 1, 0, a);
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 2: FUUROS
// ------------------------------------------------------------------

int TableTokenizer::encode_fuuros(int idx, int cp) {
	for (int seat = 0; seat < 4; ++seat) {
		auto& p = table_->players[seat];
		int seg = (seat == cp)
			? static_cast<int>(SegmentType::SELF_FUURO)
			: static_cast<int>(SegmentType::OPP_FUURO);
		int owner_r = rel(seat, cp);
		for (auto& cg : p.call_groups) {
			int meld_type = static_cast<int>(cg.type);
			int from_r = fuuro_from_r(meld_type, static_cast<int>(cg.take));
			// FUURO_FROM summary token
			idx = push(idx, static_cast<int>(SegmentType::FUURO_FROM),
			           TILE_PAD, meld_type, owner_r, from_r);
			// One token per meld tile
			for (auto* tile_obj : cg.tiles) {
				int b = static_cast<int>(tile_obj->tile);
				int a = tile_obj->red_dora ? 1 : 0;
				idx = push(idx, seg, b, 1, owner_r,
				           a | (meld_type << 1));
			}
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 3: RIVERS
// ------------------------------------------------------------------

int TableTokenizer::encode_rivers(int idx, int cp) {
	for (int seat = 0; seat < 4; ++seat) {
		auto& p = table_->players[seat];
		int seg = (seat == cp)
			? static_cast<int>(SegmentType::SELF_RIVER)
			: static_cast<int>(SegmentType::OPP_RIVER);
		int r = rel(seat, cp);
		for (auto& rt : p.river.river) {
			int base = static_cast<int>(rt.tile->tile);
			int aka = rt.tile->red_dora ? 1 : 0;
			int num = std::min(rt.number, 95);
			int extra = aka
				| ((rt.riichi ? 1 : 0) << 1)
				| ((rt.fromhand ? 1 : 0) << 2);
			idx = push(idx, seg, base, num, r, extra);
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 4: DORA
// ------------------------------------------------------------------

int TableTokenizer::encode_dora(int idx) {
	int n_active = table_->n_active_dora;
	int n_ind = std::min(n_active, static_cast<int>(table_->dora_indicator.size()));

	// Dora indicators
	for (int i = 0; i < n_ind; ++i) {
		auto* di = table_->dora_indicator[i];
		int b = static_cast<int>(di->tile);
		int a = di->red_dora ? 1 : 0;
		idx = push(idx, static_cast<int>(SegmentType::DORA_INDICATOR), b, 1, 4, a);
	}

	// Actual dora
	auto dora_list = table_->get_dora();
	int n_dora = std::min(n_active, static_cast<int>(dora_list.size()));
	for (int i = 0; i < n_dora; ++i) {
		idx = push(idx, static_cast<int>(SegmentType::ACTUAL_DORA),
		           static_cast<int>(dora_list[i]), 1, 4, 0);
	}

	// Uradora (only at GAME_OVER)
	if (static_cast<int>(table_->get_phase()) ==
	    static_cast<int>(Table::PhaseEnum::GAME_OVER)) {
		int n_ura = std::min(n_active, static_cast<int>(table_->uradora_indicator.size()));
		for (int i = 0; i < n_ura; ++i) {
			auto* di = table_->uradora_indicator[i];
			int b = static_cast<int>(di->tile);
			int a = di->red_dora ? 1 : 0;
			idx = push(idx, static_cast<int>(SegmentType::URA_DORA_INDICATOR), b, 1, 4, a);
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 5: PER-PLAYER FLAGS / SCORES
// ------------------------------------------------------------------

int TableTokenizer::encode_player_flags(int idx, int cp) {
	auto scores = table_->get_scores();
	int max_other = 0;
	for (int s = 0; s < 4; ++s) {
		if (s != cp && scores[s] > max_other) max_other = scores[s];
	}

	for (int seat = 0; seat < 4; ++seat) {
		auto& p = table_->players[seat];
		int r = rel(seat, cp);

		idx = push(idx, static_cast<int>(SegmentType::PLAYER_RIICHI), TILE_PAD,
		           p.riichi ? 1 : 0, r,
		           p.double_riichi ? 1 : 0);

		idx = push(idx, static_cast<int>(SegmentType::PLAYER_IPPATSU), TILE_PAD,
		           p.ippatsu ? 1 : 0, r, 0);

		idx = push(idx, static_cast<int>(SegmentType::PLAYER_MENZEN), TILE_PAD,
		           p.menzen ? 1 : 0, r, 0);

		int score = p.score;
		float score_norm = norm_score(score);
		float lead_gap = (seat == cp)
			? (static_cast<float>(score - max_other) / 25000.f) : 0.f;
		idx = push(idx, static_cast<int>(SegmentType::PLAYER_SCORE), TILE_PAD,
		           bucket_score(score), r, 0,
		           score_norm, lead_gap, 0.f, 0.f);
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 6: GLOBAL CONTEXT
// ------------------------------------------------------------------

int TableTokenizer::encode_global_context(int idx, int cp) {
	auto& me = table_->players[cp];
	int game_wind = static_cast<int>(table_->game_wind);
	int oya = table_->oya;
	int round_index = oya & 0x3;
	int game_number = ((game_wind - static_cast<int>(Wind::East)) * 4 + oya) & 0xFF;
	int honba = table_->honba;
	int kyoutaku = table_->kyoutaku;
	int remaining = table_->get_remain_tile();
	int turn = table_->turn;

	idx = push(idx, static_cast<int>(SegmentType::GAME_WIND), TILE_PAD, game_wind, 4, 0);
	idx = push(idx, static_cast<int>(SegmentType::SELF_WIND), TILE_PAD,
	           static_cast<int>(me.wind), 0, 0);
	idx = push(idx, static_cast<int>(SegmentType::ROUND_INDEX), TILE_PAD, round_index, 4, 0);
	idx = push(idx, static_cast<int>(SegmentType::DEALER_SEAT), TILE_PAD, oya, 4, rel(oya, cp));
	idx = push(idx, static_cast<int>(SegmentType::GAME_NUMBER), TILE_PAD, game_number, 4, 0);
	idx = push(idx, static_cast<int>(SegmentType::HONBA), TILE_PAD,
	           std::min(honba, 255), 4, 0, honba / 8.f, 0.f, 0.f, 0.f);
	idx = push(idx, static_cast<int>(SegmentType::KYOUTAKU), TILE_PAD,
	           std::min(kyoutaku, 255), 4, 0, kyoutaku / 4.f, 0.f, 0.f, 0.f);
	idx = push(idx, static_cast<int>(SegmentType::REMAINING_TILES), TILE_PAD,
	           std::min(remaining, 255), 4, 0, remaining / 70.f, 0.f, 0.f, 0.f);
	idx = push(idx, static_cast<int>(SegmentType::TURN_INDEX), TILE_PAD,
	           std::min(turn, 255), 4, 0, turn / 18.f, 0.f, 0.f, 0.f);
	return idx;
}

// ------------------------------------------------------------------
// Section 7: CONTEXT TILES
// ------------------------------------------------------------------

int TableTokenizer::encode_context_tiles(int idx, int cp, int phase,
                                          bool in_response, Tile* tsumo_tile) {
	Tile* sel_tile = table_->get_selected_action_tile();
	int sel_who = table_->who_make_selection();

	if (sel_tile != nullptr) {
		int b = static_cast<int>(sel_tile->tile);
		int a = sel_tile->red_dora ? 1 : 0;
		if (in_response) {
			idx = push(idx, static_cast<int>(SegmentType::LAST_DISCARDED_TILE),
			           b, 1, rel(sel_who, cp), a);
		} else if (cp == sel_who && is_self_phase(phase) && tsumo_tile == nullptr) {
			idx = push(idx, static_cast<int>(SegmentType::SELF_TSUMO_TILE),
			           b, 1, 0, a);
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 8: VISIBLE COUNTS
// ------------------------------------------------------------------

int TableTokenizer::encode_visible_counts(int idx, int cp) {
	auto& me = table_->players[cp];
	int visible[NUM_BASE_TILES] = {};

	// Self hand
	for (auto* t : me.hand) {
		visible[static_cast<int>(t->tile)]++;
	}
	// Dora indicators
	int n_ind = std::min(table_->n_active_dora,
	                     static_cast<int>(table_->dora_indicator.size()));
	for (int i = 0; i < n_ind; ++i) {
		visible[static_cast<int>(table_->dora_indicator[i]->tile)]++;
	}
	// Rivers + fuuros for all players
	for (int seat = 0; seat < 4; ++seat) {
		auto& p = table_->players[seat];
		for (auto& rt : p.river.river) {
			visible[static_cast<int>(rt.tile->tile)]++;
		}
		for (auto& cg : p.call_groups) {
			for (auto* t : cg.tiles) {
				visible[static_cast<int>(t->tile)]++;
			}
		}
	}
	// Cap at 4
	for (int b = 0; b < NUM_BASE_TILES; ++b) {
		if (visible[b] > 4) visible[b] = 4;
	}
	// Emit tokens (only for tiles with count > 0)
	for (int b = 0; b < NUM_BASE_TILES; ++b) {
		if (visible[b] > 0) {
			idx = push(idx, static_cast<int>(SegmentType::VISIBLE_COUNT), b, visible[b], 4, 0);
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 9: FURITEN AREA
// ------------------------------------------------------------------

int TableTokenizer::encode_furiten(int idx, int cp) {
	for (int seat = 0; seat < 4; ++seat) {
		int r = rel(seat, cp);
		bool seen[NUM_BASE_TILES] = {};
		for (auto& rt : table_->players[seat].river.river) {
			seen[static_cast<int>(rt.tile->tile)] = true;
		}
		for (int b = 0; b < NUM_BASE_TILES; ++b) {
			if (seen[b]) {
				idx = push(idx, static_cast<int>(SegmentType::FURITEN_AREA), b, 1, r, 0);
			}
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// Section 10: ORACLE
// ------------------------------------------------------------------

int TableTokenizer::encode_oracle(int idx, int cp) {
	for (int seat = 0; seat < 4; ++seat) {
		if (seat == cp) continue;
		int opp_counts[NUM_BASE_TILES][2] = {};
		for (auto* t : table_->players[seat].hand) {
			int b = static_cast<int>(t->tile);
			int a = t->red_dora ? 1 : 0;
			opp_counts[b][a]++;
		}
		int r = rel(seat, cp);
		for (int b = 0; b < NUM_BASE_TILES; ++b) {
			for (int a = 0; a <= 1; ++a) {
				int c = opp_counts[b][a];
				if (c > 0) {
					idx = push(idx, static_cast<int>(SegmentType::SELF_HAND),
					           b, c, r, a | 0x80);
				}
			}
		}
	}
	return idx;
}

// ------------------------------------------------------------------
// ACTION MASK
// ------------------------------------------------------------------

void TableTokenizer::fill_action_mask(int cp, bool riichi_stage2, Tile* sel_tile) {
	if (riichi_stage2) {
		action_mask_[A_RIICHI] = true;
		action_mask_[A_PASS_RIICHI] = true;
		return;
	}

	int phase = static_cast<int>(table_->get_phase());
	bool is_self;
	if (is_self_phase(phase)) {
		is_self = true;
	} else if (is_response_phase(phase) || is_chankan_phase(phase)) {
		is_self = false;
	} else {
		return;
	}

	// Tile being responded to (for chi disambiguation)
	int chi_tile_id = -1;
	if (sel_tile != nullptr && !is_self) {
		chi_tile_id = static_cast<int>(sel_tile->tile);
	}

	if (is_self) {
		for (auto& sel : table_->self_actions) {
			mask_one_self(sel, chi_tile_id);
		}
	} else {
		for (auto& sel : table_->response_actions) {
			mask_one_response(sel, chi_tile_id);
		}
	}
}

// Private helper: classify and set action mask for a single self-action
void TableTokenizer::mask_one_self(const SelfAction& sel, int /*chi_tile_id*/) {
	BaseAction base = sel.action;
	auto& tiles = sel.correspond_tiles;

	if (base == BaseAction::Discard) {
		if (tiles.empty()) return;
		int base_t = static_cast<int>(tiles[0]->tile);
		action_mask_[A_DISCARD_BASE + base_t] = true;
		if (tiles[0]->red_dora) {
			if (base_t == 4) action_mask_[A_DISCARD_RED5M] = true;
			else if (base_t == 13) action_mask_[A_DISCARD_RED5P] = true;
			else if (base_t == 22) action_mask_[A_DISCARD_RED5S] = true;
		}
	} else if (base == BaseAction::AnKan) {
		action_mask_[A_ANKAN] = true;
	} else if (base == BaseAction::KaKan) {
		action_mask_[A_KAKAN] = true;
	} else if (base == BaseAction::Riichi) {
		action_mask_[A_RIICHI] = true;
	} else if (base == BaseAction::Tsumo) {
		action_mask_[A_TSUMO] = true;
	} else if (base == BaseAction::Kyushukyuhai) {
		action_mask_[A_PUSH] = true;
	} else if (base == BaseAction::Ron ||
	           base == BaseAction::ChanKan ||
	           base == BaseAction::ChanAnKan) {
		action_mask_[A_RON] = true;
	} else if (base == BaseAction::Pass) {
		action_mask_[A_PASS_RESPONSE] = true;
	}
}

// Private helper: classify and set action mask for a single response-action
void TableTokenizer::mask_one_response(const ResponseAction& sel, int chi_tile_id) {
	BaseAction base = sel.action;
	auto& tiles = sel.correspond_tiles;

	if (base == BaseAction::Chi) {
		if (chi_tile_id < 0 || tiles.size() < 2) {
			// Conservatively allow all three chi variants
			action_mask_[A_CHILEFT] = action_mask_[A_CHIMIDDLE] = action_mask_[A_CHIRIGHT] = true;
			bool used_red = false;
			for (auto* t : tiles) { if (t->red_dora) { used_red = true; break; } }
			if (used_red) {
				action_mask_[A_CHILEFT_USERED] = action_mask_[A_CHIMIDDLE_USERED] =
				action_mask_[A_CHIRIGHT_USERED] = true;
			}
			return;
		}
		int kind = classify_chi(chi_tile_id, tiles);
		int slot = (kind == 0) ? A_CHILEFT : (kind == 1) ? A_CHIMIDDLE : A_CHIRIGHT;
		int slot_red = (kind == 0) ? A_CHILEFT_USERED
		             : (kind == 1) ? A_CHIMIDDLE_USERED : A_CHIRIGHT_USERED;
		bool used_red = false;
		for (auto* t : tiles) { if (t->red_dora) { used_red = true; break; } }
		if (used_red) action_mask_[slot_red] = true;
		else action_mask_[slot] = true;
	} else if (base == BaseAction::Pon) {
		bool used_red = false;
		for (auto* t : tiles) { if (t->red_dora) { used_red = true; break; } }
		if (used_red) action_mask_[A_PON_USERED] = true;
		else action_mask_[A_PON] = true;
	} else if (base == BaseAction::Kan) {
		action_mask_[A_MINKAN] = true;
	} else if (base == BaseAction::Ron ||
	           base == BaseAction::ChanKan ||
	           base == BaseAction::ChanAnKan) {
		action_mask_[A_RON] = true;
	} else if (base == BaseAction::Pass) {
		action_mask_[A_PASS_RESPONSE] = true;
	}
}

}  // namespace v3
}  // namespace TrainingDataEncoding

namespace_mahjong_end

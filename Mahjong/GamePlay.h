﻿#ifndef GAMEPLAY_H
#define GAMEPLAY_H

#include "Table.h"
#include <array>

namespace_mahjong

class PaipuReplayer
{
public:
	Table table;
	bool write_log = false;
	PaipuReplayer() = default;
	void init(const std::vector<int> &yama, const std::vector<int> &init_scores, int kyoutaku, int honba, int game_wind, int oya);
	std::vector<SelfAction> get_self_actions() const;
	std::vector<ResponseAction> get_response_actions() const;
	
	bool make_selection(int selection);
	bool make_selection_from_action(BaseAction action, std::vector<int> correspond_tiles);
	int get_selection_from_action(BaseAction action, std::vector<int> correspond_tiles);
	int get_phase() const;
	inline void set_write_log(bool is_write) { write_log = is_write; }
	Result get_result() const;	
	~PaipuReplayer() {  } 
};

namespace_mahjong_end

#endif

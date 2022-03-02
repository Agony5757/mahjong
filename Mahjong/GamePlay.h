#ifndef GAMEPLAY_H
#define GAMEPLAY_H

#include "Table.h"
#include <array>

class PaipuReplayer
{
public:
	Table table;
	bool write_log = false;
	PaipuReplayer() = default;
	void init(std::vector<int> yama, std::vector<int> init_scores, int 立直棒, int 本场, int 场风, int 亲家);
	std::vector<SelfAction> get_self_actions() const;
	std::vector<ResponseAction> get_response_actions() const;
	
	bool make_selection(int selection);
	bool make_selection_from_action(BaseAction action, std::vector<int> correspond_tiles);
	int get_selection_from_action(BaseAction action, std::vector<int> correspond_tiles);
	int get_phase() const;
	inline void set_log(bool is_write) { write_log = is_write; }
	Result get_result() const;	
	~PaipuReplayer() {  } 
};

#endif
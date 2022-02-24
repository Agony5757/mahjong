#ifndef GAMEPLAY_H
#define GAMEPLAY_H

#include "Table.h"
#include <array>
std::array<int, 4> 东风局(std::array<Agent*, 4> agents, std::stringstream&);

std::array<int, 4> 南风局(std::array<Agent*, 4> agents, std::stringstream&);

std::array<int, 4> FullGame(Wind, std::array<Agent*, 4> agents, std::stringstream&);

class PaiPuReplayer
{
public:
	Table table;
	PaiPuReplayer() = default;
	void init(std::array<int, N_TILES> yama, std::array<int, 4> init_scores, int 立直棒, int 本场, int 场风, int 亲家);
	std::vector<SelfAction> get_self_actions() const;
	std::vector<ResponseAction> get_response_actions() const;
	bool make_selection(int selection);
	bool make_selection_from_action(BaseAction action, std::vector<Tile*> correspond_tiles);
	int get_phase() const;
	Result get_result() const;	
};

#endif
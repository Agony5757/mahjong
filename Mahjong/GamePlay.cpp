#include "GamePlay.h"
#include "macro.h"

namespace_mahjong
using namespace std;

void PaipuReplayer::init(vector<int> yama, vector<int> init_scores, int 立直棒, int 本场, int 场风, int 亲家)
{	
	table.set_write_log(write_log);
	table.game_init_for_replay(yama, init_scores, 立直棒, 本场, 场风, 亲家);

	/*if (write_log) {
		FILE* fp = fopen("replay.log", "w+");
		fprintf(fp, "Table table;\ntable.game_init_for_replay(%s, %s, %d, %d, %d, %d);\n",
			vec2str(yama).c_str(),
			vec2str(init_scores).c_str(),
			立直棒, 本场, 场风, 亲家);

		fclose(fp);
	}*/
}

vector<SelfAction> PaipuReplayer::get_self_actions() const
{
	return table.get_self_actions();
}

vector<ResponseAction> PaipuReplayer::get_response_actions() const
{
	return table.get_response_actions();
}

bool PaipuReplayer::make_selection(int selection)
{	
	if (selection < 0)
	    return false;
	// if (get_phase() <= Table::PhaseEnum::P4_ACTION)
	// 	if (selection >= get_self_actions().size())
	// 		return false; 
	// else 
	//     if (selection >= get_response_actions().size())
	// 		return false; 		

	/*if (write_log) {
		FILE* fp = fopen("replay.log", "a+");
		fprintf(fp, "table.make_selection(%d);\n", selection);
		fclose(fp);
	}*/
	table.make_selection(selection);
	return true;
}

bool PaipuReplayer::make_selection_from_action(BaseAction action, vector<int> correspond_tiles)
{	
	vector<Tile*> correspond_tiles_1;
	for (int i : correspond_tiles) {
		correspond_tiles_1.push_back(&table.tiles[i]);
	}
	if (get_phase() <= Table::P4_ACTION)
	{
		auto& actions = table.self_actions;
		SelfAction action_obj(action, correspond_tiles_1);
		auto iter = find(actions.begin(), actions.end(), action_obj);	

		if (iter == actions.end())
		{
			// 出错
			return false;
		}
		else
		{		
			int idx = iter - actions.begin();		
			return make_selection(idx);			
		}
	}
	else
	{
		auto& actions = table.response_actions;
		ResponseAction action_obj(action, correspond_tiles_1);

		auto iter = find(actions.begin(), actions.end(), action_obj);
		if (iter == actions.end())
		{
			// 出错
			return false;
		}
		else
		{
			return make_selection(iter - actions.begin());
		}
	}
}

int PaipuReplayer::get_selection_from_action(BaseAction action, vector<int> correspond_tiles)
{	
	vector<Tile*> correspond_tiles_1;
	for (int i : correspond_tiles) {
		correspond_tiles_1.push_back(&table.tiles[i]);
	}
	if (get_phase() <= Table::P4_ACTION)
	{
		auto& actions = table.self_actions;
		SelfAction action_obj(action, correspond_tiles_1);
		auto iter = find(actions.begin(), actions.end(), action_obj);	
	
		if (iter == actions.end())
		{
			// 出错
			return -1;
		}
		else
		{		
			return iter - actions.begin();				
		}
	}
	else
	{
		auto& actions = table.response_actions;
		ResponseAction action_obj(action, correspond_tiles_1);

		auto iter = find(actions.begin(), actions.end(), action_obj);
		if (iter == actions.end())
		{
			// 出错
			return -1;
		}
		else
		{		
			return iter - actions.begin();				
		}
	}
}

int PaipuReplayer::get_phase() const
{
	return table.get_phase();
}

Result PaipuReplayer::get_result() const
{
	return table.get_result();
}

namespace_mahjong_end

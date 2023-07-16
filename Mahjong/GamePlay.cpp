#include "GamePlay.h"
#include "macro.h"

using namespace std;

namespace_mahjong

void PaipuReplayer::init(const vector<int> &yama, const vector<int> &init_scores, int kyoutaku, int honba, int game_wind, int oya)
{	
	fmt::print("Yama Size = {}\n", yama.size());
	if (write_log)
		table.set_debug_mode(Table::debug_buffer);
	
	table.game_init_for_replay(yama, init_scores, kyoutaku, honba, game_wind, oya);

	/*if (write_log) {
		FILE* fp = fopen("replay.log", "w+");
		fprintf(fp, "Table table;\ntable.game_init_for_replay(%s, %s, %d, %d, %d, %d);\n",
			vec2str(yama).c_str(),
			vec2str(init_scores).c_str(),
			kyoutaku, honba, game_wind, oya);

		fclose(fp);
	}*/
}

vector<SelfAction> PaipuReplayer::get_self_actions() const
{
	return table.self_actions;
}

vector<ResponseAction> PaipuReplayer::get_response_actions() const
{
	return table.response_actions;
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
	int idx = get_selection_from_action(action, correspond_tiles);
	return make_selection(idx);
}

int PaipuReplayer::get_selection_from_action(BaseAction action, vector<int> correspond_tiles)
{
	vector<Tile*> correspond_tiles_1;
	for (int i : correspond_tiles) {
		correspond_tiles_1.push_back(&table.tiles[i]);
	}
	return table.get_selection_from_action_tile(action, correspond_tiles_1);
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

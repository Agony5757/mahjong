#include "GamePlay.h"
#include "macro.h"

using namespace std;

array<int, 4> 东风局(array<Agent *, 4> agents, stringstream &ss)
{
	return FullGame(Wind::East, agents, ss);
}

array<int, 4> 南风局(array<Agent *, 4> agents, stringstream &ss) {
	return FullGame(Wind::South, agents, ss);
}

array<int, 4> FullGame(Wind 局风, array<Agent*, 4> agents, stringstream &ss)
{
	array<int, 4> score = { 25000,25000,25000,25000 };

	Wind 场风 = Wind::East;
	int n立直棒 = 0;
	int n本场 = 0;
	int 局 = 1; // 从东1局开始
	while (none_of(begin(score), end(score), [](int& s) {return s < 0; })) {
		ss << wind_to_string(场风) << 局 << "局" << endl;

		Table t(局 - 1, agents[0], agents[1], agents[2], agents[3]);
		t.n立直棒 = n立直棒;
		t.n本场 = n本场;
		for (int i = 0; i < 4; ++i) {
			t.players[i].score = score[i];
		}

		ss << n本场 << "本场;" << n立直棒 << "立直棒" << endl;
		Result s = t.GameProcess(false);
		ss << s.to_string();
		for (int i = 0; i < 4; ++i)
			score[i] = s.score[i];

		if (!s.连庄)
			局++; //没有连庄则流转

		n立直棒 = s.n立直棒;
		n本场 = s.n本场;

		if (场风 == next_wind(局风)) {
			// 已经西入
			if (any_of(begin(score), end(score), [](int &s) {return s > 30000; })) {
				break;
			}
		}

		if (局 == 5) {
			if (场风 == next_wind(局风)) {
				break;
				//已经南/西入，则不再入
			}
			if (any_of(begin(score), end(score), [](int &s) {return s > 30000; })) {
				break;
				// 有人30000以上，不南入
			}
			else {
				局 = 1;
				场风 = (Wind)((int)场风 + 1);
				// 下一种风开始
			}
		}

	}
	return score;
}

void PaipuReplayer::init(vector<int> yama, vector<int> init_scores, int 立直棒, int 本场, int 场风, int 亲家)
{
	table.game_init_for_replay(yama, init_scores, 立直棒, 本场, 场风, 亲家);
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
	if (selection >= get_self_actions().size()) { return false; }
	table.make_selection(selection);
	return true;
}

bool PaipuReplayer::make_selection_from_action(BaseAction action, vector<int> correspond_tiles)
{	
	vector<Tile*> correspond_tiles_1;
	for (int i : correspond_tiles) {
		correspond_tiles_1.push_back(&table.tiles[i]);
		printf("【%d %s】", i, table.tiles[i].to_simple_string().c_str());
	}
	if (get_phase() <= Table::P4_ACTION)
	{
		auto& actions = table.self_actions;
		SelfAction action_obj(action, correspond_tiles_1);
		auto iter = find(actions.begin(), actions.end(), action_obj);	

		if (correspond_tiles[0] == 37) {
			for (auto sa:actions){printf("%s ", sa.to_string().c_str());}
			printf("-> %d\n", iter-actions.begin())	;	
		}
		
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

int PaipuReplayer::get_phase() const
{
	return table.get_phase();
}

Result PaipuReplayer::get_result() const
{
	return table.get_result();
}
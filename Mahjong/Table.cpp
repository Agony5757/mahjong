#include "Table.h"
#include "macro.h"
#include "Rule.h"
#include "GameResult.h"
#include "ScoreCounter.h"
#include <random>
#include <cstring>

namespace_mahjong
using namespace std;

vector<BaseTile> Table::get_dora() const
{
	vector<BaseTile> doratiles;
	for (int i = 0; i < dora_spec; ++i) {
		doratiles.push_back(get_dora_next(宝牌指示牌[i]->tile));
	}
	return doratiles;
}

vector<BaseTile> Table::get_ura_dora() const
{
	vector<BaseTile> doratiles;
	for (int i = 0; i < dora_spec; ++i) {
		doratiles.push_back(get_dora_next(里宝牌指示牌[i]->tile));
	}
	return doratiles;
}

void Table::init_tiles()
{
	for (int i = 0; i < N_TILES; ++i) {
		tiles[i].tile = static_cast<BaseTile>(i / 4);
		tiles[i].red_dora = false;
		tiles[i].id = i;
	}
}

void Table::init_red_dora_3()
{
	tiles[4 * 4].red_dora = true; // 0m 5m 5m 5m
	tiles[4 * 4 + 9 * 4].red_dora = true; // 0p 5p 5p 5p
	tiles[4 * 4 + 9 * 4 + 9 * 4].red_dora = true; // 0s 5s 5s 5s
}

void Table::shuffle_tiles()
{
	static std::default_random_engine rd(time(nullptr));

	if (use_seed) {
		rd.seed(seed);
	}
	std::shuffle(牌山.begin(), 牌山.end(), rd);

	if (write_log) {
		yama_log.reserve(N_TILES);
		for (auto t : 牌山) {
			yama_log.push_back(t->id);
		}
	}
}

void Table::init_yama()
{
	牌山.resize(N_TILES);
	for (int i = 0; i < N_TILES; ++i) {
		牌山[i] = &(tiles[i]);
	}
}

void Table::init_dora()
{
	dora_spec = 1;
	宝牌指示牌 = { 牌山[5],牌山[7],牌山[9],牌山[11],牌山[13] };
	里宝牌指示牌 = { 牌山[4],牌山[6],牌山[8],牌山[10],牌山[12] };
}

string Table::export_yama() {
	stringstream ss;
	for (int i = N_TILES - 1; i >= 0; --i) {
		ss << tiles[i].to_simple_string();
	}
	return ss.str();
}

void Table::import_yama(string yama) {
	constexpr int LENGTH = N_TILES * sizeof(Tile);
	Base64 base64;
	auto decode = base64.Decode(yama, LENGTH);
	const char *s = decode.c_str();
	for (int i = 0; i < N_TILES; i++) {
		memcpy(tiles + i, s + i * sizeof(Tile), sizeof(Tile));
	}
}

void Table::import_yama(std::vector<int> yama)
{
	if (yama.size() != N_TILES)
		throw runtime_error("Yama import fail.");
	牌山.resize(N_TILES);
	for (int i = 0; i < N_TILES; i++) {
		牌山[i] = tiles + yama[i];
	}
}

void Table::init_wind()
{
	players[庄家].wind = Wind::East;
	players[(庄家 + 1) % 4].wind = Wind::South;
	players[(庄家 + 2) % 4].wind = Wind::West;
	players[(庄家 + 3) % 4].wind = Wind::North;
}

void Table::init_before_playing()
{
	// 初始化每人自风
	init_wind();
	turn = 庄家;

	// 全部自动整理手牌（可能不需要）
	for (int i = 0; i < 4; ++i) {
		players[i].sort_hand();
		players[i].update_听牌();
	}

	if (write_log) {
		auto init_score = {
			players[0].score,
			players[1].score,
			players[2].score,
			players[3].score,
		};
		FILE* fp = fopen(write_log_filename.c_str(), "w+");
		fprintf(fp, "Table table;\ntable.game_init_for_replay(%s, %s, %d, %d, %d, %d);\n",
			vec2str(yama_log).c_str(),
			vec2str(init_score).c_str(),			
			n立直棒, n本场, 场风, 庄家);

		fclose(fp);
	}

	from_beginning();
}

void Table::game_init() {
	init_tiles();
	init_red_dora_3();
	init_yama();
	shuffle_tiles();
	init_dora();

	//// 每人发13张牌
	//for (int i = 0; i < 4; ++i){
	//	deal_tile((i + 庄家) % 4, 13); // 从庄
	//	players[i].sort_hand();
	//}

	deal_tenhou_style();
	init_before_playing();
}

void Table::game_init_for_replay(std::vector<int> yama, std::vector<int> init_scores, int 立直棒_, int 本场_, int 场风_, int 亲家_)
{
	庄家 = 亲家_;
	场风 = Wind(场风_);
	n立直棒 = 立直棒_;
	n本场 = 本场_;

	init_tiles();
	init_red_dora_3();
	import_yama(yama);
	yama_log = yama;
	init_dora();
	deal_tenhou_style();

	for (int i = 0; i < 4; ++i) {
		players[i].score = init_scores[i];
	}

	init_before_playing();
}

void Table::game_init_with_metadata(unordered_map<string, string> metadata)
{
	// yama : "1z1z1z..."
	using namespace std;

	// TODO: Fix "tiles"
	if (metadata.find("yama") != metadata.end()) {
		auto val = metadata["yama"];
		if (val.size() != N_TILES * 2) throw runtime_error("Yama string incomplete.");
		for (int i = 0; i < N_TILES * 2; i += 2) {
			bool red_dora;
			// 逆序插入

			tiles[N_TILES - 1 - i / 2].tile = char2_to_basetile(val[i], val[i + 1], red_dora);
			tiles[N_TILES - 1 - i / 2].red_dora = red_dora;
		}
	}
	else {
		init_tiles();
		init_red_dora_3();
		init_yama();
		shuffle_tiles();
		init_dora();
	}

	if (metadata.find("oya") != metadata.end()) {
		auto val = metadata["oya"];
		if (val == "0") {
			庄家 = 0;
		}
		else if (val == "1") {
			庄家 = 1;
		}
		else if (val == "2") {
			庄家 = 2;
		}
		else if (val == "3") {
			庄家 = 3;
		}
		else throw runtime_error("Cannot Read Option: oya");
	}
	else {
		庄家 = 0;
	}

	if (metadata.find("wind") != metadata.end()) {
		auto val = metadata["wind"];
		if (val == "east") {
			场风 = Wind::East;
		}
		else if (val == "west") {
			场风 = Wind::West;
		}
		else if (val == "south") {
			场风 = Wind::South;
		}
		else if (val == "north") {
			场风 = Wind::North;
		}
		else throw runtime_error("Cannot Read Option: wind");
	}
	else {
		场风 = Wind::East;
	}

	// 每人发13张牌
	if (metadata.find("deal") != metadata.end()) {
		auto val = metadata["deal"];
		if (val == "from_oya") {
			for (int i = 庄家; i < 庄家 + 4; ++i) {
				deal_tile(i % 4, 13);
			}
		}
		else if (val == "from_0") {
			deal_tile(0, 13);
			deal_tile(1, 13);
			deal_tile(2, 13);
			deal_tile(3, 13);
		}
		else if (val == "tenhou") {
			deal_tenhou_style();
		}
		else throw runtime_error("Cannot Read Option: deal");
	}
	else {
		/*deal_tile(0, 13);
		deal_tile(1, 13);
		deal_tile(2, 13);
		deal_tile(3, 13);*/
		deal_tenhou_style();
	}

	init_before_playing();
}

array<int, 4> Table::get_scores()
{
	array<int, 4> scores;
	for (int i = 0; i < 4; ++i)
		scores[i] = players[i].score;
	return scores;
}

void Table::next_turn(int nextturn)
{
	Player& player = players[turn];
	BaseAction selected_base_action = selected_action.action;
	// 在切换之前，更新玩家的听牌列表，以及更新他的振听情况
	if (selected_base_action == BaseAction::立直) {
		// 立直一定更新
		player.update_听牌();
		player.update_舍牌振听();
	}
	else if (selected_base_action == BaseAction::出牌) {
		if (player.river.river.back().fromhand) {
			// 手切更新听牌列表
			player.update_听牌();
			player.update_舍牌振听();
		}
	}
	if (selected_base_action == BaseAction::暗杠) {
		player.update_听牌();
		player.remove_听牌(selected_action.correspond_tiles[0]->tile);
		player.update_舍牌振听();
	}
	if (selected_base_action == BaseAction::加杠) {
		player.update_听牌();
		player.remove_听牌(selected_action.correspond_tiles[0]->tile);
		player.update_舍牌振听();
	}

	// 更新完毕，正式切换turn，解除他的同巡振听
	turn = nextturn;
	phase = PhaseEnum(turn);
	players[turn].同巡振听 = false; 

}

void Table::from_beginning()
{
#ifdef Profiling
	FunctionProfiler;
#endif

	const static auto 四风连打牌 = [](array<Player, 4>& players) {
		BaseTile t0 = players[0].river[0].tile->tile;
		BaseTile t1 = players[1].river[0].tile->tile;
		BaseTile t2 = players[2].river[0].tile->tile;
		BaseTile t3 = players[3].river[0].tile->tile;

		return t0 == t1 && t2 == t3 && t0 == t2 && t1 >= BaseTile::_1z && t1 <= BaseTile::_4z;
	};

	// 四风连打判定
	if (players[0].river.size() == 1 &&
		players[1].river.size() == 1 &&
		players[2].river.size() == 1 &&
		players[3].river.size() == 1 &&
		players[0].副露s.size() == 0 &&
		players[1].副露s.size() == 0 &&
		players[2].副露s.size() == 0 &&
		players[3].副露s.size() == 0 &&
		四风连打牌(players))
	{
		result = 四风连打流局结算(this);
		fullGameLog.logGameOver(result);
		phase = GAME_OVER;
		return;
	}

	if (players[0].riichi &&
		players[1].riichi &&
		players[2].riichi &&
		players[3].riichi) {
		result = 四立直流局结算(this);
		phase = GAME_OVER;
		return;
	}

	// 判定四杠散了
	if (get_remain_kan_tile() == 0) {
		int n_杠 = 0;
		for (int i = 0; i < 4; ++i) {
			if (any_of(players[i].副露s.begin(), players[i].副露s.end(),
				[](Fulu& f) {
					return f.type == Fulu::暗杠 ||
						f.type == Fulu::大明杠 ||
						f.type == Fulu::加杠;
				})) {
				// 统计一共有多少个人杠过
				n_杠++;
			}
		}
		// 2个或更多人杠过
		if (n_杠 >= 2) {
			result = 四杠流局结算(this);
			phase = GAME_OVER;
			return;
		}
	}

	if (get_remain_tile() == 0) {
		result = 荒牌流局结算(this);
		phase = GAME_OVER;
		return;
	}

	// 全部自动整理手牌（可能不需要）
	for (int i = 0; i < 4; ++i) {
		players[i].sort_hand();
	}

	// 杠后从岭上摸牌
	if (after_daiminkan() || after_ankan() || after_加杠()) {
		deal_tile_岭上(turn);
	}
	// 吃碰后不摸牌，其他时候正常发牌
	else if (!after_chipon()){
		发牌(turn);
	}

	vector<SelfAction> actions;
	if (players[turn].is_riichi())
	{
		self_actions = GetRiichiSelfActions();
	}
	else
	{
		volatile profiler _("SelfActions");
		self_actions = GetSelfActions();
	}

	phase = (PhaseEnum)turn;
}

void Table::test_show_yama_with_王牌()
{
	cout << "牌山:";
	if (牌山.size() < 14) {
		cout << "牌不足14张" << endl;
		return;
	}
	for (int i = 0; i < 14; ++i) {
		cout << 牌山[i]->to_string() << " ";
	}
	cout << "(王牌区)| ";
	for (int i = 14; i < 牌山.size(); ++i) {
		cout << 牌山[i]->to_string() << " ";
	}
	cout << endl;
	cout << "宝牌指示牌为:";
	for (int i = 0; i < dora_spec; ++i) {
		cout << 宝牌指示牌[i]->to_string() << " ";
	}
	cout << endl;
}

void Table::test_show_yama()
{
	cout << "牌山:";
	for (int i = 0; i < 牌山.size(); ++i) {
		cout << 牌山[i]->to_string() << " ";
	}
	cout << "共" << 牌山.size() << "张牌";
	cout << endl;
}

void Table::test_show_player_hand(int i_player)
{
	players[i_player].test_show_hand();
}

void Table::test_show_all_player_hand()
{
	for (int i = 0; i < 4; ++i) {
		cout << "Player" << i << " : "
			<< players[i].hand_to_string()
			<< endl;
	}
	cout << endl;
}

void Table::test_show_player_info(int i_player)
{
	cout << "Player" << i_player << " : "
		<< endl << players[i_player].to_string();
}

void Table::test_show_all_player_info()
{
	for (int i = 0; i < 4; ++i)
		test_show_player_info(i);
}

void Table::test_show_full_gamelog()
{
	cout << "Full GameLog:" << endl;
	cout << fullGameLog.to_string();
}

void Table::deal_tile(int i_player)
{		
	players[i_player].hand.push_back(牌山.back());
	牌山.pop_back();
}

/* 如果还有2/4张岭上牌，则摸倒数第2张（因为最后一张压在下面）*/
void Table::deal_tile_岭上(int i_player)
{
	dora_spec++; // 先翻dora
	int n_kan = get_remain_kan_tile();
	auto iter = 牌山.begin();
	if (n_kan % 2 == 0) ++iter;
	players[i_player].hand.push_back(*iter);
	牌山.erase(iter);
}

void Table::deal_tile(int i_player, int n_tiles)
{
	for (int i = 0; i < n_tiles; ++i) {
		deal_tile(i_player);
	}
}

void Table::deal_tenhou_style()
{
	// 每次摸4个
	for (int round = 0; round < 3; ++round) {
		for (int i = 0; i < 4; ++i) {
			deal_tile((庄家 + i) % 4, 4);
		}
	}
	// 跳章
	// 每次摸1个
	for (int i = 0; i < 4; ++i) {
		deal_tile((庄家 + i) % 4);
	}
}

void Table::发牌(int i_player)
{
	deal_tile(i_player);
	fullGameLog.log摸牌(i_player, players[i_player].hand.back());
}

void Table::发岭上牌(int i_player)
{
	dora_spec++; // 先翻dora
	deal_tile(i_player);
	fullGameLog.log摸牌(i_player, players[i_player].hand.back());
}

string Table::to_string(int option) const
{
	stringstream ss;
	if (option & ToStringOption::YAMA) {
		ss << "牌山:";
		if (牌山.size() < 14) {
			ss << "牌不足14张" << endl;
			return ss.str();
		}
		for (int i = 0; i < 14; ++i) {
			ss << 牌山[i]->to_string() << " ";
		}
		ss << "(王牌区)| ";
		for (int i = 14; i < 牌山.size(); ++i) {
			ss << 牌山[i]->to_string() << " ";
		}
		ss << endl;
	}
	if (option & ToStringOption::DORA) {
		ss << "宝牌指示牌为:";
		for (int i = 0; i < dora_spec; ++i) {
			ss << 宝牌指示牌[i]->to_string() << " ";
		}
		ss << endl;
	}

	if (option & ToStringOption::REMAIN_TILE) {
		ss << "余" << get_remain_tile() << "张牌" << endl;
	}
	if (option & ToStringOption::PLAYER) {
		for (int i = 0; i < 4; ++i)
		ss << "Player" << i << " : "
			<< endl << players[i].to_string();
		ss << endl;
	}
	if (option & ToStringOption::亲家) {
		ss << "亲家: Player " << 庄家 << endl;
	}
	if (option & ToStringOption::N_本场) {
		ss << n本场 << "本场";
	}
	if (option & ToStringOption::N_立直棒) {
		ss << n本场 << "立直棒";
	}
	ss << endl;
	return ss.str();
}

vector<SelfAction> Table::GetSelfActions()
{
	FunctionProfiler;
	vector<SelfAction> actions;
	auto& the_player = players[turn];
	
	merge_into(actions, the_player.get_九种九牌());	
	merge_into(actions, the_player.get_打牌(after_chipon()));
	
	// 吃/碰后，且已经4杠的场合，不能继续杠
	if (!after_chipon() && get_remain_kan_tile() > 0) {
		merge_into(actions, the_player.get_暗杠());
		merge_into(actions, the_player.get_加杠());
	}
	merge_into(actions, the_player.get_自摸(this));

	if (players[turn].score >= 1000 && get_remain_tile() >= 4)
		// 有1000点才能立直，否则不行
		// 牌河有4张以下牌，则不能立直
		merge_into(actions, the_player.get_立直());

	sort(actions.begin(), actions.end());
	//actions.erase(unique(actions.begin(), actions.end(), action_unique_pred<SelfAction>));

	return actions;
}

vector<SelfAction> Table::GetRiichiSelfActions()
{
	vector<SelfAction> actions;
	auto& the_player = players[turn];
	
	if (get_remain_kan_tile() > 0)
		merge_into(actions, the_player.riichi_get_暗杠());
	merge_into(actions, the_player.riichi_get_打牌());
	merge_into(actions, the_player.get_自摸(this));

	sort(actions.begin(), actions.end());
	//actions.erase(unique(actions.begin(), actions.end(), action_unique_pred<SelfAction>));
	return actions;
}

vector<ResponseAction> Table::GetResponseActions(
	int i, Tile* tile, bool is下家)
{
	FunctionProfiler;
	vector<ResponseAction> actions;
	
	// first: pass action
	ResponseAction action_pass;
	action_pass.action = BaseAction::pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];

	merge_into(actions, the_player.get_荣和(this, tile));

	// 立直则不能鸣牌
	// 海底牌也不能鸣牌
	if (!the_player.is_riichi() && get_remain_tile() != 0) {
		merge_into(actions, the_player.get_Pon(tile));
		if (get_remain_kan_tile() > 0)
			merge_into(actions, the_player.get_Kan(tile));

		if (is下家) {
			merge_into(actions, the_player.get_Chi(tile));
		}
	}

	sort(actions.begin(), actions.end());
	//actions.erase(unique(actions.begin(), actions.end(), action_unique_pred<ResponseAction>));
	return actions;
}

vector<ResponseAction> Table::Get抢暗杠(int i, Tile * tile)
{
	vector<ResponseAction> actions;

	// first: pass action
	ResponseAction action_pass;
	action_pass.action = BaseAction::pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];
	merge_into(actions, the_player.get_抢暗杠(tile));

	return actions;
}

vector<ResponseAction> Table::Get抢杠(int i, Tile * tile)
{
	vector<ResponseAction> actions;

	// first: pass action
	ResponseAction action_pass;
	action_pass.action = BaseAction::pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];
	merge_into(actions, the_player.get_抢杠(tile));

	return actions;
}

int Table::get_selection_from_action_tile(BaseAction action_type, const vector<Tile*> &tiles) const
{
	if (phase == GAME_OVER) { return -1; }
	else if (phase <= P4_ACTION) {
		return get_action_index(self_actions, action_type, tiles);
	}
	else {
		return get_action_index(response_actions, action_type, tiles);
	}
}

void Table::make_selection_from_action_tile(BaseAction action_type, const vector<Tile*>& tiles)
{
	int idx = get_selection_from_action_tile(action_type, tiles);
	if (idx >= 0)
		make_selection(idx);
	else {
		throw std::runtime_error(fmt::format("Cannot locate action with action = {}", action_type));
	}
}

int Table::get_selection_from_action_basetile(BaseAction action_type, const vector<BaseTile>& tiles, bool use_red_dora) const
{
	if (phase == GAME_OVER) { return -1; }
	else if (phase <= P4_ACTION) {
		return get_action_index(self_actions, action_type, tiles, use_red_dora);
	}
	else {
		return get_action_index(response_actions, action_type, tiles, use_red_dora);
	}
}

void Table::make_selection_from_action_basetile(BaseAction action_type, const vector<BaseTile> &tiles, bool use_red_dora)
{
	int idx = get_selection_from_action_basetile(action_type, tiles, use_red_dora);
	if (idx >= 0)
		make_selection(idx);
	else {
		throw std::runtime_error(fmt::format("Cannot locate action with action = {}", action_type));
	}
}

void Table::make_selection(int selection)
{
#ifdef Profiling
	FunctionProfiler;
#endif
	// 这个地方控制了游戏流转
	if (write_log) {
		FILE* fp = fopen(write_log_filename.c_str(), "a+");
		fprintf(fp, "\ntable.make_selection(%d);", selection);
		fclose(fp);
	}
	// 分为两种情况，如果是ACTION阶段
	switch (phase) {
	case GAME_OVER:
		return;
	case P1_ACTION:
	case P2_ACTION:
	case P3_ACTION:
	case P4_ACTION: {

		if (self_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		selected_action = self_actions[selection];
		switch (selected_action.action) {
		case BaseAction::九种九牌:
			result = 九种九牌流局结算(this);
			fullGameLog.log九种九牌(turn, result);

			phase = GAME_OVER;
			return;
		case BaseAction::自摸:
			result = 自摸结算(this);
			phase = GAME_OVER;
			return;
		case BaseAction::出牌:
		case BaseAction::立直:
		{
			// 决定不胡牌，则不具有一发状态
			players[turn].一发 = false;

			tile = selected_action.correspond_tiles[0];
			// 等待回复

			// 大部分情况都是手切, 除了上一步动作为 出牌 加杠 暗杠
			// 并且判定抉择弃牌是不是最后一张牌

			bool FROM_手切摸切 = FROM_手切;
			if (last_action == BaseAction::出牌 ||
				last_action == BaseAction::加杠 ||
				last_action == BaseAction::暗杠) {
				// tile是不是最后一张
				if (tile == players[turn].hand.back())
					FROM_手切摸切 = FROM_摸切;
			}
			players[turn].move_from_hand_to_river(tile, river_counter, selected_action.action == BaseAction::立直, FROM_手切摸切);

			phase = P1_RESPONSE;
			if (0 == turn) {
				ResponseAction ra;
				ra.action = BaseAction::pass;
				response_actions = { ra };
			}
			else {
				// 对于所有其他人
				bool is下家 = false;
				if (0 == (turn + 1) % 4)
					is下家 = true;
				response_actions = GetResponseActions(0, tile, is下家);
			}
			return;
		}
		case BaseAction::暗杠:
		{
			tile = selected_action.correspond_tiles[0];

			// 第一巡消除
			players[turn].first_round = false;
			// 等待回复
			phase = P1_抢暗杠RESPONSE;
			if (0 == turn) {
				ResponseAction ra;
				ra.action = BaseAction::pass;
				response_actions = { ra };
			}
			else {
				response_actions = Get抢暗杠(0, tile);
			}

			return;
		}
		case BaseAction::加杠:
		{
			tile = selected_action.correspond_tiles[0];

			// 第一巡消除
			players[turn].first_round = false;
			// 等待回复
			phase = P1_抢杠RESPONSE;
			if (0 == turn) {
				ResponseAction ra;
				ra.action = BaseAction::pass;
				response_actions = { ra };
			}
			else {
				response_actions = Get抢杠(0, tile);
			}
			return;
		}
		default:
			throw runtime_error("Error selection.");
		}
	}

	case P1_RESPONSE:
		actions.resize(0);
		final_action = BaseAction::pass;
	case P2_RESPONSE:
	case P3_RESPONSE: {
		// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		// 立直振听判断
		int i = phase - P1_RESPONSE;
		if (i != turn &&
			players[i].is_riichi() &&
			response_actions.size() > 1 &&
			response_actions[selection].action == BaseAction::pass)
		{
			players[phase - P1_RESPONSE].立直振听 = true;
		}

		actions.push_back(response_actions[selection]);
		// 从actions中获得优先级
		if (response_actions[selection].action > final_action)
			final_action = response_actions[selection].action;

		i++; // for next player				
		if (i == turn) {
			ResponseAction ra;
			ra.action = BaseAction::pass;
			response_actions = { ra };
		}
		else {
			// 对于所有其他人			
			bool is下家 = false;
			if (i == (turn + 1) % 4)
				is下家 = true;
			response_actions = GetResponseActions(i, tile, is下家);
		}
		phase = PhaseEnum(phase + 1);
		return;
	}
	case P4_RESPONSE: {
		// 做出选择

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		actions.push_back(response_actions[selection]);
		// 从actions中获得优先级
		if (response_actions[selection].action > final_action)
			final_action = response_actions[selection].action;

		// 立直振听判断
		if (3 != turn &&
			players[3].is_riichi() &&
			response_actions.size() > 1 &&
			response_actions[selection].action == BaseAction::pass)
		{
			players[3].立直振听 = true;
		}

		// 选择优先级，并且进行response结算
		vector<int> response_player;
		for (int i = 0; i < 4; ++i) {
			if (actions[i].action == final_action) {
				response_player.push_back(i);
			}
		}
		int response = response_player[0];
		// 根据最终的final_action来进行判断
		// response_player里面保存了所有最终action和final_action相同的玩家
		// 只有在pass和荣和的时候才会出现这种情况
		// 其他情况用response来代替

		switch (final_action) {
		case BaseAction::pass:

			// 杠，打出牌之后且其他人pass
			// if (after_杠()) { dora_spec++; }

			if (selected_action.action == BaseAction::立直) {
				// 立直成功
				if (players[turn].first_round) {
					players[turn].double_riichi = true;
				}
				players[turn].riichi = true;
				n立直棒++;
				players[turn].score -= 1000;
				players[turn].一发 = true;
			}

			// 什么都不做。将action对应的牌从手牌移动到牌河里面	
			// players[turn].move_from_hand_to_river_really(tile, river_counter, FROM_手切摸切);

			// 消除第一巡
			players[turn].first_round = false;
			next_turn((turn + 1) % 4);
			last_action = selected_action.action;
			break;
		case BaseAction::吃:
		case BaseAction::碰:
		case BaseAction::杠:

			// 明杠，打出牌之后且其他人吃碰
			// if (after_杠()) { dora_spec++; }
			if (selected_action.action == BaseAction::立直) {
				// 立直成功
				if (players[turn].first_round) {
					players[turn].double_riichi = true;
				}
				players[turn].riichi = true;
				n立直棒++;
				players[turn].score -= 1000;
				// 立直即鸣牌，一定没有一发
			}

			players[turn].set_not_remained();

			players[response].门清 = false;
			players[response].move_from_hand_to_fulu(
				actions[response].correspond_tiles, tile);

			// 这是鸣牌，消除所有人第一巡和一发
			for (int i = 0; i < 4; ++i) {
				players[i].first_round = false;
				players[i].一发 = false;
			}

			// 切换turn
			next_turn(response);
			last_action = final_action;
			break;

		case BaseAction::荣和:
			result = 荣和结算(this, selected_action.correspond_tiles[0], response_player);
			phase = GAME_OVER;
			return;
		default:
			throw runtime_error("Invalid Selection.");
		}

		// 回到循环的最开始
		from_beginning();
		return;
	}

	case P1_抢杠RESPONSE:
		actions.resize(0);
		final_action = BaseAction::pass;
	case P2_抢杠RESPONSE:
	case P3_抢杠RESPONSE: {
		// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		actions.push_back(response_actions[selection]);
		// 从actions中获得优先级
		if (response_actions[selection].action > final_action)
			final_action = response_actions[selection].action;

		// 立直振听判断
		int i = phase - P1_抢杠RESPONSE;
		if (i != turn &&
			players[i].is_riichi() &&
			response_actions.size() > 1 &&
			response_actions[selection].action == BaseAction::pass)
		{
			players[i].立直振听 = true;
		}

		i++; // for next player
		if (i == turn) {
			ResponseAction ra;
			ra.action = BaseAction::pass;
			response_actions = { ra };
		}
		else {
			response_actions = Get抢杠(i, tile);
		}
		phase = PhaseEnum(phase + 1);
		return;
	}
	case P4_抢杠RESPONSE: {
		// 做出选择		

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		actions.push_back(response_actions[selection]);
		// 立直振听判断
		if (3 != turn &&
			players[3].is_riichi() &&
			response_actions.size() > 1 &&
			response_actions[selection].action == BaseAction::pass)
		{
			players[3].立直振听 = true;
		}
		// 选择优先级，并且进行response结算
		vector<int> response_player;
		for (int i = 0; i < 4; ++i) {
			if (actions[i].action == BaseAction::抢杠) {
				response_player.push_back(i);
			}
		}
		if (response_player.size() != 0) {
			// 有人抢杠则进行结算，除非加杠宣告成功，否则一发状态仍然存在
			result = 抢杠结算(this, tile, response_player);
			phase = GAME_OVER;
			return;
		}
		players[turn].play_加杠(selected_action.correspond_tiles[0]);
		last_action = BaseAction::加杠;

		// 这是鸣牌，消除所有人第一巡和一发
		for (int i = 0; i < 4; ++i) {
			players[i].first_round = false;
			players[i].一发 = false;
		}
		next_turn(turn);
		from_beginning();
		return;
	}

	case P1_抢暗杠RESPONSE:
		actions.resize(0);
		final_action = BaseAction::pass;
	case P2_抢暗杠RESPONSE:
	case P3_抢暗杠RESPONSE: {
		// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		actions.push_back(response_actions[selection]);
		// 从actions中获得优先级
		if (response_actions[selection].action > final_action)
			final_action = response_actions[selection].action;
		// 立直振听判断
		int i = phase - P1_抢暗杠RESPONSE;
		if (i != turn &&
			players[i].is_riichi() &&
			response_actions.size() > 1 &&
			response_actions[selection].action == BaseAction::pass)
		{
			players[i].立直振听 = true;
		}

		i++; // for next player
		if (i == turn) {
			ResponseAction ra;
			ra.action = BaseAction::pass;
			response_actions = { ra };
		}
		else {
			response_actions = Get抢暗杠(i, tile);
		}
		phase = PhaseEnum(phase + 1);
		return;
	}
	case P4_抢暗杠RESPONSE: {
		// 做出选择		

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}

		actions.push_back(response_actions[selection]);
		// 立直振听判断
		if (3 != turn &&
			players[3].is_riichi() &&
			response_actions.size() > 1 &&
			response_actions[selection].action == BaseAction::pass)
		{
			players[3].立直振听 = true;
		}
		// 选择优先级，并且进行response结算
		vector<int> response_player;
		for (int i = 0; i < 4; ++i) {
			if (actions[i].action == BaseAction::抢暗杠) {
				response_player.push_back(i);
			}
		}
		if (response_player.size() != 0) {
			// 有人抢暗杠则进行结算
			result = 抢暗杠结算(this, tile, response_player);
			phase = GAME_OVER;
			return;
		}
		players[turn].play_暗杠(selected_action.correspond_tiles[0]->tile);
		last_action = BaseAction::暗杠;
		// 立即翻宝牌指示牌
		// dora_spec++;

		// 这是暗杠，消除所有人第一巡和一发
		for (int i = 0; i < 4; ++i) {
			players[i].first_round = false;
			players[i].一发 = false;
		}
		next_turn(turn);
		from_beginning();
		return;
	}

	}
}
namespace_mahjong_end

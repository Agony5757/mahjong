#include "Table.h"
#include "macro.h"
#include "Rule.h"
#include "GameResult.h"
#include "ScoreCounter.h"
#include <random>
#include <cstring>

using namespace std;
namespace_mahjong

static bool check_见逃(const vector<ResponseAction>& responses, int selection)
{
	for (int i = 0; i < responses.size();++i) {
		if (responses[i].action == BaseAction::Ron ||
			responses[i].action == BaseAction::ChanKan ||
			responses[i].action == BaseAction::ChanAnKan) {
		
			if (selection != i) return true;
		}
	}
	return false;
}

void Table::new_dora() {
	n_active_dora++;
	gamelog.log_reveal_dora(dora_indicator[n_active_dora - 1]);
}

vector<BaseTile> Table::get_dora() const
{
	vector<BaseTile> doratiles;
	for (int i = 0; i < n_active_dora; ++i) {
		doratiles.push_back(get_dora_next(dora_indicator[i]->tile));
	}
	return doratiles;
}

vector<BaseTile> Table::get_ura_dora() const
{
	vector<BaseTile> doratiles;
	for (int i = 0; i < n_active_dora; ++i) {
		doratiles.push_back(get_dora_next(uradora_indicator[i]->tile));
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
	std::shuffle(yama.begin(), yama.end(), rd);

	if (write_log_mode) {
		yama_log.reserve(N_TILES);
		for (auto t : yama) {
			yama_log.push_back(t->id);
		}
	}
}

void Table::init_yama()
{
	yama.resize(N_TILES);
	for (int i = 0; i < N_TILES; ++i) {
		yama[i] = &(tiles[i]);
	}
}

void Table::init_dora()
{
	n_active_dora = 1;
	dora_indicator = { yama[5],yama[7],yama[9],yama[11],yama[13] };
	uradora_indicator = { yama[4],yama[6],yama[8],yama[10],yama[12] };
}

string Table::export_yama() {
	stringstream ss;
	for (int i = N_TILES - 1; i >= 0; --i) {
		ss << tiles[i].to_string();
	}
	return ss.str();
}

//void Table::import_yama(string yama) {
//	constexpr int LENGTH = N_TILES * sizeof(Tile);
//	Base64 base64;
//	auto decode = base64.Decode(yama, LENGTH);
//	const char *s = decode.c_str();
//	for (int i = 0; i < N_TILES; i++) {
//		memcpy(tiles + i, s + i * sizeof(Tile), sizeof(Tile));
//	}
//}

void Table::import_yama(const std::vector<int> &yama_input)
{
	if (yama_input.size() != N_TILES)
	{
		auto&& err_info = fmt::format(
			"Yama import fail. Reason: yama.size() == {} (Expect {})", 
			yama_input.size(), N_TILES);

		throw runtime_error(err_info);
	}
	yama.resize(N_TILES);
	for (int i = 0; i < N_TILES; i++) {
		yama[i] = tiles + yama_input[i];
	}
}

void Table::init_wind()
{
	players[oya].wind = Wind::East;
	players[(oya + 1) % 4].wind = Wind::South;
	players[(oya + 2) % 4].wind = Wind::West;
	players[(oya + 3) % 4].wind = Wind::North;
}

void Table::init_before_playing()
{
	// 初始化每人自风
	init_wind();
	turn = oya;

	// 全部自动整理手牌（可能不需要）
	for (int i = 0; i < 4; ++i) {
		players[i].sort_hand();
		players[i].update_atari_tiles();
	}

	debug_replay_init();
	gamelog.log_game_start(honba, kyoutaku, oya, game_wind, yama,
		get_scores(), players[0].hand, players[1].hand, players[2].hand, players[3].hand);
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

	draw_tenhou_style();
	init_before_playing();
}

void Table::game_init_for_replay(const std::vector<int> &yama, const std::vector<int> &init_scores, int kyoutaku_, int honba_, int game_wind_, int oya_)
{
	oya = oya_;
	game_wind = Wind(game_wind_);
	kyoutaku = kyoutaku_;
	honba = honba_;

	init_tiles();
	init_red_dora_3();
	import_yama(yama);
	yama_log = yama;
	init_dora();
	draw_tenhou_style();

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
			oya = 0;
		}
		else if (val == "1") {
			oya = 1;
		}
		else if (val == "2") {
			oya = 2;
		}
		else if (val == "3") {
			oya = 3;
		}
		else throw runtime_error("Cannot read option: oya");
	}
	else {
		oya = 0;
	}

	if (metadata.find("wind") != metadata.end()) {
		auto val = metadata["wind"];
		if (val == "east") {
			game_wind = Wind::East;
		}
		else if (val == "west") {
			game_wind = Wind::West;
		}
		else if (val == "south") {
			game_wind = Wind::South;
		}
		else if (val == "north") {
			game_wind = Wind::North;
		}
		else throw runtime_error("Cannot Read Option: wind");
	}
	else {
		game_wind = Wind::East;
	}

	// 每人发13张牌
	if (metadata.find("deal") != metadata.end()) {
		auto val = metadata["deal"];
		if (val == "from_oya") {
			for (int i = oya; i < oya + 4; ++i) {
				draw_n_normal(i % 4, 13);
			}
		}
		else if (val == "from_0") {
			draw_n_normal(0, 13);
			draw_n_normal(1, 13);
			draw_n_normal(2, 13);
			draw_n_normal(3, 13);
		}
		else if (val == "tenhou") {
			draw_tenhou_style();
		}
		else throw runtime_error("Cannot Read Option: deal");
	}
	else {
		draw_tenhou_style();
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
	if (selected_base_action == BaseAction::Riichi) {
		// 立直一定更新
		player.update_atari_tiles();
		player.update_furiten_river();
	}
	else if (selected_base_action == BaseAction::Discard) {
		if (player.river.river.back().fromhand) {
			// 手切更新听牌列表
			player.update_atari_tiles();
			player.update_furiten_river();
		}
	}
	else if (selected_base_action == BaseAction::AnKan) {
		player.update_atari_tiles();
		player.remove_atari_tiles(selected_action.correspond_tiles[0]->tile);
		player.update_furiten_river();
	}
	else if (selected_base_action == BaseAction::KaKan) {
		player.update_atari_tiles();
		player.remove_atari_tiles(selected_action.correspond_tiles[0]->tile);
		player.update_furiten_river();
	}

	// 更新完毕，正式切换turn，解除他的同巡振听
	turn = nextturn;
	phase = PhaseEnum(turn);
	players[turn].furiten_round = false; 

}

void Table::from_beginning()
{
	profiler _("Table.cpp/from_beginning");

	if (phase == GAME_OVER)
		return;

	const static auto 四风连打牌 = [](const array<Player, 4>& players) {
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
		players[0].call_groups.size() == 0 &&
		players[1].call_groups.size() == 0 &&
		players[2].call_groups.size() == 0 &&
		players[3].call_groups.size() == 0 &&
		四风连打牌(players))
	{
		result = generate_result_4wind(this);
		gamelog.log_gameover(result);
		phase = GAME_OVER;
		return;
	}

	if (players[0].riichi &&
		players[1].riichi &&
		players[2].riichi &&
		players[3].riichi) {
		result = generate_result_4riichi(this);
		phase = GAME_OVER;
		return;
	}

	// 判定四杠散了
	if (get_remain_kan_tile() == 0) {
		int n_kantsu = 0;
		for (int i = 0; i < 4; ++i) {
			if (any_of(players[i].call_groups.begin(), players[i].call_groups.end(),
				[](CallGroup& f) { return f.type == CallGroup::AnKan || f.type == CallGroup::DaiMinKan || f.type == CallGroup::KaKan; })) {
				// 统计一共有多少个人杠过
				n_kantsu++;
			}
		}
		// 2个或更多人杠过
		if (n_kantsu >= 2) {
			result = generate_result_4kan(this);
			phase = GAME_OVER;
			return;
		}
	}

	if (get_remain_tile() == 0) {
		result = generate_result_notile(this);
		phase = GAME_OVER;
		return;
	}

	// 全部自动整理手牌（可能不需要）
	for (int i = 0; i < 4; ++i) {
		players[i].sort_hand();
	}

	// 杠后从岭上摸牌
	if (after_daiminkan() || after_ankan() || after_kakan()) {
		draw_rinshan(turn);
	}
	// 吃碰后不摸牌，其他时候正常发牌
	else if (!after_chipon()){
		draw_normal(turn);
	}

	vector<SelfAction> actions;
	if (players[turn].is_riichi())
	{
		self_actions = _generate_riichi_self_actions();
	}
	else
	{
		self_actions = _generate_self_actions();
	}

	phase = (PhaseEnum)turn;
}

void Table::draw_tenhou_style()
{
	// 每次摸4个
	for (int round = 0; round < 3; ++round) {
		for (int i = 0; i < 4; ++i) {
			draw_n_normal((oya + i) % 4, 4);
		}
	}
	// 跳章
	// 每次摸1个
	for (int i = 0; i < 4; ++i) {
		draw_normal((oya + i) % 4);
	}
}

void Table::draw_normal(int i_player)
{
	players[i_player].hand.push_back(yama.back());
	gamelog.log_draw(i_player, yama.back(), false);
	yama.pop_back();
}

void Table::draw_n_normal(int i_player, int n_tiles)
{
	for (int i = 0; i < n_tiles; ++i) {
		draw_normal(i_player);
	}
}

/* 如果还有2/4张岭上牌，则摸倒数第2张（因为最后一张压在下面）*/
void Table::draw_rinshan(int i_player)
{
	new_dora(); // 先翻dora
	int n_kan = get_remain_kan_tile();
	auto iter = yama.begin();
	if (n_kan % 2 == 0) ++iter;
	players[i_player].hand.push_back(*iter);
	gamelog.log_draw(i_player, *iter, true);
	yama.erase(iter);
}

string Table::to_string() const
{
	stringstream ss;
	ss << "Yama: ";
	if (yama.size() < 14) {
		throw runtime_error("Error: Yama has less than 14 tiles.");
	}

	for (int i = 0; i < 14; ++i) {
		ss << yama[i]->to_string() << " ";
	}
	ss << "(Wanpai)| ";
	for (int i = 14; i < yama.size(); ++i) {
		ss << yama[i]->to_string() << " ";
	}
	ss << "\n";

	ss << "Dora Indicator(s):";
	for (int i = 0; i < n_active_dora; ++i) {
		ss << dora_indicator[i]->to_string() << " ";
	}
	ss << "\n";
	ss << "Remaining tiles: " << get_remain_tile() << "\n";
	for (int i = 0; i < 4; ++i)
		ss << "Player " << i << ": " << "\n" 
		   << players[i].to_string() << "\n";

	ss << "\n";
	ss << "Oya player " << oya << "\n";
	ss << "Honba: " << honba << "\n";
	ss << "Kyoutaku: " << kyoutaku << "\n";
	return ss.str();
}

vector<SelfAction> Table::_generate_self_actions()
{
	profiler _("Table.cpp/_generate_self_actions");
	vector<SelfAction> actions;
	auto& the_player = players[turn];
	
	merge_into(actions, the_player.get_kyushukyuhai());	
	merge_into(actions, the_player.get_discard(after_chipon()));
	
	// 吃/碰后，且已经4杠的场合，不能继续杠
	if (!after_chipon() && get_remain_kan_tile() > 0) {
		merge_into(actions, the_player.get_ankan());
		merge_into(actions, the_player.get_kakan());
	}
	merge_into(actions, the_player.get_tsumo(this));

	if (players[turn].score >= 1000 && get_remain_tile() >= 4)
		// 有1000点才能立直，否则不行
		// 牌河有4张以下牌，则不能立直
		merge_into(actions, the_player.get_riichi());

	sort(actions.begin(), actions.end());
	//actions.erase(unique(actions.begin(), actions.end(), action_unique_pred<SelfAction>));

	return actions;
}

vector<SelfAction> Table::_generate_riichi_self_actions()
{
	vector<SelfAction> actions;
	auto& the_player = players[turn];
	
	if (get_remain_kan_tile() > 0)
	{
		merge_into(actions, the_player.riichi_get_ankan());
	}
	merge_into(actions, the_player.riichi_get_discard());
	merge_into(actions, the_player.get_tsumo(this));

	sort(actions.begin(), actions.end());
	//actions.erase(unique(actions.begin(), actions.end(), action_unique_pred<SelfAction>));
	return actions;
}

vector<ResponseAction> Table::_generate_response_actions(
	int i, Tile* tile, bool is_next)
{
	profiler _("Table.cpp/_generate_response_actions");
	vector<ResponseAction> actions;
	
	// first: Pass action
	ResponseAction action_pass;
	action_pass.action = BaseAction::Pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];

	merge_into(actions, the_player.get_ron(this, tile));

	// 立直则不能鸣牌
	// 海底牌也不能鸣牌
	if (!the_player.is_riichi() && get_remain_tile() != 0) {
		merge_into(actions, the_player.get_pon(tile));
		if (get_remain_kan_tile() > 0)
			merge_into(actions, the_player.get_kan(tile));

		if (is_next) {
			merge_into(actions, the_player.get_chi(tile));
		}
	}

	sort(actions.begin(), actions.end());
	//actions.erase(unique(actions.begin(), actions.end(), action_unique_pred<ResponseAction>));
	return actions;
}

vector<ResponseAction> Table::_generate_chanankan_response_actions(int i, Tile *tile)
{
	vector<ResponseAction> actions;

	// first: Pass action
	ResponseAction action_pass;
	action_pass.action = BaseAction::Pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];
	merge_into(actions, the_player.get_chanankan(tile));

	return actions;
}

vector<ResponseAction> Table::_generate_chankan_response_actions(int i, Tile *tile)
{
	vector<ResponseAction> actions;

	// first: Pass action
	ResponseAction action_pass;
	action_pass.action = BaseAction::Pass;
	actions.push_back(action_pass);

	auto &the_player = players[i];
	merge_into(actions, the_player.get_chankan(tile));

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

void Table::_handle_response_action()
{
	// 见逃判断
	int i = phase - P1_RESPONSE;
	if (check_见逃(response_actions, selection)) {
		players[i].见逃();
	}	
	// 在0,1,2处理完之后，为下一个玩家生成对应的动作，并改变对应的phase
	if (i < 3)
	{
		i++; // for next player				
		if (i == turn) {
			ResponseAction ra;
			ra.action = BaseAction::Pass;
			response_actions = { ra };
		}
		else {
			// 对于所有其他人			
			bool is下家 = false;
			if (i == (turn + 1) % 4)
				is下家 = true;
			response_actions = _generate_response_actions(i, tile, is下家);
		}
		phase = PhaseEnum(phase + 1);
	}
}

void Table::_handle_response_chankan_action()
{
	// 见逃判断
	int i = phase - P1_CHANKAN_RESPONSE;
	if (check_见逃(response_actions, selection)) {
		players[i].见逃();
	}

	// 在0,1,2处理完之后，为下一个玩家生成对应的动作，并改变对应的phase
	if (i < 3)
	{
		i++; // for next player				
		if (i == turn) {
			ResponseAction ra;
			ra.action = BaseAction::Pass;
			response_actions = { ra };
		}
		else {
			// 对于所有其他人			
			bool is下家 = false;
			if (i == (turn + 1) % 4)
				is下家 = true;
			response_actions = _generate_chankan_response_actions(i, tile);
		}
		phase = PhaseEnum(phase + 1);
	}
}

void Table::_handle_response_chanankan_action()
{
	// 见逃判断
	int i = phase - P1_CHANANKAN_RESPONSE;
	if (check_见逃(response_actions, selection)) {
		players[i].见逃();
	}

	// 在0,1,2处理完之后，为下一个玩家生成对应的动作，并改变对应的phase
	if (i < 3)
	{
		i++; // for next player				
		if (i == turn) {
			ResponseAction ra;
			ra.action = BaseAction::Pass;
			response_actions = { ra };
		}
		else {
			// 对于所有其他人			
			bool is下家 = false;
			if (i == (turn + 1) % 4)
				is下家 = true;
			response_actions = _generate_chanankan_response_actions(i, tile);
		}
		phase = PhaseEnum(phase + 1);
	}
}

void Table::_handle_response_final_execution()
{
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
	case BaseAction::Pass:
		if (selected_action.action == BaseAction::Riichi) {
			// 立直成功
			if (players[turn].first_round) {
				players[turn].double_riichi = true;
			}
			players[turn].riichi = true;
			kyoutaku++;
			players[turn].score -= 1000;
			players[turn].ippatsu = true;

			/* log riichi success if no ron */
			gamelog.log_riichi_success(this);
		}

		// 消除第一巡
		players[turn].first_round = false;
		next_turn((turn + 1) % 4);
		last_action = selected_action.action;
		break;
	case BaseAction::Chi:
	case BaseAction::Pon:
	case BaseAction::Kan:

		if (selected_action.action == BaseAction::Riichi) {
			// 立直成功
			if (players[turn].first_round) {
				players[turn].double_riichi = true;
			}
			players[turn].riichi = true;
			kyoutaku++;
			players[turn].score -= 1000;
			// 立直即鸣牌，一定没有ippatsu

			/* log riichi success if no ron */
			gamelog.log_riichi_success(this);
		}

		players[turn].set_not_remained();

		players[response].execute_naki(
			actions[response].correspond_tiles, tile, (turn - response) % 4);

		gamelog.log_call(response, turn, tile, actions[response].correspond_tiles, final_action);

		// 这是鸣牌，消除所有人第一巡和ippatsu
		for (int i = 0; i < 4; ++i) {
			players[i].first_round = false;
			players[i].ippatsu = false;
		}

		// 切换turn
		next_turn(response);
		last_action = final_action;
		break;

	case BaseAction::Ron:
		/* 为每一个胡牌的玩家生成gamelog */
		for (int player : response_player)
		{
			gamelog.log_ron(player, turn, selected_action.correspond_tiles[0]);
		}
		result = generate_result_ron(this, selected_action.correspond_tiles[0], response_player);
		gamelog.log_gameover(result);
		phase = GAME_OVER;
		return;
	default:
		throw runtime_error("Invalid Selection.");
	}
}

void Table::_handle_response_final_chankan_execution()
{
	// 进行chankan结算	
	vector<int> response_player;
	for (int i = 0; i < 4; ++i) {
		if (actions[i].action == BaseAction::ChanKan) {
			response_player.push_back(i);
		}
	}

	// 要么有抢杠，要么是pass
	// 这里是有抢杠
	if (response_player.size() != 0) {
		// 有人抢杠则进行结算，除非加杠宣告成功，否则ippatsu状态仍然存在
		for (int player : response_player)
			gamelog.log_ron(player, turn, tile);
		result = generate_result_chankan(this, tile, response_player);
		gamelog.log_gameover(result);
		phase = GAME_OVER;
		return;
	}

	// 这里是全部pass
	players[turn].execute_kakan(tile);
	last_action = BaseAction::KaKan;
	gamelog.log_kakan(turn, tile);

	// 这是鸣牌，消除所有人第一巡和ippatsu
	for (int i = 0; i < 4; ++i) {
		players[i].first_round = false;
		players[i].ippatsu = false;
	}
	next_turn(turn);
}

void Table::_handle_response_final_chanankan_execution()
{
	// 进行chanankan结算	
	vector<int> response_player;
	for (int i = 0; i < 4; ++i) {
		if (actions[i].action == BaseAction::ChanAnKan) {
			response_player.push_back(i);
		}
	}

	// 要么有抢杠，要么是pass
	// 这里是有抢杠
	if (response_player.size() != 0) {
		// 有人抢暗杠则进行结算，已经不用管ippatsu了
		for (int player : response_player)
			gamelog.log_ron(player, turn, tile);
		result = generate_result_chanankan(this, tile, response_player);
		gamelog.log_gameover(result);
		phase = GAME_OVER;
		return;
	}
	players[turn].execute_ankan(tile->tile);
	last_action = BaseAction::AnKan;
	gamelog.log_ankan(turn, selected_action.correspond_tiles);

	// 这是暗杠，消除所有人第一巡和ippatsu
	for (int i = 0; i < 4; ++i) {
		players[i].first_round = false;
		players[i].ippatsu = false;
	}
	next_turn(turn);
}

void Table::_handle_self_action()
{
	switch (selected_action.action) {
	case BaseAction::Kyushukyuhai:
		gamelog.log_kyushukyuhai(turn, result);
		result = generate_result_9hai(this);
		gamelog.log_gameover(result);
		phase = GAME_OVER;
		return;
	case BaseAction::Tsumo:
		gamelog.log_tsumo(turn);
		result = generate_result_tsumo(this);
		gamelog.log_gameover(result);
		phase = GAME_OVER;
		return;
	case BaseAction::Discard:
	case BaseAction::Riichi:
	{
		// 决定不胡牌，则不具有ippatsu状态
		players[turn].ippatsu = false;

		tile = selected_action.correspond_tiles[0];
		// 等待回复

		// 大部分情况都是手切, 除了上一步动作为 出牌 加杠 暗杠
		// 并且判定抉择弃牌是不是最后一张牌

		bool is_from_hand = DiscardFromHand;
		if (last_action == BaseAction::Discard ||
			last_action == BaseAction::KaKan ||
			last_action == BaseAction::AnKan) {
			// tile是不是最后一张
			if (tile == players[turn].hand.back())
				is_from_hand = DiscardFromTsumo;
		}
		players[turn].execute_discard(tile, river_counter, selected_action.action == BaseAction::Riichi, is_from_hand);
		
		/* Log discard before any response */
		if (selected_action.action == BaseAction::Discard)
			gamelog.log_discard(turn, tile, is_from_hand);
		else if (selected_action.action == BaseAction::Riichi)
			gamelog.log_riichi_discard(turn, tile, is_from_hand);

		phase = P1_RESPONSE;
		if (0 == turn) {
			ResponseAction ra;
			ra.action = BaseAction::Pass;
			response_actions = { ra };
		}
		else {
			// 对于所有其他人
			bool is_next = false;
			if (0 == (turn + 1) % 4)
				is_next = true;
			response_actions = _generate_response_actions(0, tile, is_next);
		}
		return;
	}
	case BaseAction::KaKan:
	{
		tile = selected_action.correspond_tiles[0];

		/* log kakan before response*/
		gamelog.log_kakan(turn, tile);

		// 第一巡消除
		players[turn].first_round = false;
		// 等待回复
		phase = P1_CHANKAN_RESPONSE;
		if (0 == turn) {
			ResponseAction ra;
			ra.action = BaseAction::Pass;
			response_actions = { ra };
		}
		else {
			response_actions = _generate_chankan_response_actions(0, tile);
		}
		return;
	}
	case BaseAction::AnKan:
	{
		tile = selected_action.correspond_tiles[0];

		/* log kakan before response*/
		gamelog.log_ankan(turn, selected_action.correspond_tiles);

		// 第一巡消除
		players[turn].first_round = false;
		// 等待回复
		phase = P1_CHANANKAN_RESPONSE;
		if (turn == 0) {
			ResponseAction ra;
			ra.action = BaseAction::Pass;
			response_actions = { ra };
		}
		else {
			response_actions = _generate_chanankan_response_actions(0, tile);
		}

		return;
	}
	default:
		throw runtime_error("Error base action in selection.");
	}
}

void Table::make_selection(int selection_)
{
	profiler _("Table.cpp/make_selection");

	selection = selection_;
	// 这个地方控制了游戏流转
	debug_selection_record();

	// handle the "selection" variable
	// if self action, then assign this->selected_action
	// if response, then push_back this->actions
	_check_selection();

	// 分为两种情况，如果是ACTION阶段
	switch (phase) {
	case GAME_OVER:
		return;

		// Self action 阶段，做出抉择后自动结算 (tsumo, kyushukyuhai) 或者
		// P1_RESPONSE (discard, riichi)
		// P1_CHANKAN_RESPONSE (kakan)
		// P1_CHANANKAN_RESPONSE (ankan) 阶段
	case P1_ACTION:
	case P2_ACTION:
	case P3_ACTION:
	case P4_ACTION:
		_handle_self_action();

		if (phase != GAME_OVER)
		{
			/* ready for response/chankan_response/chanankan_response */
			actions.resize(0);
			final_action = BaseAction::Pass;
		}
		return;

	// P1 P2 P3依次做出抉择，推入actions，并且为下一位玩家生成抉择，改变phase
	case P1_RESPONSE:
	case P2_RESPONSE:
	case P3_RESPONSE:
		// 收回每个人的response，并生成下一个玩家的response
		_handle_response_action();
		return;
	case P4_RESPONSE:
		_handle_response_action();

		// 根据每个人的response，结算最终的response
		_handle_response_final_execution();
		// 回到循环的最开始
		from_beginning();
		return;

	case P1_CHANKAN_RESPONSE:
	case P2_CHANKAN_RESPONSE:
	case P3_CHANKAN_RESPONSE:
		// 收回每个人的response，并生成下一个玩家的response
		_handle_response_chankan_action();
		return;
	case P4_CHANKAN_RESPONSE: {
		_handle_response_chankan_action();

		// 根据每个人的response，结算最终的response
		_handle_response_final_chankan_execution();
		// 回到循环的最开始
		from_beginning();
		return;
	}

	case P1_CHANANKAN_RESPONSE:
	case P2_CHANANKAN_RESPONSE:
	case P3_CHANANKAN_RESPONSE:
		// 收回每个人的response，并生成下一个玩家的response
		_handle_response_chanankan_action();
		return;
	case P4_CHANANKAN_RESPONSE: {
		_handle_response_chanankan_action();

		// 根据每个人的response，结算最终的response
		_handle_response_final_chanankan_execution();
		// 回到循环的最开始
		from_beginning();
		return;
	}
	}
}

void Table::_check_selection()
{
	switch (phase)
	{
	case P1_ACTION:
	case P2_ACTION:
	case P3_ACTION:
	case P4_ACTION:
		if (self_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}
		if (selection >= self_actions.size())
		{
			throw runtime_error(
				fmt::format("Selection overflows. (Executing {} while size is {})", selection, self_actions.size())
			);
		}
		selected_action = self_actions[selection];
		return;

	case P1_RESPONSE:
	case P2_RESPONSE:
	case P3_RESPONSE:
	case P4_RESPONSE:
	case P1_CHANKAN_RESPONSE:
	case P2_CHANKAN_RESPONSE:
	case P3_CHANKAN_RESPONSE:
	case P4_CHANKAN_RESPONSE:
	case P1_CHANANKAN_RESPONSE:
	case P2_CHANANKAN_RESPONSE:
	case P3_CHANANKAN_RESPONSE:
	case P4_CHANANKAN_RESPONSE:

		if (response_actions.size() == 0) {
			throw runtime_error("Empty Selection Lists.");
		}
		if (selection >= response_actions.size())
		{
			throw runtime_error(
				fmt::format("Selection overflows. (Executing {} while size is {})", selection, response_actions.size())
			);
		}
		actions.push_back(response_actions[selection]);
		
		// 从actions中获得优先级
		if (response_actions[selection].action > final_action)
			final_action = response_actions[selection].action;

		return;
	case GAME_OVER:
		return;
	}
}
namespace_mahjong_end

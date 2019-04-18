#include "Agent.h"

using namespace std;

int RealPlayer::get_self_action(Table * status, std::vector<SelfAction> actions)
{
	status->test_show_all();
	cout << endl; cout << "Select:" << endl;
	int i = 0;

	for (auto action : actions) {
		cout << i << " " << action.to_string() << endl;
		++i;
	}
	int selection;
	cin >> selection;
	return selection;
}

int RealPlayer::get_response_action(Table * status, SelfAction action, Tile* tile, std::vector<ResponseAction> actions)
{
	//status->test_show_all();
	
	cout << endl; 
	cout << "You are player " << i_player << "." << endl;
	cout << "Player " << status->turn;
	switch (action.action) {
	case Action::立直:
		cout << " calls riichi and plays ";
		break;
	case Action::出牌:
		cout << " plays ";
		break;
	case Action::暗杠:
		cout << " 暗杠 ";
		break;
	case Action::加杠:
		cout << " 加杠 ";
		break;
	default:
		throw runtime_error("Unknown action.");
	}
	cout<< tile->to_string() << endl;
	
	cout << "Select:" << endl;
	int i = 0;
	for (auto action : actions) {
		cout << i << " " << action.to_string() << endl;
		++i;
	}
	int selection;
	cin >> selection;
	return selection;
}

#include <random>

int RandomPlayer::get_self_action(Table * status, std::vector<SelfAction> actions)
{
	for (int i = 0; i < actions.size(); ++i) {
		if (actions[i].action == Action::自摸)
			return i;
		if (actions[i].action == Action::立直)
			return i;
		if (actions[i].action == Action::九种九牌)
			return i;
	}
	std::default_random_engine generator;
	std::uniform_int_distribution<int> distribution(0, actions.size() - 1);
	int dice_roll = distribution(generator);  // generates number in the range 1..6 
	return dice_roll;
}

int RandomPlayer::get_response_action(Table * status, SelfAction action, Tile *, std::vector<ResponseAction> actions)
{
	for (int i = 0; i < actions.size(); ++i) {
		if (actions[i].action == Action::荣和)
			return i;
	}
	std::default_random_engine generator;
	std::uniform_int_distribution<int> distribution(0, actions.size() - 1);
	int dice_roll = distribution(generator);  // generates number in the range 1..6 
	return dice_roll;
}

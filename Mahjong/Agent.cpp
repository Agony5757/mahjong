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

#include "Agent.h"

using namespace std;

int RealPlayer::get_self_action(Table * status, std::vector<SelfAction> actions)
{
	status->test_show_all();
	cout << endl; cout << "Select:" << endl;
	for (auto action : actions) {
		cout << action.to_string() << endl;
	}
	int selection;
	cin >> selection;
	return selection;
}

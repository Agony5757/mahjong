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

int RealPlayer::get_response_action(Table * status, std::vector<ResponseAction> actions)
{
	// 只有pass的情况
	if (actions.size() == 1)
		return 0;

	for (auto action : actions) {
		cout << action.to_string() << endl;
	}
}

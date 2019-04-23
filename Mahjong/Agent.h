#ifndef AGENT_H
#define AGENT_H

#include "Action.h"
#include "Table.h"
// abstract class of Agent

// For Action Phase
// Agent gets the std::vector<SelfAction> as input,
// outputs its choice (in integer);

// For Response Phase
// Agent gets the std::vector<ResponseAction> as input,
// outputs its choice (in integer)

// Except the choice, agent could get all informations
// from the table if needed. This is a struct called
// TableStatus.


// Forward Decl
class Table;

enum LogMode : int {
	SELF_ACTION = 1 << 1,
	TABLE_STATUS = 1 << 2,
	RESPONSE_ACTION = 1 << 3,
	OTHER_PLAYER_ACTION = 1 << 4,
	ALL = ((1 << 5) - 1),
};

// Abstract base class
class Agent {
public:
	virtual inline int get_self_action(Table* table, std::vector<SelfAction> actions) {
		return 0;
	}
	
	virtual inline int get_response_action(Table*, SelfAction action, Tile*, std::vector<ResponseAction> actions) {
		return 0;
	}
};

class RealPlayer : public Agent {
public:
	int i_player; // player number
	inline RealPlayer(int i) :i_player(i) {}
	int get_self_action(Table* status, std::vector<SelfAction> actions);
	int get_response_action(Table* status, SelfAction action, Tile*, std::vector<ResponseAction> actions);
};

class RandomPlayer : public Agent {
public:
	int i_player; // player number
	std::stringstream &ss;
	int mode;
	inline RandomPlayer(int i, std::stringstream &ss_, 
		int mode_ = 0) 
		:i_player(i), ss(ss_), mode(mode_) {}
	int get_self_action(Table* status, std::vector<SelfAction> actions);
	int get_response_action(Table* status, SelfAction action, Tile*, std::vector<ResponseAction> actions);
};

extern int extern_get_self_action(int i_player, Table* table, std::vector<SelfAction> actions);
extern int extern_get_response_action(int i_player, Table* status, SelfAction action, Tile*, std::vector<ResponseAction> actions);

class ExternPlayer : public Agent {
public:
	int i_player; // player number
	inline ExternPlayer(int i) :i_player(i) {}
	inline int get_self_action(Table* status, std::vector<SelfAction> actions) {
		return extern_get_self_action(i_player, status, actions);
	}
	inline int get_response_action(Table* status, SelfAction action, Tile* tile, std::vector<ResponseAction> actions) {
		return extern_get_response_action(i_player, status, action, tile, actions);
	}
};

#include <Python.h>

class DeepLearningAI : public Agent {
public:
	int i_player;
	static PyObject* test_module;
	static PyObject* dict;
	static PyObject* MahjongLearnerClass;
	PyObject* MahjongLearnerObj;
	inline DeepLearningAI(int i) : i_player(i) {
		if (!Py_IsInitialized())
			Py_Initialize();

		

		if (!test_module)
			test_module = PyImport_ImportModule("test.py");

		if (!dict)
			dict = PyModule_GetDict(test_module);

		if (!MahjongLearnerClass)
			MahjongLearnerClass = PyDict_GetItemString(dict, "MahjongLearner");

		MahjongLearnerObj = PyInstanceMethod_New(MahjongLearnerClass);
	}
	int get_self_action(Table* status, std::vector<SelfAction> actions);
	int get_response_action(Table* status, SelfAction action, Tile* tile, std::vector<ResponseAction> actions);
	~DeepLearningAI() {
		if (Py_IsInitialized())
			Py_Finalize();
	}
	void GameOver(int score);
};

#endif
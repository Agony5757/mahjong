#ifndef ACTION_H
#define ACTION_H

#include "Tile.h"
#include "fmt/core.h"

namespace_mahjong

enum class BaseAction : uint8_t {
	// response begin
	pass,
	吃, 
	碰,
	杠,
	荣和,
	// response end
	// 注意到所有的response Action可以通过大小来比较

	抢暗杠,
	抢杠,

	// self action begin
	暗杠,
	加杠,
	出牌,
	立直,
	自摸,
	九种九牌,
	// self action end
};

struct Action
{
	Action() = default;
	Action(BaseAction action, std::vector<Tile*>);
	BaseAction action = BaseAction::pass;

	/* 关于corresponding_tile的约定
	pass: empty (size=0)
	吃/碰: 手牌中2张牌 (size=2)
	杠: 手牌中2张牌 (size=3)
	荣/抢杠/抢暗杠: 荣到的那1张牌 (size=1)

	暗杠: 手牌中的4张牌 (size=4)
	加杠: 手牌中的1张牌 (size=1)
	出牌/立直: 手牌中的1张牌 (size=2)	
	自摸: empty (size=0)
	九种九牌: 能推的N种九牌，每种各一张 (size>=9)

	所有的corresponding_tile默认是排序的，否则判断吃牌会出现一定的问题
	*/
	std::vector<Tile*> correspond_tiles;
	std::string to_string() const;
    bool operator==(const Action& other) const;
	bool operator<(const Action& other) const;	
};

template<typename ActionType>
bool action_unique_pred(const ActionType& action1, const ActionType& action2)
{
	static_assert(std::is_base_of<Action, ActionType>::value, "Bad ActionType.");
	if (action1.action != action2.action) 
		return false;
	if (action1.correspond_tiles.size() != action2.correspond_tiles.size())
		return false;
	for (size_t i = 0; i < action1.correspond_tiles.size(); ++i) {
		if (action1.correspond_tiles[i]->red_dora ^ action2.correspond_tiles[i]->red_dora) {
			return false;
		}
		if (action1.correspond_tiles[i]->tile != action2.correspond_tiles[i]->tile) {
			return false;
		}
	}
	return true;
}

struct SelfAction : public Action
{
	SelfAction() = default;
	SelfAction(BaseAction, std::vector<Tile*>);
    bool operator==(const SelfAction& other) const;
};

struct ResponseAction : public Action
{
	ResponseAction() = default;
	ResponseAction(BaseAction, std::vector<Tile*>);
    bool operator==(const ResponseAction& other) const;
};


template<typename ActionType>
int get_action_index(const std::vector<ActionType> &actions, BaseAction action_type, std::vector<Tile*> correspond_tiles)
{

	if (action_type == BaseAction::九种九牌 ||
		action_type == BaseAction::荣和 ||
		action_type == BaseAction::抢杠 ||
		action_type == BaseAction::抢暗杠) {
		for (int i = 0; i < actions.size(); ++i) {
			if (actions[i].action == action_type)
				return i;
		}
		return -1;
	}
	else {	
		auto iter = std::find(actions.begin(), actions.end(), ActionType{action_type, correspond_tiles});
		if (iter == actions.end())
			return -1;
		else 
			return iter - actions.begin();
	}	
}

template<typename ActionType>
int get_action_index(const std::vector<ActionType> &actions, BaseAction action_type, std::vector<BaseTile> correspond_tiles, bool use_red_dora)
{
	static_assert(std::is_base_of<Action, ActionType>::value, "Bad ActionType.");

	// assume actions vector is sorted.
	if (action_type == BaseAction::九种九牌 ||
	    action_type == BaseAction::荣和 || 
		action_type == BaseAction::抢杠 || 
		action_type == BaseAction::抢暗杠) {
		for (int i = 0; i < actions.size(); ++i) {
			if (actions[i].action == action_type)
				return i;
		}
		return -1;
	}

	if (use_red_dora) {
		// 带有红宝牌的操作一定会先于不带的出现
		for (auto iter = actions.begin(); iter != actions.end(); ++iter) {
			if (iter->action == action_type &&
				iter->correspond_tiles.size() == correspond_tiles.size())
			{
				bool match = true;
				for (size_t i = 0; i < iter->correspond_tiles.size();++i) {
					if (iter->correspond_tiles[i]->tile != correspond_tiles[i]) {
						match = false;
						break;
					}
				}
				if (match) return iter - actions.begin();
			}
		}
	}
	else {
		// 不用红宝牌的话就倒序找第一个
		for (auto iter = actions.rbegin(); iter != actions.rend(); ++iter) {
			if (iter->action == action_type &&
				iter->correspond_tiles.size() == correspond_tiles.size())
			{
				bool match = true;
				for (size_t i = 0; i < iter->correspond_tiles.size();++i) {
					if (iter->correspond_tiles[i]->tile != correspond_tiles[i]) {
						match = false;
						break;
					}
				}
				if (match) return actions.size() - 1 - (iter - actions.rbegin());
			}
		}
	}
	return -1;
}

namespace_mahjong_end

#endif
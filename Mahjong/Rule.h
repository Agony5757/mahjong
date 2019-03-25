#ifndef RULE_H
#define RULE_H

#include "Table.h"

// 和牌型包括了无役的情况，这是必要不充分条件，并且不需要满足有14张的条件
// 这是去掉副露，留下手牌的判断
bool isCommon和牌型(std::vector<Tile*>);

#endif
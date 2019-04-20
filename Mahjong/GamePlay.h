#ifndef GAMEPLAY_H
#define GAMEPLAY_H

#include "Table.h"
#include <array>
std::array<int, 4> 东风局(std::array<Agent*, 4> agents, std::stringstream&);

std::array<int, 4> 南风局(std::array<Agent*, 4> agents, std::stringstream&);

std::array<int, 4> FullGame(Wind, std::array<Agent*, 4> agents, std::stringstream&);

#endif
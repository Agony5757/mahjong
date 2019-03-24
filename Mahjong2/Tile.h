#pragma once
#include <memory>
#include <vector>
#include <unordered_map>
#include <string>
#include <iostream>
#include <sstream>
#include <exception>
#include <algorithm>
#include <stdlib.h>
#include <time.h>

enum Wind {
	East = 1, South, West, North
};

enum class Belong : uint8_t {
	p1手, p1河,
	p2手, p2河,
	p3手, p3河,
	p4手, p4河,
	yama,
};

enum BaseTile {
	_1m, _2m, _3m, _4m, _5m, _6m, _7m, _8m, _9m,
	_1s, _2s, _3s, _4s, _5s, _6s, _7s, _8s, _9s,
	_1p, _2p, _3p, _4p, _5p, _6p, _7p, _8p, _9p,
	east, south, west, north,
	白, 发, 中
};

class Tile {
public:
	BaseTile tile;
	bool red_dora;
	Belong belongs;
	inline std::string to_string() {
		std::string ret;
		if (0 <= tile && tile <= 8) {
			ret = "[" + std::to_string(static_cast<int>(tile) + 1) + "m";
		}
		else if (9 <= tile && tile <= 17) {
			ret = "[" + std::to_string(static_cast<int>(tile) - 8) + "s";
		}
		else if (18 <= tile && tile <= 26) {
			ret = "[" + std::to_string(static_cast<int>(tile) - 17) + "p";
		}
		else if (tile == east) {
			ret = "[东";
		}
		else if (tile == south) {
			ret = "[南";
		}
		else if (tile == west) {
			ret = "[西";
		}
		else if (tile == north) {
			ret = "[北";
		}
		else if (tile == 白) {
			ret = "[白";
		}
		else if (tile == 发) {
			ret = "[发";
		}
		else if (tile == 中) {
			ret = "[中";
		}
		else throw std::runtime_error("unknown tile");

		if (red_dora) {
			ret += '*';
		}
		return ret + ']';
	}
};

inline bool tile_comparator(Tile* t2, Tile* t1) {
	if (t1->tile > t2->tile) {
		return true;
	}
	else if (t1->tile < t2->tile) {
		return false;
	}
	else {
		return t1 > t2;
	}
}

inline std::string tiles_to_string(std::vector<Tile*> tiles) {
	std::stringstream ss;
	for (auto tile : tiles) {
		ss << tile->to_string();
	}
	return ss.str();
}

inline std::string 副露_to_string(Tile* head, std::vector<Tile*> fulu) {
	std::stringstream ss;
	ss << "[" << head->to_string() << "]";
	ss << tiles_to_string(fulu);
	return ss.str();
}

inline std::string wind_to_string(Wind wind) {
	switch (wind) {
	case Wind::East:
		return "东";
	case Wind::South:
		return "南";
	case Wind::West:
		return "西";
	case Wind::North:
		return "北";
	default:
		return "??";
	}
}
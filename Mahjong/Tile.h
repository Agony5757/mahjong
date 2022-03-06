#ifndef TILE_H
#define TILE_H

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
#include "fmt/core.h"

// #define MAJ_DEBUG

enum Wind {
	East, South, West, North
};

enum BaseTile {
	_1m, _2m, _3m, _4m, _5m, _6m, _7m, _8m, _9m,
	_1p, _2p, _3p, _4p, _5p, _6p, _7p, _8p, _9p,
	_1s, _2s, _3s, _4s, _5s, _6s, _7s, _8s, _9s,
	_1z, _2z, _3z, _4z,	_5z, _6z, _7z
};

inline std::string basetile_to_string(BaseTile bt) {
	using namespace std;
	static vector<string> names{
		"1m","2m","3m","4m","5m","6m","7m","8m","9m",
		"1p","2p","3p","4p","5p","6p","7p","8p","9p",
		"1s","2s","3s","4s","5s","6s","7s","8s","9s",	
		"1z","2z","3z","4z","5z","6z","7z" 
	};
	return names[char(bt)];
}

inline BaseTile char2_to_basetile(char number, char color, bool& red_dora) {
	int num = number - '0';
	red_dora = false;
	if (num == 0) {
		red_dora = true;
		num = 5;
	}
	if (color == 'm') {
		return BaseTile(_1m + num - 1);
	}
	if (color == 'p') {
		return BaseTile(_1p + num - 1);
	}
	if (color == 's') {
		return BaseTile(_1s + num - 1);
	}	
	if (color == 'z') {
		return BaseTile(_1z + num - 1);
	}
	throw std::runtime_error("Bad tile string.");
}

inline BaseTile get_dora_next(BaseTile tile) {
	switch (tile) {
	case _9m: return _1m;
	case _9s: return _1s;
	case _9p: return _1p;
	case _4z: return _1z;
	case _7z: return _5z;
	default:  return static_cast<BaseTile>((int)tile + 1);
	}
}

inline bool is_1hai(BaseTile t) {
	if (t == _1m || t == _1p || t == _1s ) {
		return true;
	}
	else return false;
}

inline bool is_9hai(BaseTile t) {
	if (t == _9m || t == _9p || t == _9s ) {
		return true;
	}
	else return false;
}

inline bool is_19hai(BaseTile t) {
	if (is_9hai(t) || is_1hai(t)) {
		return true;
	} 
	else return false;
}

inline bool is_tsuhai(BaseTile t) {
	if (t >= BaseTile::_1z && t<= BaseTile::_7z) {
		return true;
	}
	else return false;
}

inline bool is_yaochuhai(BaseTile t) {
	if (is_19hai(t) || is_tsuhai(t)) {
		return true;
	}
	else return false;
}

inline bool is_shuntsu(std::vector<BaseTile> tiles) {
	if (tiles.size() != 3) return false;
	std::sort(tiles.begin(), tiles.end());

	if (tiles[1] - tiles[0] != 1) return false;
	if (tiles[2] - tiles[1] != 1) return false;
	
	if (tiles[2] == _1p) return false;
	if (tiles[2] == _2p) return false;
	if (tiles[2] == _1s) return false;
	if (tiles[2] == _2s) return false;
	if (tiles[2] >= _1z) return false;

	return true;
}

inline bool is_koutsu(std::vector<BaseTile> tiles) {
	if (tiles.size() != 3) return false;

	if (tiles[1] - tiles[0] != 0) return false;
	if (tiles[2] - tiles[1] != 0) return false;
	
	return true;
}

inline bool is_kantsu(std::vector<BaseTile> tiles) {
	if (tiles.size() != 4) return false;

	if (tiles[1] - tiles[0] != 0) return false;
	if (tiles[2] - tiles[1] != 0) return false;
	if (tiles[3] - tiles[2] != 0) return false;

	return true;
}

inline bool is_wind_match(BaseTile tile, Wind 场风) {
	switch (场风) {
	case Wind::East:
		return tile == BaseTile::_1z;
	case Wind::South:
		return tile == BaseTile::_2z;
	case Wind::West:
		return tile == BaseTile::_3z;
	case Wind::North:
		return tile == BaseTile::_4z;
	default:
		throw std::runtime_error("Unknown wind.");
	}
}

inline bool is_567z(BaseTile tile) {
	return (tile == BaseTile::_7z || tile == BaseTile::_6z || tile == BaseTile::_5z);
}
	
inline bool is_yakuhai(BaseTile tile, Wind game_wind, Wind self_wind) {
	if (is_wind_match(tile, game_wind)) {
		return true;
	}
	if (is_wind_match(tile, self_wind)) {
		return true;
	}
	if (is_567z(tile)) {
		return true;
	}
	return false;
}

class Tile {
public:
	BaseTile tile;
	bool red_dora;
	int id;

	inline std::string to_string() const {
		std::stringstream ss;
		int number = tile % 9 + 1;
		if (red_dora)
			number = 0;
		switch (tile / 9) {
		case 0:
			ss << number << "m";
			return ss.str();
		case 1:
			ss << number << "p";
			return ss.str();
		case 2:
			ss << number << "s";
			return ss.str();
		case 3:
			ss << number << "z";
			return ss.str();
		}
		throw std::runtime_error("Error Tile.");
	}
};

inline std::string tiles_to_string(std::vector<Tile*> tiles) {
	std::stringstream ss;
	for (auto tile : tiles) {
		ss << tile->to_string();
	}
	return ss.str();
}

inline std::string 副露_to_string(Tile* head, std::vector<Tile*> CallGroup) {
	std::stringstream ss;
	ss << "[" << head->to_string() << "]";
	ss << tiles_to_string(CallGroup);
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

struct CallGroup {
	enum Type {
		Chi,
		Pon,
		DaiMinKan,
		KaKan,
		AnKan,
	};
	std::vector<Tile*> tiles;
	int take = 0;
	// take == 0 stands for (1)23
	// take == 1 stands for 1(2)3
	// take == 2 stands for 12(3)

	Type type;
	inline std::string to_string() const {
		std::string ret;
		switch (type) {
		case Chi:
		case Pon:
		case DaiMinKan:
			for (int i = 0; i < 3; ++i) {
				if (i == take) ret += fmt::format("({})", tiles[i]->to_string());
				else ret += tiles[i]->to_string();
			}
			return ret;
		case KaKan:
			for (int i = 0; i < 4; ++i) {
				if (i == take && i == 4) ret += fmt::format("({})", tiles[i]->to_string());
				else ret += tiles[i]->to_string();
			}
			return ret;
		case AnKan:
			for (int i = 0; i < 4; ++i) {
				if (i == 0 || i == 3) ret += tiles[i]->to_string();
				else ret += "*";
			}
			return ret;
		default:
			throw std::runtime_error("Bad call group (fuuro) type.");
		}
	}
};

#endif
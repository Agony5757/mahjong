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

// #define MAJ_DEBUG

enum Wind {
	East = 1, South, West, North
};

enum BaseTile : unsigned char {
	_1m, _2m, _3m, _4m, _5m, _6m, _7m, _8m, _9m,
	_1p, _2p, _3p, _4p, _5p, _6p, _7p, _8p, _9p,
	_1s, _2s, _3s, _4s, _5s, _6s, _7s, _8s, _9s,
	_1z, _2z, _3z, _4z,	_5z, _6z, _7z
};

inline std::string basetile_to_string_simple(BaseTile bt) {
	using namespace std;
	static vector<string> names{
		"1m","2m","3m","4m","5m","6m","7m","8m","9m",
		"1p","2p","3p","4p","5p","6p","7p","8p","9p",
		"1s","2s","3s","4s","5s","6s","7s","8s","9s",	
		"1z","2z","3z","4z","5z","6z","7z" 
	};
	return names[int(bt)];
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
	throw std::runtime_error("Unknown Tile String");
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

inline bool is_幺牌(BaseTile t) {
	if (t == _1m || t == _1p || t == _1s ) {
		return true;
	}
	else return false;
}

inline bool is_九牌(BaseTile t) {
	if (t == _9m || t == _9p || t == _9s ) {
		return true;
	}
	else return false;
}

inline bool is_老头牌(BaseTile t) {
	if (is_九牌(t) || is_幺牌(t)) {
		return true;
	} 
	else return false;
}

inline bool is_字牌(BaseTile t) {
	if (t >= BaseTile::_1z && t<= BaseTile::_7z) {
		return true;
	}
	else return false;
}

inline bool is_幺九牌(BaseTile t) {
	if (is_老头牌(t) || is_字牌(t)) {
		return true;
	}
	else return false;
}

inline bool is_顺子(std::vector<BaseTile> tiles) {
	if (tiles.size() != 3) return false;
	std::sort(tiles.begin(), tiles.end());

	if (tiles[1] - tiles[0] != 1) return false;
	if (tiles[2] - tiles[1] != 1) return false;
	// 必须成顺子
	
	if (tiles[2] == _1p) return false;
	if (tiles[2] == _2p) return false;
	if (tiles[2] == _1s) return false;
	if (tiles[2] == _2s) return false;
	if (tiles[2] >= _1z) return false;

	return true;
}

inline bool is_刻子(std::vector<BaseTile> tiles) {
	if (tiles.size() != 3) return false;

	if (tiles[1] - tiles[0] != 0) return false;
	if (tiles[2] - tiles[1] != 0) return false;
	// 必须都相同
	
	return true;
}

inline bool is_杠(std::vector<BaseTile> tiles) {
	if (tiles.size() != 4) return false;

	if (tiles[1] - tiles[0] != 0) return false;
	if (tiles[2] - tiles[1] != 0) return false;
	if (tiles[3] - tiles[2] != 0) return false;
	// 必须都相同

	return true;
}

inline bool is_场自风(BaseTile tile, Wind 场风) {
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

//inline bool is_自风(BaseTile tile, Wind 自风) {
//	switch (自风) {
//	case Wind::East:
//		return tile == BaseTile::_1z;
//	case Wind::West:
//		return tile == BaseTile::_3z;
//	case Wind::South:
//		return tile == BaseTile::_2z;
//	case Wind::North:
//		return tile == BaseTile::_4z;
//	default:
//		throw std::runtime_error("Unknown wind.");
//	}
//}

inline bool is_三元牌(BaseTile tile) {
	return (tile == BaseTile::_7z || tile == BaseTile::_6z || tile == BaseTile::_5z);
}
	
inline bool is_役牌(BaseTile tile, Wind 场风, Wind 自风) {
	if (is_场自风(tile, 场风)) {
		return true;
	}
	if (is_场自风(tile, 自风)) {
		return true;
	}
	if (is_三元牌(tile)) {
		return true;
	}
	return false;
}

inline std::string basetile_to_string(BaseTile tile) {
	std::string ret;
	if (0 <= tile && tile <= 8) {
		ret = "[" + std::to_string(static_cast<int>(tile) + 1) + "m";
	}
	else if (9 <= tile && tile <= 17) {
		ret = "[" + std::to_string(static_cast<int>(tile) - 8) + "p";
	}
	else if (18 <= tile && tile <= 26) {
		ret = "[" + std::to_string(static_cast<int>(tile) - 17) + "s";
	}
	else if (tile == _1z) {
		ret = "[东";
	}
	else if (tile == _2z) {
		ret = "[南";
	}
	else if (tile == _3z) {
		ret = "[西";
	}
	else if (tile == _4z) {
		ret = "[北";
	}
	else if (tile == _5z) {
		ret = "[白";
	}
	else if (tile == _6z) {
		ret = "[发";
	}
	else if (tile == _7z) {
		ret = "[中";
	}
	else throw std::runtime_error("unknown tile");
	return ret + ']';
}

class Tile {
public:
	BaseTile tile;
	bool red_dora;
	int id;

	inline std::string to_simple_string() const {
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

	inline std::string to_string() const {
		std::string ret;
		if (0 <= tile && tile <= 8) {
			ret = "[" + std::to_string(static_cast<int>(tile) + 1) + "m";
		}
		else if (9 <= tile && tile <= 17) {
			ret = "[" + std::to_string(static_cast<int>(tile) - 8) + "p";
		}
		else if (18 <= tile && tile <= 26) {
			ret = "[" + std::to_string(static_cast<int>(tile) - 17) + "s";
		}
		else if (tile == _1z) {
			ret = "[东";
		}
		else if (tile == _2z) {
			ret = "[南";
		}
		else if (tile == _3z) {
			ret = "[西";
		}
		else if (tile == _4z) {
			ret = "[北";
		}
		else if (tile == _5z) {
			ret = "[白";
		}
		else if (tile == _6z) {
			ret = "[发";
		}
		else if (tile == _7z) {
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

struct Fulu {
	enum Type {
		Chi,
		Pon,
		大明杠,
		加杠,
		暗杠,
	};
	std::vector<Tile*> tiles;
	int take;
	// take标记的tiles中第几张牌拿的是别人的
	// take == 0 说明 (1)23
	// take == 1 说明 1(2)3
	// take == 2 说明 12(3)
	// take在type==Chi的时候才有效，其他时候不用

	Type type;
	inline std::string to_string() const {
		std::stringstream ss;
		switch (type) {
		case Chi: {
			for (int i = 0; i < 3; ++i) {
				if (i == take) {
					ss << "(" << tiles[i]->to_string() << ")";
				}
				else {
					ss << tiles[i]->to_string();
				}
			}
			break;
		}
		case Pon: {
			for (int i = 0; i < 3; ++i) {
				if (i == 1) {
					ss << "(" << tiles[i]->to_string() << ")";
				}
				else {
					ss << tiles[i]->to_string();
				}
			}
			break;
		}
		case 大明杠: {
			for (int i = 0; i < 4; ++i) {
				if (i < 1) {
					ss << "(" << tiles[i]->to_string() << ")";
				}
				else {
					ss << tiles[i]->to_string();
				}
			}
			break;
		}
		case 加杠: {
			for (int i = 0; i < 4; ++i) {
				if (i < 2) {
					ss << "(" << tiles[i]->to_string() << ")";
				}
				else {
					ss << tiles[i]->to_string();
				}
			}
			break;
		}
		case 暗杠: {
			for (int i = 0; i < 4; ++i) {
				if (i == 0 || i == 3) {
					ss << tiles[i]->to_string();
				}
				else {
					ss << "[?]";
				}
			}
			break;
		}
		}
		return ss.str();
	}
};

#endif
#ifndef MACRO_H
#define MACRO_H

#include <vector>
#include <algorithm>
#include <type_traits>
#include <string>
#include <array>
#include "Tile.h"
#include "Profiler.h"

namespace_mahjong

constexpr bool FROM_摸切 = false;
constexpr bool FROM_手切 = true;

template<typename ContainerType, typename ElemType>
bool is_in(const ContainerType &container, const ElemType &elem){
	if (std::find(std::begin(container), std::end(container), elem) != std::end(container)) {
		return true;
	}
	else return false;
}

template<typename T>
void erase_n(std::vector<T>& vec, const T& to_erase, size_t count) {
	for (size_t i = 0; i < count; ++i) {		
		vec.erase(find(vec.begin(), vec.end(), to_erase));
	}
}

template<class _InIt,
	class _Fn> inline
	_Fn for_all(_InIt &_Capacitor, _Fn _Func)
{	
	return for_each(_Capacitor.begin(), _Capacitor.end(), _Func);
}

inline std::vector<BaseTile> convert_tiles_to_base_tiles(std::vector<Tile*> tile) {
	std::vector<BaseTile> bts;
	for_each(tile.begin(), tile.end(), [&bts](Tile* t) {bts.push_back(t->tile); });
	return bts;
}

/* Check if two containers have the same size and same corresponding value. */
template<typename T>
bool is_same_container(T a, T b) {
	if (a.size() != b.size()) {
		return false;
	}
	for (size_t i = 0; i < a.size(); ++i) {
		if (a[i] != b[i])
			return false;
	}
	return true;
}

inline std::vector<Tile*>::iterator
find_match_tile(std::vector<Tile*>& tiles, BaseTile t) {
	for (auto iter = tiles.begin();
		iter != tiles.end();
		++iter) {
		if ((*iter)->tile == t) {
			return iter;
		}
	}	
	return tiles.end();
}

inline std::vector<Tile*>::const_iterator
find_match_tile(const std::vector<Tile*>& tiles, BaseTile t) {
	for (auto iter = tiles.begin();
		iter != tiles.end();
		++iter) {
		if ((*iter)->tile == t) {
			return iter;
		}
	}	
	return tiles.end();
}

inline std::vector<Tile*>::iterator
find_match_tile(std::vector<Tile*>& tiles, Tile* t) {
	for (auto iter = tiles.begin();
		iter != tiles.end();
		++iter) {
		if ((*iter) == t) {
			return iter;
		}
	}
	return tiles.end();
}

// 找手牌中是不是有t的重复n张牌
inline std::vector<Tile*> get_duplicate(std::vector<Tile*> tiles, BaseTile t, unsigned int n) {

	std::vector<Tile*> duplicate_tiles;
	if (n > 4) { return duplicate_tiles; }

	int duplicates = 0;
	for (auto tile : tiles) {
		if (tile->tile == t)
			duplicates++;
	}
	if (duplicates == n) {
		for (auto tile : tiles) {
			if (tile->tile == t) {
				duplicates--;
				duplicate_tiles.push_back(tile);
			}
		}
	}
	sort(duplicate_tiles.begin(), duplicate_tiles.end());
	return duplicate_tiles;
}

template<typename T>
void merge_into(std::vector<T> &to, const std::vector<T> &from) {
	to.insert(to.end(), from.begin(), from.end());
}

class Base64 {
private:
	std::string _base64_table;
	static const char base64_pad = '='; 
public:
	Base64()
	{
		_base64_table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"; /*这是Base64编码使用的标准字典*/
	}
	/**
	 * 这里必须是unsigned类型，否则编码中文的时候出错
	 */
	inline std::string Encode(const unsigned char * str, int bytes) {
		int num = 0, bin = 0;
		std::string _encode_result;
		const unsigned char * current;
		current = str;
		while (bytes > 2) {
			_encode_result += _base64_table[current[0] >> 2];
			_encode_result += _base64_table[((current[0] & 0x03) << 4) + (current[1] >> 4)];
			_encode_result += _base64_table[((current[1] & 0x0f) << 2) + (current[2] >> 6)];
			_encode_result += _base64_table[current[2] & 0x3f];

			current += 3;
			bytes -= 3;
		}
		if (bytes > 0)
		{
			_encode_result += _base64_table[current[0] >> 2];
			if (bytes % 3 == 1) {
				_encode_result += _base64_table[(current[0] & 0x03) << 4];
				_encode_result += "==";
			}
			else if (bytes % 3 == 2) {
				_encode_result += _base64_table[((current[0] & 0x03) << 4) + (current[1] >> 4)];
				_encode_result += _base64_table[(current[1] & 0x0f) << 2];
				_encode_result += "=";
			}
		}
		return _encode_result;
	}
	inline std::string Decode(std::string str, int length) {
		const char DecodeTable[] =
		{
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -1, -1, -2, -2, -1, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-1, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, 62, -2, -2, -2, 63,
			52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -2, -2, -2, -2, -2, -2,
			-2,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
			15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -2, -2, -2, -2, -2,
			-2, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
			41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
			-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2
		};
		int bin = 0, i = 0, pos = 0;
		std::string _decode_result;
		const char *current = str.c_str();
		char ch;
		while ((ch = *current++) != '\0' && length-- > 0)
		{
			if (ch == base64_pad) { // 当前一个字符是“=”号
				/*
				先说明一个概念：在解码时，4个字符为一组进行一轮字符匹配。
				两个条件：
					1、如果某一轮匹配的第二个是“=”且第三个字符不是“=”，说明这个带解析字符串不合法，直接返回空
					2、如果当前“=”不是第二个字符，且后面的字符只包含空白符，则说明这个这个条件合法，可以继续。
				*/
				if (*current != '=' && (i % 4) == 1) {
					return NULL;
				}
				continue;
			}
			ch = DecodeTable[ch];
			//这个很重要，用来过滤所有不合法的字符
			if (ch < 0) { /* a space or some other separator character, we simply skip over */
				continue;
			}
			switch (i % 4)
			{
			case 0:
				bin = ch << 2;
				break;
			case 1:
				bin |= ch >> 4;
				_decode_result += bin;
				bin = (ch & 0x0f) << 4;
				break;
			case 2:
				bin |= ch >> 2;
				_decode_result += bin;
				bin = (ch & 0x03) << 6;
				break;
			case 3:
				bin |= ch;
				_decode_result += bin;
				break;
			}
			i++;
		}
		return _decode_result;
	}
};

// from p1 to p2
inline int get_distance(int p1, int p2) {
	if (p1 <= p2) {
		return p2 - p1;
	}
	else {
		return p2 - p1 + 4;
	}
}

// vector<string> merge
inline std::string merge_strings(std::vector<std::string> strings) {
	using std::string;
	string final_string;
	for (auto _string  : strings) {
		final_string += _string;
		final_string += " ";
	}
	return final_string;
}

inline Wind next_wind(Wind 风) {
	return (Wind)(int(风) + 1);
}

inline std::string score_to_string(std::array<int, 4> scores) {
	using namespace std;
	stringstream ss;
	ss << scores[0] << "|" << scores[1] << "|" << scores[2] << "|" << scores[3];
	return ss.str();
}

namespace_mahjong_end

#endif
#ifndef MACRO_H
#define MACRO_H

#include <vector>
#include <algorithm>
#include <type_traits>
#include <string>
#include <array>
#include "Tile.h"
#include "Profiler.h"
#include "fmt/core.h"

namespace_mahjong

template<typename ContainerType, typename ElemType>
bool is_in(const ContainerType &container, const ElemType &elem)
{
	if (std::find(std::begin(container), std::end(container), elem) != std::end(container))
		return true;
	else 
		return false;
}

template<typename T>
void erase_n(std::vector<T>& vec, const T& to_erase, size_t count) 
{
	for (size_t i = 0; i < count; ++i) vec.erase(find(vec.begin(), vec.end(), to_erase));
}

template<class _InIt, class _Fn>
_Fn for_all(_InIt &_Capacitor, _Fn _Func)
{	
	return std::for_each(_Capacitor.begin(), _Capacitor.end(), _Func);
}

inline std::vector<BaseTile> convert_tiles_to_basetiles(const std::vector<Tile*> &tile) {
	std::vector<BaseTile> bts;
	bts.reserve(tile.size());
	std::for_each(tile.begin(), tile.end(), [&bts](Tile* t) { bts.push_back(t->tile); });
	std::sort(bts.begin(), bts.end());
	return bts;
}

/* Check if two containers have the same size and same corresponding value. */
template<typename T>
bool is_same_container(const T& a, const T& b)
{
	if (a.size() != b.size()) {
		return false;

		for (size_t i = 0; i < a.size(); ++i) {
			if (a[i] != b[i]) return false;
		}
		return true;
	}
}

inline auto	find_match_tile(std::vector<Tile*>&tiles, BaseTile t) -> decltype(tiles.end())
{
	for (auto iter = tiles.begin(); iter != tiles.end(); ++iter)
		if ((*iter)->tile == t) return iter;

	return tiles.end();
}

inline auto find_match_tile(const std::vector<Tile*> &tiles, BaseTile t) -> decltype(tiles.end())
{
	for (auto iter = tiles.begin(); iter != tiles.end(); ++iter)
		if ((*iter)->tile == t) return iter;

	return tiles.end();
}

inline auto find_match_tile(std::vector<Tile*>&tiles, Tile *t) -> decltype(tiles.end())
{
	return std::find(tiles.begin(), tiles.end(), t);
}

/* 获取n张相同牌，并返回 */
inline std::vector<Tile*> get_n_copies(const std::vector<Tile*> &tiles, BaseTile t, unsigned int n) {

	std::vector<Tile*> copy_tiles;
	if (n > 4) { return copy_tiles; }

	int ncopies = 0;
	for (auto tile : tiles) {
		if (tile->tile == t)
			ncopies++;
	}
	if (ncopies == n) {
		for (auto tile : tiles) {
			if (tile->tile == t) {
				ncopies--;
				copy_tiles.push_back(tile);
			}
		}
	}
	sort(copy_tiles.begin(), copy_tiles.end());
	return copy_tiles;
}

template<typename T>
void merge_into(std::vector<T> &to, const std::vector<T> &from)
{
	to.insert(to.end(), from.begin(), from.end());
}

class Base64 {
private:
	std::string _base64_table;
	static const char base64_pad = '=';
public:
	Base64()
	{
		_base64_table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
	}
	inline std::string Encode(const unsigned char* str, int bytes) {
		int num = 0, bin = 0;
		std::string _encode_result;
		const unsigned char* current;
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
		const char* current = str.c_str();
		char ch;
		while ((ch = *current++) != '\0' && length-- > 0)
		{
			if (ch == base64_pad) {
				if (*current != '=' && (i % 4) == 1) {
					return NULL;
				}
				continue;
			}
			ch = DecodeTable[ch];
			if (ch < 0) {
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
inline int get_player_distance(int p1, int p2) {
	if (p1 <= p2) {
		return p2 - p1;
	}
	else {
		return p2 - p1 + 4;
	}
}

inline Wind next_wind(Wind wind) {
	return (Wind)((int(wind) + 1) % 4);
}

inline std::string score_to_string(const std::array<int, 4> &scores) {
	return fmt::format("{}", fmt::join(scores, "|"));
}

inline std::string vec2str(const std::vector<int> &vec)
{
	return fmt::format("{{{}}}", fmt::join(vec, ","));
};

namespace_mahjong_end

#endif
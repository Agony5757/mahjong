#ifndef Mini_Mahjong_Constant_H__
#define Mini_Mahjong_Constant_H__

#pragma once

#include <type_traits>

namespace mahjong
{	
	enum ClaimType
	{
		None = 0x00000000,
		Chi  = 0x00000001,
		Pong = 0x00000010,
		Kang = 0x00000100
	};
	ClaimType operator&(const ClaimType& type1, const ClaimType& type2);
	ClaimType operator|(const ClaimType& type1, const ClaimType& type2);
	ClaimType& operator|=(ClaimType& type1, const ClaimType& other);
	
	/*
	* TileType : 0bXX000000
	*/
	enum TileType
	{
		Manzu   = 0b00000000,
		Souzu   = 0b01000000,
		Ponzu   = 0b10000000,
		Special = 0b11000000
	};
	/*
	* TileData : 0b0000XXXX
	*    - Suzi : (1~9) 1-base
	*    - Special : {East, South, West, North, Hyaku, Patsu, Chun} 1-base
	*/

	
	enum class TileGroupType
	{
		None,
		Toitsu,
		Shuntsu,
		Ankou,
		Minkou,
		Ankang,
		Daiminkang,
		Shouminkang,
	};

	enum class Wind 
	{
		East,
		South,
		West,
		North
	};
	Wind& operator++(Wind& orgWind);
	Wind operator++(Wind& orgWind, int);
	Wind operator+(const Wind& orgWind, const int i);
	Wind operator-(const Wind& orgWind, const int i);
}

#endif
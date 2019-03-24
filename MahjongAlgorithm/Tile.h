#ifndef Mini_Mahjong_Tile_H__
#define Mini_Mahjong_Tile_H__

#pragma once

#include "Constant.h"

#include <string>
#include <assert.h>
#include <stdint.h>
#include <vector>
#include <iostream>
#include <bitset>
#include <Windows.h>

namespace mahjong
{
	class Tile
	{
	public:
		Tile();
		Tile(const TileType tileType, const int data, const bool isDora);
		
		std::string toString() const;

		TileType getTileType() const;
		int getTileNumber() const;
		uint8_t getData() const;

		bool isDora() const;
		bool isYaochuTile() const;

		bool operator==(const Tile& t) const;
		bool operator!=(const Tile& t) const;
		bool operator<(const Tile& t) const;
		bool operator<=(const Tile& t) const;
		bool operator>(const Tile& t) const;
		bool operator>=(const Tile& t) const;
	private:
		uint8_t m_data;
		bool m_isDora;
	};

	namespace Tiles
	{
			const std::vector<Tile> yaochuTiles = {
			Tile(TileType::Special, 1, false),
			Tile(TileType::Special, 2, false),
			Tile(TileType::Special, 3, false),
			Tile(TileType::Special, 4, false),
			Tile(TileType::Special, 5, false),
			Tile(TileType::Special, 6, false),
			Tile(TileType::Special, 7, false),
			Tile(TileType::Manzu, 1, false),
			Tile(TileType::Manzu, 9, false),
			Tile(TileType::Ponzu, 1, false),
			Tile(TileType::Ponzu, 9, false),
			Tile(TileType::Souzu, 1, false),
			Tile(TileType::Souzu, 9, false),
		};
	}
}

#endif
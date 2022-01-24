#include <assert.h>
#include "Tile.h"

namespace mahjong
{
	Tile::Tile() : m_data(0), m_isDora(false)
	{

	}

	Tile::Tile(const TileType tileType, const int data , const bool isDora)
	{
		assert( 
			( (tileType == TileType::Manzu || tileType == TileType::Ponzu || tileType == TileType::Souzu) && 1 <= data && data <= 9) ||
			( tileType == TileType::Special && 1 <= data && data <= 7 )
		);
		m_data = tileType | data;
		m_isDora = isDora;
	}

	std::string Tile::toString() const
	{
		std::string out = "";
		switch (getTileType())
		{
		case mahjong::TileType::Manzu:
			out = std::to_string(getTileNumber()) + "万";
			break;
		case mahjong::TileType::Ponzu:
			out = std::to_string(getTileNumber()) + "筒";
			break;
		case mahjong::TileType::Souzu:
			out = std::to_string(getTileNumber()) + "索";
			break;
		case mahjong::TileType::Special:
			switch (getTileNumber())
			{
			case 0b00000001:
				out = "东";
				break;
			case 0b00000010:
				out = "南";
				break;
			case 0b00000011:
				out = "西";
				break;
			case 0b00000100:
				out = "北";
				break;
			case 0b00000101:
				out = "白";
				break;
			case 0b00000110:
				out = "发";
				break;
			case 0b00000111:
				out = "中";
				break;
			default:
				std::cerr << "Unknown Special Character : " << std::bitset<8>(getData()) << std::endl;
				system("pause");
			}
			break;
		default:
			std::cerr << "Unknown Type : " << std::bitset<8>(getData()) << std::endl;
			system("pause");
		}
		return out;
	}

	TileType Tile::getTileType() const
	{
		return static_cast<TileType>(m_data & 0b11000000);
	}

	int Tile::getTileNumber() const
	{
		return m_data & 0b00001111;
	}

	uint8_t Tile::getData() const
	{
		return m_data;
	}

	bool Tile::isDora() const
	{
		return m_isDora;
	}

	bool Tile::isYaochuTile() const
	{
		if (getTileType() == TileType::Special || ((getTileNumber() == 1 || getTileNumber() == 9)))
			return true;
		return false;
	}

	// Operator overloading
	bool Tile::operator==(const Tile& t) const
	{
		return m_data == t.getData();
	}

	bool Tile::operator!=(const Tile& t) const
	{
		return m_data != t.getData();
	}

	bool Tile::operator<(const Tile& t) const
	{
		return m_data < t.getData();
	}

	bool Tile::operator<=(const Tile& t) const
	{
		return m_data <= t.getData();
	}

	bool Tile::operator>(const Tile& t) const
	{
		return m_data > t.getData();
	}

	bool Tile::operator>=(const Tile& t) const
	{
		return m_data >= t.getData();
	}
}
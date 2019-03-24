#include "TileGroup.h"

namespace mahjong
{
	TileGroup::TileGroup()
	{
		m_tileGroupType = TileGroupType::None;
		m_tiles.clear();
	}

	TileGroup::TileGroup(const std::vector<Tile>& newTiles, TileGroupType newTileGroupType)
	{
		m_tiles = newTiles;
		m_tileGroupType = newTileGroupType;
	}

	void TileGroup::reset()
	{
		m_tiles.clear();
	}

	void TileGroup::putTile(const Tile& newTile)
	{
		m_tiles.push_back(newTile);
	}

	void TileGroup::setTileGroupType(const TileGroupType& newTileGroupType)
	{
		m_tileGroupType = newTileGroupType;
	}

	TileGroupType TileGroup::getTileGroupType() const
	{
		return m_tileGroupType;
	}

	std::vector<Tile> TileGroup::getTilesList() const
	{
		return m_tiles;
	}

	bool TileGroup::operator==(const TileGroup& other) const
	{
		if (m_tileGroupType != other.getTileGroupType() || m_tiles.size() != other.getTilesList().size())
			return false;

		for (size_t i = 0; i < m_tiles.size(); i++)
			if (m_tiles[i] != other.getTilesList()[i])
				return false;

		return true;
	}

	bool TileGroup::operator!=(const TileGroup& other) const
	{
		if (*this == other)
			return false;
		else
			return true;
	}

	bool TileGroup::operator<(const TileGroup& other) const
	{
		if (m_tileGroupType == TileGroupType::Toitsu && other.getTileGroupType() != TileGroupType::Toitsu)
			return true;
		else if (m_tileGroupType != TileGroupType::Toitsu && other.getTileGroupType() == TileGroupType::Toitsu)
			return false;

		if (m_tiles[0] < other.getTilesList()[0])
			return true;
		else 
			return false;
	}

	bool TileGroup::operator>=(const TileGroup& other) const
	{
		if (*this == other || *this > other)
			return true;
		else
			return false;
	}

	bool TileGroup::operator>(const TileGroup& other) const
	{
		if (*this != other && !(*this < other))
			return true;
		else
			return false;
	}

	bool TileGroup::operator<=(const TileGroup& other) const
	{
		if (*this < other || *this == other)
			return true;
		else
			return false;
	}

	bool operator==(const CompletedTiles& t1, const CompletedTiles& t2)
	{
		if (t1.head == t2.head)
		{
			for (size_t i = 0; i < t1.body.size(); i++)
				if (t1.body[i] != t2.body[i])
					return false;
			return true;
		}
		return false;
	}


}
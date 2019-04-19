#include "Yaku.h"

#include <iostream>
#include <algorithm>
#include <set>

namespace mahjong
{
	Yaku::Yaku() {}
	Yaku::Yaku(const Yaku& other) {}
	Yaku::~Yaku() {}

	Yaku* Yaku::GetInstance()
	{
		static Yaku ins;
		return &ins;
	}

	void Yaku::reset()
	{
		m_completedTiles.head.reset();
		for (auto it : m_completedTiles.body)
		it.reset();
		m_toitsuNum = 0;
	}

	//std::vector<CompletedTiles> Yaku::testGetYaku(const Player& p, const Tile& agariTile, bool isTsumo)
	//{
	//	std::vector<CompletedTiles> ret;

	//	reset();
	//	m_completedTiles.body = p.getOpendMentsu();
	//	std::vector<CompletedTiles> duplicated = getAllCompletedTiles(p.getInHandTiles(), agariTile, isTsumo);
	//	for (auto it : duplicated)
	//		if (std::find(std::begin(ret), std::end(ret), it) == std::end(ret))
	//			ret.push_back(it);

	//	return ret;
	//}


	std::vector<CompletedTiles> Yaku::getAllCompletedTiles(const std::vector<Tile>& curTiles, const Tile& agariTile, bool isTsumo)
	{
		std::vector<CompletedTiles> ret;

		// 对
		std::vector<CompletedTiles> toitsuCompletedTiles;

		// 顺
		std::vector<CompletedTiles> shuntsuCompletedTiles;

		// 刻
		std::vector<CompletedTiles> koutsuCompletedTiles;

		bool flag = false;
		unsigned int index = 0;

		std::vector<Tile> tmpTiles;
		while (index < curTiles.size())
		{
			toitsuCompletedTiles.clear();
			shuntsuCompletedTiles.clear();
			koutsuCompletedTiles.clear();

			if (index > 0 && curTiles[index] == curTiles[index - 1])
			{ // Skip same tiles
				index++;
				continue;
			}

			// 1. Find Toitsu (Head)
			if (m_toitsuNum == 0)
			{
				if (std::count(std::begin(curTiles), std::end(curTiles), curTiles[index]) >= 2)
				{
					flag = true;
					tmpTiles = curTiles;
					TileGroup tmpHead;
					tmpHead.setTileGroupType(TileGroupType::Toitsu);
					for (int i = 0; i < 2; i++) {
						tmpHead.putTile(*std::find(std::begin(tmpTiles), std::end(tmpTiles), curTiles[index]));
						tmpTiles.erase(std::find(std::begin(tmpTiles), std::end(tmpTiles), curTiles[index]));
					}
					m_completedTiles.head = tmpHead;
					m_toitsuNum++;
					toitsuCompletedTiles = getAllCompletedTiles(tmpTiles, agariTile, isTsumo);
					m_toitsuNum--;
				}

			}

			// 2. Find Koutsu
			if (std::count(std::begin(curTiles), std::end(curTiles), curTiles[index]) == 3)
			{
				flag = true;
				tmpTiles = curTiles;
				TileGroup tmpKoutsu;
				tmpKoutsu.setTileGroupType(TileGroupType::Ankou);
				for (int i = 0; i < 3; i++) {
					tmpKoutsu.putTile(*std::find(std::begin(tmpTiles), std::end(tmpTiles), curTiles[index]));
					tmpTiles.erase(std::find(std::begin(tmpTiles), std::end(tmpTiles), curTiles[index]));
				}
				m_completedTiles.body.push_back(tmpKoutsu);
				koutsuCompletedTiles = getAllCompletedTiles(tmpTiles, agariTile, isTsumo);
				m_completedTiles.body.erase(std::find(std::begin(m_completedTiles.body), std::end(m_completedTiles.body), tmpKoutsu));
			}

			// 3. Find Shuntsu : Sorted
			if (curTiles[index].getTileType() != TileType::Special &&
				std::find_if(std::begin(curTiles), std::end(curTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber() + 1); }) != std::end(curTiles) &&
				std::find_if(std::begin(curTiles), std::end(curTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber() + 2); }) != std::end(curTiles))
			{
				flag = true;
				TileGroup tmpShuntsu;
				tmpShuntsu.setTileGroupType(TileGroupType::Shuntsu);
				tmpTiles = curTiles;
				tmpShuntsu.putTile(*std::find_if(std::begin(tmpTiles), std::end(tmpTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber()); }));
				tmpTiles.erase(std::find_if(std::begin(tmpTiles), std::end(tmpTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber()); }));
				tmpShuntsu.putTile(*std::find_if(std::begin(tmpTiles), std::end(tmpTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber() + 1); }));
				tmpTiles.erase(std::find_if(std::begin(tmpTiles), std::end(tmpTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber() + 1); }));
				tmpShuntsu.putTile(*std::find_if(std::begin(tmpTiles), std::end(tmpTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber() + 2); }));
				tmpTiles.erase(std::find_if(std::begin(tmpTiles), std::end(tmpTiles), [&](const Tile& t) { return (t.getTileType() == curTiles[index].getTileType() && t.getTileNumber() == curTiles[index].getTileNumber() + 2); }));

				m_completedTiles.body.push_back(tmpShuntsu);
				shuntsuCompletedTiles = getAllCompletedTiles(tmpTiles, agariTile, isTsumo);
				m_completedTiles.body.erase(std::find(std::begin(m_completedTiles.body), std::end(m_completedTiles.body), tmpShuntsu));
			}

			if (toitsuCompletedTiles.size() > 0)
				ret.insert(std::end(ret), std::begin(toitsuCompletedTiles), std::end(toitsuCompletedTiles));
			if (shuntsuCompletedTiles.size() > 0)
				ret.insert(std::end(ret), std::begin(shuntsuCompletedTiles), std::end(shuntsuCompletedTiles));
			if (koutsuCompletedTiles.size() > 0)
				ret.insert(std::end(ret), std::begin(koutsuCompletedTiles), std::end(koutsuCompletedTiles));

			index++;
		}

		// 4. Rest Tile Check
		tmpTiles.clear(); // Used to save agariTiles
		if (flag == false) // false flag means there's no more tile which can be Mentsu
		{
			if (curTiles.size() == 1 && curTiles[0] == agariTile) // Head-wait
			{
				TileGroup head;
				head.setTileGroupType(TileGroupType::Toitsu);
				head.putTile(agariTile);
				head.putTile(curTiles[0]);
				m_completedTiles.head = head;
				std::sort(std::begin(m_completedTiles.body), std::end(m_completedTiles.body));
				ret.push_back(m_completedTiles);
			}
			else if (curTiles.size() == 2) // body-wait
			{
				TileGroup body;
				// Check Shuntsu - Left Tile
				if (
					agariTile.getTileType() == curTiles[0].getTileType() && agariTile.getTileType() == curTiles[1].getTileType() &&
					agariTile.getTileType() != TileType::Special &&

					agariTile.getTileNumber() == (curTiles[0].getTileNumber() - 1) && agariTile.getTileNumber() == (curTiles[1].getTileNumber() - 2)
					)
				{
					body.setTileGroupType(TileGroupType::Shuntsu);
					body.putTile(agariTile);
					body.putTile(curTiles[0]);
					body.putTile(curTiles[1]);
					m_completedTiles.body.push_back(body);
					std::sort(std::begin(m_completedTiles.body), std::end(m_completedTiles.body));
					ret.push_back(m_completedTiles);
					m_completedTiles.body.erase(std::find(std::begin(m_completedTiles.body), std::end(m_completedTiles.body), body));
				}
				// Check Shuntsu - Center Tile
				else if (agariTile.getTileType() == curTiles[0].getTileType() && agariTile.getTileType() == curTiles[1].getTileType() &&
					agariTile.getTileType() != TileType::Special &&

					agariTile.getTileNumber() == (curTiles[0].getTileNumber() + 1) && agariTile.getTileNumber() == (curTiles[1].getTileNumber() - 1)
					)
				{
					body.setTileGroupType(TileGroupType::Shuntsu);
					body.putTile(curTiles[0]);
					body.putTile(agariTile);
					body.putTile(curTiles[1]);
					m_completedTiles.body.push_back(body);
					std::sort(std::begin(m_completedTiles.body), std::end(m_completedTiles.body));
					ret.push_back(m_completedTiles);
					m_completedTiles.body.erase(std::find(std::begin(m_completedTiles.body), std::end(m_completedTiles.body), body));
				}
				// Check Shuntsu - Right Tile
				else if (agariTile.getTileType() == curTiles[0].getTileType() && agariTile.getTileType() == curTiles[1].getTileType() &&
					agariTile.getTileType() != TileType::Special &&

					agariTile.getTileNumber() == (curTiles[0].getTileNumber() + 2) && agariTile.getTileNumber() == (curTiles[1].getTileNumber() + 1)
					)
				{
					body.setTileGroupType(TileGroupType::Shuntsu);
					body.putTile(curTiles[0]);
					body.putTile(curTiles[1]);
					body.putTile(agariTile);
					m_completedTiles.body.push_back(body);
					std::sort(std::begin(m_completedTiles.body), std::end(m_completedTiles.body));
					ret.push_back(m_completedTiles);
					m_completedTiles.body.erase(std::find(std::begin(m_completedTiles.body), std::end(m_completedTiles.body), body));
				}
				// Check Toitsu
				if (agariTile == curTiles[0] && agariTile == curTiles[1])
				{
					body.setTileGroupType(isTsumo ? TileGroupType::Ankou : TileGroupType::Minkou);
					body.putTile(agariTile);
					body.putTile(curTiles[0]);
					body.putTile(curTiles[1]);
					m_completedTiles.body.push_back(body);
					std::sort(std::begin(m_completedTiles.body), std::end(m_completedTiles.body));
					ret.push_back(m_completedTiles);
					m_completedTiles.body.erase(std::find(std::begin(m_completedTiles.body), std::end(m_completedTiles.body), body));
				}
			}
		}

		return ret;
	}
}
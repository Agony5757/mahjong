#ifndef TABLE_STATUS_H
#define TABLE_STATUS_H

#include "Tile.h"
#include "GameLog.h"
// 显示每个玩家可以看到的桌面状态
// 这个信息可以从GameLog openLog里面获得

// Abstract Base Class
class AbstractTableStatus {
public:
	AbstractTableStatus(const GameLog &gameLog);
	GameLog game_log;
	virtual GameLog get_gamelog();
	std::string status;
	virtual void parse_gamelog();
	std::string to_string();
};

class TableStatus : public AbstractTableStatus {
public:
	void clear_all();
	void parse_gamelog();
	
	//Wind your_wind;
	//int mountain_remain;

	enum OpenTileSource {
		上家手切,
		上家摸切,
		下家手切,
		下家摸切,
		对家手切,
		对家摸切,
		自家手切,
		自家摸切,
	};

	struct OpenTileInfo {
		BaseTile tile;
		bool is_after_riichi;
		OpenTileSource source;
	};

	std::vector<BaseTile> your_river;
	std::vector<BaseTile> 上家_river;
	std::vector<BaseTile> 对家_river;
	std::vector<BaseTile> 下家_river;



};

#endif
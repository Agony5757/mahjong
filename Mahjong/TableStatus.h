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
};

class TableStatus : public AbstractTableStatus {
public:
	void clear_all();
	void parse_gamelog(const GameLog &gamelog);
	void to_string();

	Wind your_wind;
	int mountain_remain;

	

	enum OpenTileSource {
		手切,
		摸切,
		上家打出,
		下家打出,
		对家打出,
		
	};

	struct OpenTileInfo {
		BaseTile tile;
		bool is_riichi;
		OpenTileSource source;
	};

	std::vector<BaseTile> your_river;
	std::vector<BaseTile> 上家_river;
	std::vector<BaseTile> 对家_river;
	std::vector<BaseTile> 下家_river;

};

#endif
import MahjongPy as mj

table = mj.Table()
#table.game_init()
#print(mj.TableToString(table,999).decode("GBK"))

table.game_init_with_metadata({'oya':'1', 'wind':'east'})


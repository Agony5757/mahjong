import re
import os
import time
import numpy as np

# 下面这些包用于下载和解析牌谱
import eventlet
import xml.etree.ElementTree as ET
import urllib.request
import gzip

import MahjongPy as mp

eventlet.monkey_patch()

def get_tile_from_id(id):
    color = id // 36
    number = (id % 36) // 4 + 1
    color_str = "mpsz"
    return str(number) + color_str[color]

def get_tiles_from_id(tiles):
    ret = ''
    for tile in tiles:
        ret += get_tile_from_id(tile)
    return ret

def paipu_link(paipu):
    paipu = paipu[:-4]
    return r'http://tenhou.net/0/?log='+paipu
    

# 把副露的5位数解码成具体的东西
def decodem(naru_tiles_int, naru_player_id):
    # 54279 : 4s0s chi 6s
    # 35849 : 6s pon
    # 51275 : chu pon
    # ---------------------------------
    binaries = bin(naru_tiles_int)[2:]

    opened = True

    if len(binaries) < 16:
        binaries = "0" * (16 - len(binaries)) + binaries

    bit2 = int(binaries[-3], 2)
    bit3 = int(binaries[-4], 2)
    bit4 = int(binaries[-5], 2)

    if bit2:
        naru_type = "Chi"

        bit0_1 = int(binaries[-2:], 2)

        if bit0_1 == 3:  # temporally not used
            source = "kamicha"
        elif bit0_1 == 2:
            source = "opposite"
        elif bit0_1 == 1:
            source = "shimocha"
        elif bit0_1 == 0:
            source = "self"

        bit10_15 = int(binaries[:6], 2)
        bit3_4 = int(binaries[-5:-3], 2)
        bit5_6 = int(binaries[-7:-5], 2)
        bit7_8 = int(binaries[-9:-7], 2)

        which_naru = bit10_15 % 3

        source_player_id = (naru_player_id + bit0_1) % 4  # TODO: 包牌

        start_tile_id = int(int(bit10_15 / 3) / 7) * 9 + int(bit10_15 / 3) % 7

        side_tiles_added = [[start_tile_id * 4 + bit3_4, 0], [start_tile_id * 4 + 4 + bit5_6, 0],
                            [start_tile_id * 4 + 8 + bit7_8, 0]]
        # TODO: check aka!
        side_tiles_added[which_naru][1] = 1

        hand_tiles_removed = []
        for kk, ss in enumerate(side_tiles_added):
            if kk != which_naru:
                hand_tiles_removed.append(ss[0])


    else:
        naru_type = "Pon"

        if bit3:

            bit9_15 = int(binaries[:7], 2)

            which_naru = bit9_15 % 3
            pon_tile_id = int(int(bit9_15 / 3))

            side_tiles_added = [[pon_tile_id * 4, 0], [pon_tile_id * 4 + 1, 0], [pon_tile_id * 4 + 2, 0],
                                [pon_tile_id * 4 + 3, 0]]

            bit5_6 = int(binaries[-7:-5], 2)
            which_not_poned = bit5_6

            del side_tiles_added[which_not_poned]

            side_tiles_added[which_naru][1] = 1

            hand_tiles_removed = []
            for kk, ss in enumerate(side_tiles_added):
                if kk != which_naru:
                    hand_tiles_removed.append(ss[0])

        else:  # An-Kan, Min-Kan, Ka-Kan

            bit5_6 = int(binaries[-7:-5], 2)
            which_kan = bit5_6

            if bit4:
                naru_type = "Ka-Kan"
                bit9_15 = int(binaries[:7], 2)

                kan_tile_id = int(bit9_15 / 3)

                side_tiles_added = [[kan_tile_id * 4 + which_kan, 1]]

                hand_tiles_removed = [kan_tile_id * 4 + which_kan]

            else:  # An-Kan or # Min-Kan

                which_naru = naru_tiles_int % 4

                bit8_15 = int(binaries[:8], 2)

                kan_tile = bit8_15
                kan_tile_id = int(kan_tile / 4)
                which_kan = kan_tile % 4

                side_tiles_added = [[kan_tile_id * 4, 0], [kan_tile_id * 4 + 1, 0], [kan_tile_id * 4 + 2, 0],
                                    [kan_tile_id * 4 + 3, 0]]
                if which_naru == 0:
                    naru_type = "An-Kan"
                    hand_tiles_removed = []
                    for kk, ss in enumerate(side_tiles_added):
                        hand_tiles_removed.append(ss[0])
                    opened = False

                else:
                    naru_type = "Min-Kan"
                    side_tiles_added[which_kan][1] = 1

                    hand_tiles_removed = []
                    for kk, ss in enumerate(side_tiles_added):
                        if kk != which_kan:
                            hand_tiles_removed.append(ss[0])

    return side_tiles_added, hand_tiles_removed, naru_type, opened

def paipu_replay():
    # -------- 读取2020年所有牌谱的url ---------------
    # 参考 https://m77.hatenablog.com/entry/2017/05/21/214529

    # paipu_urls = []

    # path = os.path.dirname(__file__) + "/2020_paipu"
    # files = os.listdir(path)  # 得到文件夹下的所有文件名称

    # filenames = []

    # for file in files:  # 遍历文件夹
    #     if not os.path.isdir(file) and file[-4:] == "html":  # 判断是否是文件夹，不是文件夹才打开
    #         filenames.append(path + "/" + file)  # 打开文件

    # for filename in filenames:

    #     f = open(filename, 'r', encoding='UTF-8')

    #     scc = f.read()
    #     # print(scc)

    #     f.close()

    #     replay_urls = re.findall('href="(.+?)">', scc)

    #     log_urls = []

    #     for tmp in replay_urls:
    #         log_url_split = tmp.split("?log=")
    #         log_urls.append(log_url_split[0] + "log?" + log_url_split[1])

    #     paipu_urls = paipu_urls + log_urls

    # print("牌谱的URL读取完毕！")
    # print("----------------------------------")

    # # 天凤牌谱的hosts
    # hosts = ["e3.mjv.jp",
    #          "e4.mjv.jp",
    #          "e5.mjv.jp",
    #          "k0.mjv.jp",
    #          "e.mjv.jp"]

    num_games = 0
    is_new_round = False

    # ----------------- start ---------------------

    # 385284 matches in 2020 year
    # for url in paipu_urls:

        # success_paipu_load = False
        # for host in hosts:
        #     try:
        #         with eventlet.Timeout(2):
        #             # start_time = time.time()
        #             HEADER = {
        #                 'Host': host,
        #                 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0',
        #                 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        #                 'Accept-Language': 'en-US,en;q=0.5',
        #                 'Accept-Encoding': 'gzip, deflate',
        #                 'Connection': 'keep-alive'
        #             }

        #             req = urllib.request.Request(url=url, headers=HEADER)
        #             opener = urllib.request.build_opener()
        #             response = opener.open(req)
        #             paipu = gzip.decompress(response.read()).decode('utf-8')
        #             success_paipu_load = True
        #             print("读取牌谱成功! （{}）".format(url))
        #             break
        #     except:
        #         time.sleep(0.01)
        #         continue

        # if not success_paipu_load:
        #     print("读取牌谱失败! （{}） 跳过".format(url))
        #     continue

        # finish = False

        # if finish:
        #     break

        # # Save Paipu
        # if not os.path.exists("./paipuxmls"):
        #     os.makedirs("./paipuxmls")
        # paipu_id = url.split("?")[-1]
        # text_file = open("./paipuxmls/" + paipu_id + ".txt", "w")
        # text_file.write(paipu)
        # text_file.close()
    basepath = os.path.dirname(__file__)
    path = basepath + "/paipuxmls"
    files = os.listdir(path)  # 得到文件夹下的所有文件名称

    for paipu in files:
        if not paipu.endswith('txt'): continue
        filename = path + '/' + paipu
        # print(filename)
        try:
            tree = ET.parse(filename)
        except Exception as e:
            print(filename, e)
            continue
        root = tree.getroot()
        print("解析牌谱为ElementTree成功！")

        # =================== 开始解析牌谱 =======================

        replayer = None
        riichi_status = False
        for child_no, child in enumerate(root):
            # Initial information, discard
            if child.tag == "SHUFFLE":
                # 牌山生成，参见 http://blog.tenhou.net/article/30503297.html
                seed_str = child.get("seed")
                prefix = 'mt19937ar-sha512-n288-base64,'
                if not seed_str.startswith(prefix):
                    print('Bad seed string')
                    continue
                seed = seed_str[len(prefix):]
                inst = mp.TenhouShuffle.instance()
                inst.init(seed)

            elif child.tag == "GO":  # 牌桌规则和等级等信息.
                #         print(child.attrib)
                try:
                    type_num = int(child.get("type"))
                    tmp = str(bin(type_num))

                    game_info = dict()
                    game_info["is_pvp"] = int(tmp[-1])
                    if not game_info["is_pvp"]:
                        break

                    game_info["no_aka"] = int(tmp[-2])
                    if game_info["no_aka"]:
                        break

                    game_info["no_kuutan"] = int(tmp[-3])
                    if game_info["no_kuutan"]:
                        break

                    game_info["is_hansou"] = int(tmp[-4])
                    # no requirement

                    game_info["is_3ma"] = int(tmp[-5])
                    if game_info["is_3ma"]:
                        break

                    game_info["is_pro"] = int(tmp[-6])
                    # no requirement

                    game_info["is_fast"] = int(tmp[-7])
                    if game_info["is_fast"]:
                        break

                    game_info["is_joukyu"] = int(tmp[-8])

                except Exception as e:
                    print(e)
                    continue

                for key in game_info:
                    print(key, game_info[key])

                # 0x01	如果是PVP对战则为1
                # 0x02	如果没有赤宝牌则为1
                # 0x04	如果无食断则为1
                # 0x08	如果是半庄则为1
                # 0x10	如果是三人麻将则为1
                # 0x20	如果是特上卓或凤凰卓则为1
                # 0x40	如果是速卓则为1
                # 0x80	如果是上级卓则为1

            elif child.tag == "TAIKYOKU":
                print("=========== 此场开始 =========")
                is_new_round = False
                round_no = 0

            elif child.tag == "UN":
                # 段位信息
                pass

            elif child.tag == "INIT":
                print("-----   此局开始  -------")

                # 开局时候的各家分数
                scores_str = child.get("ten").split(',')
                scores = [int(tmp) * 100 for tmp in scores_str]
                print("开局各玩家分数：", scores)

                # Oya ID
                oya_id = int(child.get("oya"))
                print("庄家是玩家{}".format(oya_id))

                # 什么局
                winds = "东南西北"
                chinese_numbers = "一二三四"
                game_order = int(child.get("seed").split(",")[0])
                print("此局是{}{}局".format(winds[game_order // 4], chinese_numbers[game_order % 4]))

                # 本场和立直棒
                honba = int(child.get("seed").split(",")[1])
                riichi_sticks = int(child.get("seed").split(",")[2])
                print("此局是{}本场, 有{}根立直棒".format(honba, riichi_sticks))

                # 骰子数字
                dice_numbers = [int(child.get("seed").split(",")[3]) + 1, int(child.get("seed").split(",")[4]) + 1]
                print("骰子的数字是", dice_numbers)

                # 牌山
                inst = mp.TenhouShuffle.instance()
                yama = inst.generate_yama()
                print("牌山是: ", yama)

                # 利用PaiPuReplayer进行重放
                replayer = mp.PaipuReplayer()
                print(f'Replayer.init: {yama} {scores} {riichi_sticks} {honba} {game_order // 4} {oya_id}')
                replayer.init(yama, scores, riichi_sticks, honba, game_order // 4, oya_id)
                print('Init over.')

                # 开局的dora
                dora_tiles = [int(child.get("seed").split(",")[5])]
                print("开局DORA：{}".format(dora_tiles[-1]))

                # 开局的手牌信息:
                hand_tiles = []
                for pid in range(4):
                    tiles_str = child.get("hai{}".format(pid)).split(",")
                    hand_tiles_player = [int(tmp) for tmp in tiles_str]
                    hand_tiles_player.sort()
                    hand_tiles.append(hand_tiles_player)
                    print("玩家{}的开局手牌是{}".format(pid, get_tiles_from_id(hand_tiles_player)))

                game_has_init = True  # 表示这一局开始了
                remaining_tiles = 70

            # ------------------------- 对局过程中信息 ---------------------------
            elif child.tag == "DORA":
                dora_tiles.append(int(child.get("hai")))
                print("翻DORA：{}".format(dora_tiles[-1]))

            elif child.tag == "REACH":
                # 立直
                player_id = int(child.get("who"))
                if int(child.get("step")) == 1:
                    riichi_status = True
                    print("玩家{}宣布立直".format(player_id))

                if int(child.get("step")) == 2:
                    riichi_status = False
                    print("玩家{}立直成功".format(player_id))

            elif child.tag[0] in ["T", "U", "V", "W"] and child.attrib == {}:  # 摸牌
                player_id = "TUVW".find(child.tag[0])
                remaining_tiles -= 1
                obtained_tile = int(child.tag[1:])
                print("玩家{}摸牌{}".format(player_id, get_tile_from_id(obtained_tile)))
                # 进行4次放弃动作
                replayer.make_selection(0)
                replayer.make_selection(0)
                replayer.make_selection(0)
                replayer.make_selection(0)

            elif child.tag[0] in ["D", "E", "F", "G"] and child.attrib == {}:  # 打牌
                player_id = "DEFG".find(child.tag[0])
                discarded_tile = int(child.tag[1:])
                print("玩家{}舍牌{}".format(player_id, get_tile_from_id(discarded_tile)))
                self_actions = replayer.table.get_self_actions()
                sa_str = ''
                for sa in self_actions:
                    sa_str += sa.to_string()
                    sa_str += ','
                print(sa_str)
                if riichi_status:
                    for i, sa in enumerate(self_actions):
                        if sa.correspond_tiles[0].id == discarded_tile:
                            replayer.make_selection(int(i))

                    # replayer.make_selection_from_action(mp.BaseAction.Riichi, [discarded_tile])
                else:
                    for i, sa in enumerate(self_actions):
                        if sa.action == mp.BaseAction.Play and \
                           sa.correspond_tiles[0].id == discarded_tile:

                            print(i, sa.to_string())
                            replayer.make_selection(int(i))

                    # replayer.make_selection_from_action(mp.BaseAction.Play, [discarded_tile])
                print(replayer.table.get_selected_action().to_string())
            elif child.tag == "N":  # 鸣牌 （包括暗杠）
                naru_player_id = int(child.get("who"))
                player_id = naru_player_id
                naru_tiles_int = int(child.get("m"))

                # print("==========  Naru =================")
                side_tiles_added_by_naru, hand_tiles_removed_by_naru, naru_type, opened = decodem(
                    naru_tiles_int, naru_player_id)

                # opened = True表示是副露，否则是暗杠

                print("玩家{}用手上的{}进行了一个{}，形成了{}".format(
                    naru_player_id, hand_tiles_removed_by_naru, naru_type, side_tiles_added_by_naru))
                for i in range(4):
                    if replayer.get_phase() > int(mp.PhaseEnum.P4_ACTION): #回复阶段，除该人之外
                        if i != naru_player_id:
                            replayer.make_selection(0)
                    else: #自己暗杠或者鸣牌
                        response_types = ['Chi', 'Pon', 'Min-Kan']
                        action_types = {'Chi': mp.BaseAction.Chi, 'Pon': mp.BaseAction.Pon, 'Min-Kan': mp.BaseAction.Kan,
                                        'An-Kan': mp.BaseAction.AnKan, 'Ka-Kan': mp.BaseAction.KaKan}
                        # if naru_type in response_types:
                        #     correspond_tiles = hand_tiles_removed_by_naru                                                      
                        # elif naru_type == 'An-Kan':
                        #     hand_tiles_removed_by_naru # 都是corres.
                        # elif naru_type == 'Ka-Kan':
                        #     side_tiles_added_by_naru = [hand_tiles_removed_by_naru]
                        # else:
                        #     raise RuntimeError('???')

                        ret = replayer.make_selection_from_action(action_types[naru_type], 
                            hand_tiles_removed_by_naru)
                        if not ret:
                            print(f'要{naru_type} {get_tiles_from_id(hand_tiles_removed_by_naru)}, Fail.\n'
                                    f'{replayer.table.players[naru_player_id].to_string()}')
                            raise RuntimeError('Replay Fail.' + paipu_link(paipu))

            elif child.tag == "BYE":  # 掉线
                bye_player_id = int(child.get("who"))
                print("### 玩家{}掉线！！ ".format(bye_player_id))

            elif child.tag == "RYUUKYOKU" or child.tag == "AGARI":
                
                score_info_str = child.get("sc").split(",")
                score_info = [int(tmp) for tmp in score_info_str]
                score_changes = [score_info[1] * 100, score_info[3] * 100, score_info[5] * 100, score_info[7] * 100]

                if child.tag == "RYUUKYOKU":
                    print("本局结束: 结果是流局")                    

                if child.tag == "AGARI":
                    who_agari = []
                    if child_no + 1 < len(root) and root[child_no + 1].tag == "AGARI":
                        print("这局是Double Ron!!!!!!!!!!!!")
                        who_agari.append(int(root[child_no + 1].get("who")))

                    agari_player_id = int(child.get("who"))  
                    who_agari.append(int(child.get("who")))

                    for i in range(4):
                        phase = replayer.get_phase()
                        ret = False
                        if phase <= int(mp.PhaseEnum.P4_ACTION):
                            ret = replayer.make_selection_from_action(mp.BaseAction.Tsumo, [])
                        else:
                            if i not in who_agari:
                                replayer.make_selection(0)
                            else:
                                if phase <= int(mp.PhaseEnum.P4_RESPONSE):
                                    ret = replayer.make_selection_from_action(mp.BaseAction.Ron, [])
                                elif phase <= int(mp.PhaseEnum.P4_chankan):
                                    ret = replayer.make_selection_from_action(mp.BaseAction.ChanKan, [])
                                elif phase <= int(mp.PhaseEnum.P4_chanankan):
                                    ret = replayer.make_selection_from_action(mp.BaseAction.ChanAnKan, [])
                    
                    if not ret:
                        raise RuntimeError('Replay fail.')
                    
                    if replayer.get_phase() != int(mp.PhaseEnum.GAME_OVER):
                        raise RuntimeError('Replay fail.')

                    result = replayer.get_result()
                    scores = result.score
                    for i in range(4):
                        if score_changes[i] != scores[i]:
                            raise RuntimeError('Replay fail.')
                    
                    print('OK!')

                    from_who = int(child.get("fromWho"))
                    agari_tile = int(child.get("machi"))
                    honba = int(child.get("ba").split(",")[0])
                    riichi_sticks = int(child.get("ba").split(",")[1])

                    if from_who == agari_player_id:
                        info = "自摸"
                    else:
                        info = "玩家{}的点炮".format(from_who)

                    print("玩家{} 通过{} 用{} 和了{}点 ({}本场,{}根立直棒)".format(
                        agari_player_id, info, agari_tile, score_changes[agari_player_id] , honba, riichi_sticks))
                    print("和牌时候的手牌 (不包含副露):", [int(hai) for hai in child.get("hai").split(",")])

                print("本局各玩家的分数变化是", score_changes)

                if not (child_no + 1 < len(root) and root[child_no + 1].tag == "AGARI"):
                    game_has_end = True  # 这一局结束了
                    num_games += 1

                    if num_games % 100 == 0:
                        print("****************** 已解析{}局 ***************".format(num_games))

                if "owari" in child.attrib:
                    owari_scores = child.get("owari").split(",")
                    print("========== 此场终了，最终分数 ==========")
                    print(int(owari_scores[0]) * 100, int(owari_scores[2]) * 100,
                          int(owari_scores[4]) * 100, int(owari_scores[6]) * 100)

            else:
                print(child.tag, child.attrib)

                raise ValueError("Unexpected Element!")


if __name__ == "__main__":
    paipu_replay()
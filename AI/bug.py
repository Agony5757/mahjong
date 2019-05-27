#!/usr/bin/env python
# coding: utf-8


import numpy as np
import MahjongPy as mp

Phases = (
"P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION", "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE", "P4_RESPONSE",
"P1_抢杠RESPONSE", "P2_抢杠RESPONSE", "P3_抢杠RESPONSE", "P4_抢杠RESPONSE",
"P1_抢暗杠RESPONSE", "P2_抢暗杠RESPONSE", " P3_抢暗杠RESPONSE", " P4_抢暗杠RESPONSE", "GAME_OVER")

for n in range(1):
    t = mp.Table()
    t.game_init()
    for m in range(50):
        # print(Phases[t.get_phase()] )

        if t.get_phase() < 4:
            aval_actions = t.get_self_actions()
            a = np.random.randint(len(aval_actions))
            if aval_actions[a].action == mp.Action.Tsumo:
                print(aval_actions[a].action)
                for i in range(len(aval_actions[a].correspond_tiles)):
                    print(aval_actions[a].correspond_tiles[i].tile)
            t.make_selection(a)
        else:
            aval_actions = t.get_response_actions()
            a = np.random.randint(len(aval_actions))

            if aval_actions[a].action == mp.Action.Ron:
                print(aval_actions[a].action)
                for i in range(len(aval_actions[a].correspond_tiles)):
                    print(aval_actions[a].correspond_tiles[i].tile)
            t.make_selection(a)

        # print("\r")

        if Phases[t.get_phase()] == "GAME_OVER":
            print(t.get_result().result_type)
            break


## Check tiles once, fulus is OK!

for p in range(4):
    hand = t.players[p].hand
    print('player {}'.format(p))
    for k in range(len(hand)):
        print(hand[k].tile)
for p in range(4):
    fulus = t.players[p].fulus
    print('player {}'.format(p))
    for k in range(len(fulus)):
        for m in range(len(fulus[k].tiles)):
            print(fulus[k].tiles[m].tile)
        print(fulus[k].take)


## Check tiles twice, fulus[k].tiles becomes a empty list

for p in range(4):
    hand = t.players[p].hand
    print('player {}'.format(p))
    for k in range(len(hand)):
        print(hand[k].tile)
for p in range(4):
    fulus = t.players[p].fulus
    print('player {}'.format(p))
    for k in range(len(fulus)):
        for m in range(len(fulus[k].tiles)):
            print(fulus[k].tiles[m].tile)
        print(fulus[k].take)
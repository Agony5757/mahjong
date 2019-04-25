import numpy as np
import tensorflow as tf
from naiveAI import *
from buffer import PrioritizedReplayBuffer
from copy import deepcopy

def _hand_conversion(hand_from_cpp):
    # convert from [0, 2, 2, 3, 4]
    # to 
    # [1,0,0,0,
    #  0,0,0,0
    #  1,1,0,0
    #  1,0,0,0,
    #  1,0,0,0
    #  ...]

    hand_encoded = np.zeros((34,4))
    for tile in hand_from_cpp:
        for i in range(4):
            if hand_encoded[i, tile] == 0:
                hand_encoded[i, tile] = 1

    return hand_encoded

def _hand_selection_conversion(hand_from_cpp):
    # convert from [0, 2, 2, 3, 4]
    # to list(list())
    # [2,2,3,4]
    # [0,2,3,4]
    # [0,2,3,4]
    # [0,2,2,4]
    # [0,2,2,3]

    selection_list_list = list()

    for i in range(len(hand_from_cpp)):
        copy_hand = deepcopy(hand_from_cpp)
        copy_hand.pop(i)
        selection_list_list.append(copy_hand)

    return selection_list_list

class DataAdapter:
    def __init__():
        self.agents = dict()
        sess = tf.InteractiveSession()
        self.nn = NMNaive(sess)

        self.this_states = dict()
        self.next_states = dict()
        self.actions = dict()
        self.hands = dict()
        self.next_aval_states = dict()
        self.policies = dict()

    def reset_all():
        # reset for a new name
        self.hands = None

    def register_agents(self, i, agent):
        self.agents[i] = agent

    def receive_game_result(self, score):
        for i in range(4):
            if i in self.agents:
                self.agents[i].remember(
                    self.this_states[i], 
                    self.actions[i], 
                    self.hands[i], 
                    score[i], 
                    True, 
                    self.next_aval_states[i], 
                    self.policies[i])
                self.agents[i].learn()
    
    def receive_all_player_hand_before_self_action(self, hands, turn):
        # for all players, each time before they select
        # is "this_state".
        # "aval_state" can be generated from "this_state" 

        # if in the middle of the game:
        # first start with a learning phase for all agents
        if self.this_state is None:
            for i in agents:
                self.next_states[i] = hands[i]
                self.agents[i].remember(
                    self.this_states[i], 
                    self.actions[i], 
                    self.next_states[i], 
                    -1, 
                    False, 
                    self.next_aval_states[i], 
                    self.policies[i])                    

        # everyone make a log
        for i in agents:
            self.this_states[i] = deepcopy(self.next_states[i])

        for i in agents:

            if i == turn:
                # for player who takes the action
                next_aval_state = np.zeros([len(hands[i]), 34, 4])


                selections = _hand_selection_conversion(hands[i])
                for i in len(hands[i]):
                    next_aval_state[i] = _hand_conversion(selection)

                self.next_aval_states[i] = next_aval_state
                self.actions[i], self.policies[i] = self.agents.select(next_aval_state)

            else:
                # for players who do not take action

                next_aval_state = None
                self.next_aval_states[i] = next_aval_state
                self.actions[i], self.policies[i] = self.agents.select(next_aval_state)

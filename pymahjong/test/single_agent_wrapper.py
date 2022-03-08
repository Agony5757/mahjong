import gym
import torch
from .env_pymahjong import MahjongEnv
import random


class SingleAgentMahjongEnv(gym.Env):
    THIS_AGENT_ID = 0
    # The agent is the player 0 in MahjongEnv (while Oya may be others)
    def __init__(self, opponent_agent="vlog-bc"):

        super(SingleAgentMahjongEnv, self).__init__()

        assert opponent_agent in ["random", "vlog-bc", "vlog-cql"]

        if opponent_agent =="vlog-cql":
            self.opponent_agent = torch.load("./models/mahjong_VLOG_CQL_0.model")
        elif opponent_agent == "vlog-bc":
            self.opponent_agent = torch.load("./models/mahjong_VLOG_BC_0.model")
        else:
            self.opponent_agent = "random"

        self.env = MahjongEnv()

        self.observation_space = self.env.observation_space
        self.oracle_observation_space = self.env.oracle_observation_space
        self.full_observation_space = self.env.full_observation_space
        self.action_space = self.env.action_space

    def _proceed_until_agent_turn(self):
        while self.env.get_curr_player_id() != self.THIS_AGENT_ID:
            if self.opponent_agent == "random":
                aval_actions = self.env.get_valid_actions(self.env.get_curr_player_id(), nhot=False)
                self.env.step(aval_actions[random.randint(len(aval_actions))])
            else:
                action_mask =  self.env.get_valid_actions(self.env.get_curr_player_id(), nhot=True)
                obs = self.env.get_obs(self.env.get_curr_player_id())
                action = self.agent.select(obs, action_mask=action_mask)
                self.env.step(action)

    def reset(self, oya=None, game_wind=None):
        if oya is None:
            oya = random.randint(4)
        if game_wind is None:
            game_wind = "east"

        self.env.reset(oya=oya, game_wind=game_wind)
        self._proceed_until_agent_turn()
        return self.get_obs()

    def step(self, action):
        assert self.env.get_curr_player_id() == self.THIS_AGENT_ID

        self.env.step(action)
        self._proceed_until_agent_turn()

        if self.env.is_over():
            r = self.env.get_payoffs()[self.THIS_AGENT_ID]
            done = True
        else:
            r = 0
            done = False

        return self.get_obs(), r, done, {}

    def get_obs(self):
        assert self.env.get_curr_player_id() == self.THIS_AGENT_ID
        return self.env.get_obs(self.THIS_AGENT_ID)

    def get_oracle_obs(self):
        assert self.env.get_curr_player_id() == self.THIS_AGENT_ID
        return self.env.get_oracle_obs(self.THIS_AGENT_ID)

    def get_full_obs(self):
        assert self.env.get_curr_player_id() == self.THIS_AGENT_ID
        return self.env.get_full_obs(self.THIS_AGENT_ID)

    def render(self, mode='human'):
        self.env.render()

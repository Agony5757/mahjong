
# Py

## Usage

The environment is wrapped like a Gym environment (https://github.com/openai/gym), but it differs from a normal single-agent gym environment because Mahjong is a 4-players game with sophisticated state transitions. Please see below for detailed API.

This environment only supports Python 3.7 on Ubuntu 18.04 and Python 3.6 on Windows.



## Decision flow

Decision steps were divided into two categories (drawing a tile is not considered a decision step):
- step_response: when a player can make response to another player's played tile (Pong, Chi, Kan, Win (Ron), etc.).


- step_play: when a player can make some decisions based on the tiles of itself (An-Kan, Ka-Kan, Win (Tsumo), etc.).

When either step for any player is needed, the corresponding player ("get_curr_player_id()") selects a valid action and then the game proceeds until the next decision step).
(sometimes multiple players can respond to the same tile, then they need make decisions respectively according to counterclockwise order and then game proceeds).

For convenience to AI study, we unified all decision steps into a single "step" method. See **API** and **Example** for details


##  Observation

The executor observation has shape of 93 by 34, and the oracle observation has shape of 111 by 34. The first dimension corresponds to 111 features (channels),  The second dimension of observation (with size 34)  corresponds to 34 Mahjong tiles (the order is Character 1-9, Dot 1-9,  Bamboo 1-9, East, South, West, North, White, Green, Red).

The value of any element in an observation is 1 or 0. See [observation_action_explanation.pdf](https://github.com/pymahjong/pymahjong/blob/main/observation_action_explanation.pdf) for details.


## Action

We use 47 discrete actions to encode all possible decisions in a game. See [observation_action_explanation.pdf](https://github.com/pymahjong/pymahjong/blob/main/observation_action_explanation.pdf) for details.



## Dataset for offline reinforcement learning / imitation learning

Please downloaded from: https://drive.google.com/drive/folders/19v6bpG_9nfKgSGVscbQ6efaJP1fFoPpo?usp=sharing

The data after unzipping are in .mat format, which can be loaded in Python using scipy
```
data = scipy.io.loadmat("xxx.mat")
```
The loaded data is a Python dictionary contains the human demonstrations
- data["X"] : executor observation
- data["O"] : additional oracle observation (oracle observation is np.concatenate([data["X"], data["O"]], axis=-2))
- data["A"] : Action selected
- data["M"] : Valid actions (=1 means the corresponding action is valid at that step)
- data["R"] : Reward
- data["D"] : Done signal
- data["V"] : =0 if this step is the terminated step of an episode
  (i.e. the status after a game comes to a result, and observations at this step were recorded);
  otherwise = 1.

Each batch of data corresponds to around 0.6~0.7 million steps, or around 40,000 games.

## Example

For a simplest example where agents make fully random decisions (Please make sure you are using Python 3.7 on Ubuntu 18.04 or Python 3.6 on Windows)
```
git clone https://github.com/pymahjong/pymahjong
cd pymahjong
pip install -r requirements.txt
python env_mahjong_example.py
```

### Know Issues
There is a common error message:

> ImportError: libpython3.7m.so.1.0: cannot open shared object file: No such file or directory

Some possible ways to fix this are
```
sudo apt-get install libpython3.7
```
or
```
export LD_LIBRARY_PATH=/path/to/libpython/directory
```



## API

The basic API is similar to openAI-gym, however,
since Mahjong is a multi-player game with complicated state transitions,
there is some difference

First to make an instance of the environment
```
from env_mahjong import *
env = EnvMahjong()
```

To init a game (episode), you need the ID of the parent player ("Oya") and game wind, e.g.,
```
sp = env.reset(0, 'east')  # oya ID and game wind
```

After an episode starts, we need to know the ID of current decison-making player, obatined by
```
curr_pid = env.get_curr_player_id()
```
The next thing to know what actions are valid at current decision step, with 2 ways
```
valid_actions = env.get_valid_actions(nhot=False)  # List[int] of valid actions
action_mask = env.get_valid_actions(nhot=True)  # n-hot vector of valid actions
```

To get executor and oracle observations,
```
x_executor = env.get_obs(curr_pid)
x_oracle = np.concatenate([x_executor, env.get_oracle_obs(curr_pid)], axis=-2)
```
The agent should select an action inside "valid_actions" using executor observation.
Then, we can used the Gym-like step function to continue the game
```
action = decision_model(x_executor)
sp, r, done, info = env.step(curr_pid, action)
```
Here sp is the raw state after this decision.
We do not recommend to use sp directly because game state may frequently chang during non-decison steps (e.g., drawing tiles).
Instead, we should always call "env.get_obs(curr_pid)" and "env.get_oracle_obs(curr_pid)" right before usage.

We also do not recommend to use r and done during the game. Instead, we can get the payoff if a game is done:

```
if env.has_done():  # Should use env.has_done() instead of done from step()!!
    print("result:", np.array(env.get_payoffs()))
```
where "env.get_payoffs()" returns a list of payoffs of the four players.

See [env_mahjong_example.py](https://github.com/pymahjong/pymahjong/blob/main/env_mahjong_example.py) for a runnable instance.

## Citation
```
@inproceedings{
han2022variational,
title={Variational oracle guiding for reinforcement learning},
author={Dongqi Han and Tadashi Kozuno and Xufang Luo and Zhao-Yun Chen and Kenji Doya and Yuqing Yang and Dongsheng Li},
booktitle={International Conference on Learning Representations},
year={2022},
url={https://openreview.net/forum?id=pjqqxepwoMy}
}
```
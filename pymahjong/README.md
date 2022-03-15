# pymahjong

pymahjong is an python environment for decision-AI study, based on Japanese Mahjong. The environment was introduced in the research article "Variational Oracle Guiding for Reinforcement Learning" (https://openreview.net/forum?id=pjqqxepwoMy) by Dongqi Han, Tadashi Kozuno, Xufang Luo, Zhao-Yun Chen, Kenji Doya, Yuqing Yang and Dongsheng Li.


we provide a **multi-agent** and a **single-agent** versions of Mahjong envrionments.
The difference is that the single-agent version is like a standard OpenAI gym environment, in which the agent plays with 3 pre-trained opponents;
while in the multi-agent version, 4 agents play with each other: at each step, a certain player (env.get_current_player_id()) needs to make an action until the game is over.

## Installation

Require Python 3.6 or higher, currently tested on Ubuntu 18.04 and 20.04

```
pip install pymahjong
```

To check if it works
```
import pymahjong
pymahjong.test()
```

Dependence:
- gym
- numpy
- torch (to use pretrained models)

## Observation and action encoding

We encode the executor observation by a matrix of shape 93 by 34, and the full observation (executor & oracle) is a matrix of shape 111 by 34. The first dimension corresponds to 111 features (channels),  The second dimension of observation (with size 34) corresponds to 34 Mahjong tiles (the order is Character 1-9, Dot 1-9,  Bamboo 1-9, East, South, West, North, White, Green, Red).  If you want to have customized encoding, please check the documentation of the C++ code https://github.com/Agony5757/mahjong/.

The value of any element in an observation matrix is 1 or 0. See [observation_action_explanation.pdf](https://github.com/Agony5757/mahjong/blob/master/pymahjong/observation_action_explanation.pdf) for details.

We use 47 discrete actions to encode all possible decisions in a game. See [observation_action_explanation.pdf](https://github.com/Agony5757/mahjong/blob/master/pymahjong/observation_action_explanation.pdf) for details. (If you know the rule of Riichi Mahjong, for your information, we divided the "riichi" action into 2 steps: first decide which tile to discard; then if riichi is possible, decide whether to riichi or not (dama)).


## Single-agent version

The usage is similar to a standard OpenAI gym environment. However, one should note that **not all actions are available at a given step**, although there are 47 different possible actions.
To know what actions are allowed, see the example code below. 

```
import pymahjong
import numpy as np

env = pymahjong.SingleAgentMahjongEnv(opponent_agent="vlog-bc")  # the 3 opponents play randomly

obs = env.reset()  # get the obsevation at the first step of a game

while True:
    valid_actions = env.get_valid_actions()  # e.g., [0, 3, 4, 20, 21]

    a = np.random.choice(valid_actions)  # make decision among valid actions

    obs, reward, done, _ = env.step(a)  # reward is zero unless the game is over (done = True).

    # oracle_obs = env.get_oracle_obs()  # if you need oracle observation
    # full_obs = env.get_oracle_obs()  # full_obs = concat((obs, oracle_obs), axis=0)

    if done:
        print("agent payoff = {}".format(reward))
        break
```

Note: In a Mahjong game, it is possible the game is over before a certain player start to act (if others satisfy the game-over condition). In this case, the single-agent version envrionment will simply reset the game. Therefore, the agent always has at least 1 decision step in a game (episode).

### pretrained opponents agent
We provide two pretrained models for the 3 opponents (see the paper https://openreview.net/forum?id=pjqqxepwoMy) in the single-agent version environment.

To use the pretrained models, you need to have [PyTorch](https://pytorch.org/) installed. You can download the models from [this link](https://1drv.ms/u/s!AuxZyB8UeEtsgpNScPpUjF1c09gaZQ?e=j4lS05) and put the .model files at the same directory as your python script. The pretrained model should automatically enable CUDA if your PyTorch supports CUDA.

Variational Latent Oracle Guiding + Conservative Q-learning
```
env = pymahjong.SingleAgentMahjongEnv(opponent_agent="vlog-cql")
```

Variational Latent Oracle Guiding + Behavior Cloning
```
env = pymahjong.SingleAgentMahjongEnv(opponent_agent="vlog-bc")
```



## Multi-agent version

The basic API is similar to openAI-gym, however,
since Mahjong is a multi-player game with complicated state transitions,
there is some difference

First to make an instance of the environment
```
import pymahjong
env = pymahjong.MahjongEnv()
```

To init a game (episode)
```
env.reset()  
```

After an episode starts, we need to know the ID of current decison-making player, obatined by
```
curr_pid = env.get_curr_player_id()
```
The next thing to know is what actions are valid at the current decision step, by
```
valid_actions = env.get_valid_actions()  # List[int] of valid actions
```


To get executor and oracle observations of the current decision-making player,
```
executor_obs = env.get_obs(curr_pid)
oracle_obs = env.get_oracle_obs(curr_pid)
# full_obs = concat((executor_obs, oracle_obs), axis=0)
```
The agent should select an action among "valid_actions".
Then, we can used the Gym-like step function to continue the game
```
action = decision_model(executor_obs, valid_actions) 
env.step(curr_pid, action)
```
The env.step() method does return any data because the game state may frequently change during non-decision steps (e.g., drawing tiles).
Instead, we should always call "env.get_obs(curr_pid)" and "env.get_oracle_obs(curr_pid)" right before usage.

After each call of "env.step()", we should check "env.is_over()" which indicates the end of a game. We can get the payoffs of the 4 players if a game is over:

```
if env.is_over(): 
    print("result:", np.array(env.get_payoffs()))
```
where "env.get_payoffs()" returns a list of payoffs of the four players.

### Example
```
import pymahjong
import numpy as np
env = pymahjong.MahjongEnv()

num_games = 100

for game in range(num_games):

    env.reset()

    while not env.is_over():
        curr_player_id = env.get_curr_player_id()

        # --------- get decision information -------------

        valid_actions = env.get_valid_actions()

        executor_obs = env.get_obs(curr_player_id)

        # oracle_obs = env.get_oracle_obs(curr_player_id)
        # full_obs = env.get_full_obs(curr_player_id)
        # full_obs = np.concatenate([executor_obs, oracle_obs], axis=0)

        # --------- make decision -------------

        a = np.random.choice(valid_actions)

        env.step(curr_player_id, a)

    # ----------------------- get result ---------------------------------

    payoffs = np.array(env.get_payoffs())
    print("Game {}, payoffs: {}".format(game, payoffs))

```



## Game initialization
Although we recommend to to directly use "env.reset()" to initialize a game,
one may manually assign "oya" (0, 1, 2 or 3) and "game_wind" ("east", "south", "west" or "north"). By default, each player alternatively plays as oya and the game wind is "east".
Seed for generating the Mahjong table can also be assigned, e.g.,
```
env.reset(oya=1, game_wind="south", seed=1234)
```


## Rendering
Currently we do not have a GUI, one may roughly check the game status by "env.render()" which prints the status of the Mahjong table in a simple way. If you would like to kindly help us for GUI, please contact us!


## Citation
```
@inproceedings{han2022variational,
    title={Variational oracle guiding for reinforcement learning},
    author={Dongqi Han and Tadashi Kozuno and Xufang Luo and Zhao-Yun Chen and Kenji Doya and Yuqing Yang and Dongsheng Li},
    booktitle={International Conference on Learning Representations},
    year={2022},
    url={https://openreview.net/forum?id=pjqqxepwoMy}
}
```

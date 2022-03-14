# pymahjong

pymahjong is an python environment for decision-AI study, based on Japanese Mahjong. 


we provide a **multi-agent** and a **single-agent** versions of Mahjong envrionments.
The difference is that the single-agent version is like a standard OpenAI gym environment, in which the agent plays with 3 pre-trained opponents;
while in the multi-agent version, 4 agents play with each other: at each step, a certain player (env.get_current_player_id()) needs to make an action until the game is over.

## Single-agent version

The usage is similar to a standard OpenAI gym environment. However, one should note that **not all actions are available at a given step**, although there are 47 different possible actions.
To know what actions are allowed, see the example code below. 

```
env = pymahjong.MahjongEnv()

env.reset()

while True:
    valid_actions = env.get_valid_actions()  # e.g., [0, 3, 4, 20, 21]
  
    a = np.random.choice(valid_actions)  # make decision among valid actions
  
    obs, reward, done, _ = env.step(a)
  
    if done:
        break

```


## Multi-agent version


## Oya, game wind


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

# pymahjong

[![PyPI version](https://badge.fury.io/py/pymahjong.svg)](https://pypi.org/project/pymahjong/)
[![Python versions](https://img.shields.io/pypi/pyversions/pymahjong.svg)](https://pypi.org/project/pymahjong/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://agony5757.github.io/mahjong/)
[![Build Status](https://github.com/Agony5757/mahjong/actions/workflows/build-and-test.yml/badge.svg?branch=master)](https://github.com/Agony5757/mahjong/actions/workflows/build-and-test.yml)

A Japanese Riichi Mahjong environment for decision AI research, featuring a high-performance C++ backend with Python bindings.

## Features

- **Complete Rule Implementation** - Full Japanese Riichi Mahjong rules including all standard yaku
- **Gymnasium Compatible** - Ready-to-use single-agent environment with pretrained opponents
- **Multi-agent Support** - 4-player environment for multi-agent research
- **Oracle Observation** - Access to hidden information (opponents' hands) for oracle-guided learning
- **High Performance** - C++ game engine with efficient Python bindings via pybind11
- **Cross-platform** - Pre-built wheels for Linux, macOS, and Windows (Python 3.10-3.14)

## Installation

```bash
pip install pymahjong
```

Verify the installation:

```python
import pymahjong
pymahjong.test()
```

## Quick Start

### Single-Agent Environment

Play against 3 opponents with a gym-like interface:

```python
import pymahjong
import numpy as np

env = pymahjong.SingleAgentMahjongEnv(opponent_agent="random")
obs = env.reset()

while True:
    valid_actions = env.get_valid_actions()
    action = np.random.choice(valid_actions)
    obs, reward, done, _ = env.step(action)
    
    if done:
        print(f"Game over! Payoff: {reward}")
        break
```

### Multi-Agent Environment

4 agents compete in a full game:

```python
import pymahjong
import numpy as np

env = pymahjong.MahjongEnv()

for game in range(10):
    env.reset()
    
    while not env.is_over():
        pid = env.get_curr_player_id()
        valid_actions = env.get_valid_actions()
        obs = env.get_obs(pid)
        
        action = np.random.choice(valid_actions)
        env.step(pid, action)
    
    print(f"Game {game}: payoffs = {env.get_payoffs()}")
```

## Documentation

Full documentation is available at [https://agony5757.github.io/mahjong/](https://agony5757.github.io/mahjong/)

- [Installation Guide](https://agony5757.github.io/mahjong/installation.html)
- [Quick Start](https://agony5757.github.io/mahjong/quickstart.html)
- [API Reference](https://agony5757.github.io/mahjong/api/index.html)
- [Advanced Topics](https://agony5757.github.io/mahjong/advanced/index.html)

## Pretrained Models

Pretrained opponent models are available from the [GitHub releases](https://github.com/Agony5757/mahjong/releases/tag/v1.0.2):

```python
env = pymahjong.SingleAgentMahjongEnv(opponent_agent="path/to/model.pth")
```

## Offline Dataset

Human demonstration data from Tenhou.net (6 dan+ players) is available for offline RL research. [Download from releases](https://github.com/Agony5757/mahjong/releases/tag/v1.0.2).

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Citing

If you use pymahjong in your research, please cite:

```bibtex
@inproceedings{han2022variational,
  title     = {Variational Oracle Guiding for Reinforcement Learning},
  author    = {Dongqi Han and Tadashi Kozuno and Xufang Luo and Zhao-Yun Chen 
               and Kenji Doya and Yuqing Yang and Dongsheng Li},
  booktitle = {International Conference on Learning Representations},
  year      = {2022},
  url       = {https://openreview.net/forum?id=pjqqxepwoMy}
}
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Contact

- Email: hdqhdq58@outlook.com
- QQ Group: 608064044

# pymahjong

A Japanese Mahjong environment for decision AI research.

```{toctree}
:hidden:
:maxdepth: 2

installation
quickstart
demo
api/index
advanced/index
examples/index
web_frontend
glossary
changelog
```

## Overview

**pymahjong** is a Python environment for decision-AI study, based on Japanese Riichi Mahjong. It provides both multi-agent and single-agent versions of Mahjong environments, making it suitable for reinforcement learning research.

The environment was introduced in the research article ["Variational Oracle Guiding for Reinforcement Learning"](https://openreview.net/forum?id=pjqqxepwoMy) published at ICLR 2022.

## Features

- **Complete Mahjong Rules**: Implements Japanese Riichi Mahjong rules including all standard yaku
- **Multi-agent Environment**: 4-player game environment for multi-agent research
- **Single-agent Environment**: Gym-compatible environment with pretrained opponents
- **Oracle Observation**: Hidden information (opponents' hands) available for oracle guiding research
- **C++ Backend**: High-performance C++ engine with Python bindings
- **Cross-platform**: Supports Linux, macOS, and Windows

## Quick Links

- [Installation Guide](installation.md)
- [Quick Start Guide](quickstart.md)
- {doc}`Live Demo <demo>`
- [API Reference](api/index.md)

## Citation

If you use pymahjong in your research, please cite:

```bibtex
@inproceedings{han2022variational,
  title={Variational oracle guiding for reinforcement learning},
  author={Dongqi Han and Tadashi Kozuno and Xufang Luo and Zhao-Yun Chen and Kenji Doya and Yuqing Yang and Dongsheng Li},
  booktitle={International Conference on Learning Representations},
  year={2022},
  url={https://openreview.net/forum?id=pjqqxepwoMy}
}
```

## Contact

- **Email**: hdqhdq58@outlook.com
- **GitHub**: [https://github.com/Agony5757/mahjong](https://github.com/Agony5757/mahjong)

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Test Commands

### Python Package (pymahjong)

```bash
# Install with uv (recommended)
uv venv && source .venv/bin/activate
uv pip install ".[dev,docs]"

# Or with pip
pip install ".[dev,docs]"

# Run basic tests
python -c "import pymahjong as pm; pm.test()"

# Run with pretrained opponents (requires PyTorch)
python -c "import pymahjong as pm; pm.test_with_pretrained('path/to/model.pth')"
```

### Build Wheel

```bash
# Build wheel
python -m build --wheel

# Wheel will be in dist/pymahjong-<version>-<python>-<platform>.whl
```

### C++ Native Build

```bash
mkdir build && cd build
cmake .. -DCMAKE_CXX_COMPILER=clang++
make -j$(nproc)
./bin/test  # Run C++ tests
```

### Documentation

```bash
pip install -e ".[docs]"
cd docs && make html
# Output: docs/_build/html/
```

### CI Testing

CI runs on Ubuntu with Python 3.10-3.13 matrix and executes:
1. Build package with `pip install .`
2. Run `python -c "import pymahjong as pm; pm.test()"`
3. Paipu replay validation

## Architecture Overview

### Core Components

**Mahjong/** — C++ game engine implementing Japanese Riichi Mahjong rules:
- `Table.h/cpp` — Central game state manager (tiles, players, phase, actions)
- `Player.h/cpp` — Player state (hand, river, riichi status, tenpai detection)
- `Rule.h/cpp` — Tile splitting, winning hand detection, tenpai calculation
- `Action.h/cpp` — Action types (Discard, Chi, Pon, Kan, Riichi, Ron, Tsumo, etc.)
- `ScoreCounter.h/cpp` — Yaku evaluation and score calculation
- `GamePlay.h/cpp` — `PaipuReplayer` for replaying recorded games
- `Encoding/` — Observation/action encoding for ML (V1 and V2)

**Pybinder/** — pybind11 bindings exposing C++ classes to Python as `MahjongPyWrapper` module.

**pymahjong/** — Python gymnasium environments:
- `env_pymahjong.py` — `MahjongEnv` (multi-agent) and `SingleAgentMahjongEnv` (gym-compatible)
- `models.py` — Pretrained model definitions (VLOG architecture)
- `tenhou_paipu_check.py` — Replay validation for Tenhou paipu files

**ThirdParty/** — Vendored dependencies (fmt, tenhou shuffle). pybind11 is installed via pip.

### Game Flow

The `Table` class uses a phase-based state machine:
1. `P1_ACTION` through `P4_ACTION` — Self-action phases (discard, riichi, tsumo, kan)
2. `P1_RESPONSE` through `P4_RESPONSE` — Response phases (chi, pon, ron, pass)
3. Special phases for ChanKan/ChanAnKan responses
4. `GAME_OVER` — Terminal state

Use `table.get_phase()` to check current phase, `table.get_self_actions()` or `table.get_response_actions()` for valid moves, and `table.make_selection(index)` to execute.

### Observation Encoding

- **Executor observation**: 93×34 boolean matrix (visible game state)
- **Oracle observation**: 18×34 boolean matrix (hidden information: opponents' hands)
- **Full observation**: 111×34 (concatenated)
- **Actions**: 54 discrete actions (see `env_pymahjong.py` for mapping)

### Key Patterns

- Actions are selected by index into the `self_actions` or `response_actions` vectors
- Use `get_selection_from_action_basetile()` to find action index from tile types
- Riichi is two-step: first discard tile selection, then riichi/pass decision
- Debug mode (`set_debug_mode(1 or 2)`) generates replayable code for debugging

## Build System

- **Build backend**: scikit-build-core (pyproject.toml)
- **Python binding**: pybind11 (installed via pip, not vendored)
- **CMake minimum**: 3.15
- **C++ standard**: C++14

## Dependencies

- Python 3.10+, NumPy, gymnasium
- PyTorch (optional, for pretrained models)
- C++14 compiler, CMake 3.15+
- pybind11 (build dependency, auto-installed)

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag: `git tag v1.x.x`
4. Push tag: `git push origin v1.x.x`
5. GitHub Actions builds wheels and publishes to PyPI

## Documentation

- Framework: Sphinx with Furo theme
- Source: `docs/` directory (Markdown via MyST)
- Deploy: GitHub Pages (`.github/workflows/docs.yml`)

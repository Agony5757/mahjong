# Contributing to pymahjong

Thank you for your interest in contributing! This guide covers the basics for getting started.

## Development Setup

### Prerequisites

- Python 3.10+
- C++14 compatible compiler (GCC 7+, Clang 5+, MSVC 2019+)
- CMake 3.15+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install for Development

```bash
# Clone the repository
git clone https://github.com/Agony5757/mahjong.git
cd mahjong

# Create virtual environment and install
uv venv && source .venv/bin/activate
uv pip install ".[dev,docs]"

# Verify installation
python -c "import pymahjong as pm; pm.test()"
```

### Build C++ Native Module

```bash
mkdir build && cd build
cmake .. -DCMAKE_CXX_COMPILER=clang++
make -j$(nproc)
./bin/test
```

## Code Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) with a line length of 88 characters
- Use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Write docstrings in [Google style](https://google.github.io/styleguide/pyguide.html#384-classes) for all public APIs

```bash
ruff check pymahjong/
ruff format pymahjong/
```

### C++

- Follow C++14 standard
- Use `clang-format` with the project's `.clang-format` configuration
- Add comments for non-obvious logic

## Pull Request Process

1. **Create a branch** from `develop` with a descriptive name:
   - `feature/add-new-encoding` for new features
   - `fix/observation-bug` for bug fixes
   - `docs/api-reference` for documentation

2. **Make your changes** with clear, focused commits

3. **Test your changes**:
   ```bash
   python -c "import pymahjong as pm; pm.test()"
   ```

4. **Update documentation** if you've added or changed public APIs

5. **Open a Pull Request** against the `develop` branch with:
   - A clear description of the change
   - Any relevant issue references
   - Test results or screenshots if applicable

## Reporting Issues

When filing a bug report, please include:

- Python version and OS
- pymahjong version (`pip show pymahjong`)
- A minimal reproducible example
- Expected vs. actual behavior

## Project Structure

```
Mahjong/          C++ game engine (rules, scoring, game logic)
Pybinder/         pybind11 bindings (C++ -> Python)
pymahjong/        Python package (environments, models, utilities)
docs/             Sphinx documentation
ThirdParty/       Vendored dependencies
```

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

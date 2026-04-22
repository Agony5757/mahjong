# Installation

## Requirements

- Python 3.10+
- CMake 3.15+
- C++14 compatible compiler (GCC, Clang, or MSVC)

## Install from PyPI

```bash
pip install pymahjong
```

## Verify Installation

```python
import pymahjong as pm
pm.test()
```

If installation is successful, you should see output like:

```
Total 100 random-play games, 100 games without error, takes X.XX s
```

## Install from Source

### Prerequisites

- Python 3.10+
- CMake 3.15+
- C++14 compiler:
  - Linux: GCC or Clang
  - macOS: Clang (Xcode Command Line Tools)
  - Windows: MSVC (Visual Studio Build Tools)

### Clone and Install

```bash
git clone https://github.com/Agony5757/mahjong.git
cd mahjong
pip install .
```

### Development Installation

For development, install with extra dependencies:

```bash
pip install -e ".[dev,docs]"
```

## Optional Dependencies

### PyTorch (for pretrained models)

To use pretrained opponent models in single-agent mode:

```bash
pip install torch
```

Download pretrained models from [GitHub Releases](https://github.com/Agony5757/mahjong/releases).

### Development Tools

```bash
pip install -e ".[dev]"
```

Includes: pytest, ruff

### Documentation Tools

```bash
pip install -e ".[docs]"
```

Includes: sphinx, furo, myst-parser, sphinx-autodoc-typehints, sphinx-copybutton

## Platform-specific Notes

### Linux

```bash
# Ubuntu/Debian
sudo apt-get install cmake g++ ninja-build

# Fedora
sudo dnf install cmake gcc-c++ ninja-build
```

### macOS

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install cmake (via Homebrew)
brew install cmake ninja
```

### Windows

1. Install Visual Studio Build Tools with C++ workload
2. Install CMake from [cmake.org](https://cmake.org/download/)
3. Ensure `cmake` is in your PATH

## Troubleshooting

### Build Errors

If you encounter build errors:

1. Ensure CMake 3.15+ is installed: `cmake --version`
2. Ensure you have a C++14 compatible compiler
3. Try building with verbose output: `pip install . -v`

### Import Errors

If `import pymahjong` fails after installation:

1. Check if the package is installed: `pip show pymahjong`
2. Try reinstalling: `pip install --force-reinstall pymahjong`
3. Check Python version: `python --version` (requires 3.10+)

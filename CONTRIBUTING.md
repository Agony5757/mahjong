# Contributing to pymahjong

Thanks for contributing. This repository mixes a C++ Mahjong engine, pybind11 bindings, Python environments, and documentation, so small, focused pull requests are much easier to review and validate than broad refactors.

## Before You Start

- Search existing [issues](https://github.com/Agony5757/mahjong/issues) before opening a new one.
- For behavior changes, include a concrete reproduction or paipu fragment whenever possible.
- For substantial design changes, open an issue first so the direction can be aligned before implementation.

## Development Setup

### Prerequisites

- Python 3.10+
- CMake 3.15+
- A C++14 compiler
- `uv` (recommended) or `pip`

### Install a Development Environment

```bash
git clone https://github.com/Agony5757/mahjong.git
cd mahjong

uv venv
source .venv/bin/activate
uv pip install ".[dev,docs]"
```

If you prefer `pip`, the equivalent is:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install ".[dev,docs]"
```

## Repository Layout

```text
Mahjong/          Core C++ rules, scoring, and state transitions
Pybinder/         pybind11 bindings
pymahjong/        Python APIs, environments, and utilities
web/              Browser UI and replay tooling
docs/             Sphinx documentation source
test/             Native test executable
ThirdParty/       Vendored dependencies
```

## What to Run Before Opening a PR

Run the checks that match your change surface.

### Core Python and binding checks

```bash
python -c "from pymahjong.test import test_shanten_regressions, test; test_shanten_regressions(); test()"
```

### Documentation build

```bash
cd docs
make html
```

### Native build smoke test

```bash
mkdir -p build
cd build
cmake ..
cmake --build . -j
```

If your change touches the web client, include the exact manual or automated checks you ran in the PR description.

## Coding Expectations

### Python

- Follow PEP 8.
- Prefer explicit, readable names over compact logic.
- Keep public APIs documented with docstrings.

### C++

- Target C++14 unless the repository is explicitly upgraded.
- Keep ownership and lifetime behavior obvious.
- Add brief comments for non-obvious algorithms or rule edge cases.
- Avoid introducing dependencies for small, self-contained helpers.

### Tests

- Every bug fix should add or update a regression test.
- Prefer deterministic repro cases over only relying on random-play smoke tests.
- If an issue references a specific hand, rule interaction, or replay, turn that into an executable test where possible.

### Documentation

- Update README or docs when changing user-visible workflows or APIs.
- Keep examples runnable and copy-pasteable.

## Pull Request Workflow

- Open PRs against `master`.
- Use a focused branch name such as `fix/exact-shanten-search` or `docs/update-demo-guide`.
- Keep commits scoped and intentional.
- Include the motivation, user impact, and validation steps in the PR body.
- Link the relevant issue using `Fixes #...` or `Refs #...` where appropriate.

Draft PRs are welcome when you want early feedback on direction or API shape.

## Reporting Bugs

Good bug reports usually include:

- pymahjong version
- Python version and OS
- A minimal reproduction
- Expected behavior
- Actual behavior
- Logs, screenshots, or replay data if relevant

Use the issue templates when possible so maintainers get the right context up front.

## Security

For sensitive security reports, do not open a public issue. Follow [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be released under the [Apache License 2.0](LICENSE).

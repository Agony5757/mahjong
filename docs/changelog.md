# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] - 2026-04-30

### Fixed
- `get_scores()` binding missing in pybind11 (was causing `AttributeError` in `web/game_manager.py`)
- `seed` attribute assignment fixed: use `set_seed()` instead of direct member access
- All `to_string()` methods returning `bytes` instead of `str` (pybind11 `py::bytes` → `py::str`)
- CI workflow test invocation broken after `test()` removal from public API
- `import pymahjong` failing in environments without torch (lazy-load RL model imports)

### Changed
- Established clean public `__all__` API surface: 36 symbols, explicit imports, no wildcard pollution
- Added `__version__` from setuptools-scm build-time injection
- `test()` moved to internal `pymahjong.test` module (not part of public API)
- Python submodules now export `__all__`
- Renamed `paipu_replay_1` → `paipu_replay_summary`
- Removed deprecated `env_mahjong.py` (superseded by `env_pymahjong.py`)

### Added
- `docs/cpp_api/` — C++ engine API reference documentation
- `docs/advanced/state_machine.md` — C++ engine phase/state machine reference
- `docs/web_frontend.md` — Web frontend (FastAPI + Canvas) documentation
- C++ `ScoreTable`, `YakuDetector`, `FuCalculator` modules
- `web/` — Web UI for human-vs-AI, 4-AI battle, and paipu replay

## [1.1.0] - 2024-XX-XX

### Added
- Modern build system using `pyproject.toml` with scikit-build-core
- cibuildwheel GitHub Actions for cross-platform wheel building
- Trusted publishing to PyPI
- Sphinx documentation with Furo theme
- GitHub Pages documentation deployment

### Changed
- Python version support updated to 3.10-3.14 (dropped 3.8, 3.9)
- pybind11 is now a build dependency instead of vendored
- Build backend changed from setup.py to scikit-build-core

### Removed
- Vendored pybind11 from ThirdParty/

## [1.0.5] - 2024-01-XX

### Changed
- Migrated from gym to gymnasium for modern compatibility
- Fixed CI workflow for compatibility with modern GitHub Actions runners

## [1.0.4] - 2023-XX-XX

### Added
- Pretrained VLOG models (CQL and BC variants)
- Offline dataset for training

### Fixed
- Various bug fixes and performance improvements

## [1.0.0] - 2022-XX-XX

### Added
- Initial release
- Complete Japanese Riichi Mahjong rules implementation
- Multi-agent environment (`MahjongEnv`)
- Single-agent environment (`SingleAgentMahjongEnv`)
- Observation encoding (executor and oracle)
- Paipu replay system
- C++ backend with pybind11 bindings

[1.1.2]: https://github.com/Agony5757/mahjong/compare/v1.1.1...v1.1.2
[1.1.0]: https://github.com/Agony5757/mahjong/compare/v1.0.5...v1.1.0
[1.0.5]: https://github.com/Agony5757/mahjong/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/Agony5757/mahjong/compare/v1.0.0...v1.0.4
[1.0.0]: https://github.com/Agony5757/mahjong/releases/tag/v1.0.0

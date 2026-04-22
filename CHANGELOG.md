# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-04-XX

### Added
- Modern build system using `pyproject.toml` with scikit-build-core
- cibuildwheel GitHub Actions for cross-platform wheel building
- Trusted publishing to PyPI via OIDC
- Sphinx documentation with Furo theme
- GitHub Pages documentation deployment via GitHub Actions
- Python 3.13 and 3.14 support

### Changed
- Python version support updated to 3.10-3.14 (dropped 3.8, 3.9)
- pybind11 is now a build dependency instead of vendored
- Build backend changed from custom setup.py to scikit-build-core
- CI workflow now tests multiple Python versions (3.10-3.13)

### Removed
- Vendored pybind11 from ThirdParty/ directory
- Complex CMakeBuild class from setup.py (now a shim)

## [1.0.5] - 2024-01-XX

### Changed
- Migrated from gym to gymnasium for modern compatibility
- Fixed CI workflow for compatibility with modern GitHub Actions runners

## [1.0.4] - 2023-XX-XX

### Added
- Pretrained VLOG models (CQL and BC variants)
- Offline dataset for training available on GitHub Releases

### Fixed
- Various bug fixes and performance improvements

## [1.0.0] - 2022-04-XX

### Added
- Initial release
- Complete Japanese Riichi Mahjong rules implementation
- Multi-agent environment (`MahjongEnv`)
- Single-agent environment (`SingleAgentMahjongEnv`)
- Observation encoding with executor (93 channels) and oracle (18 channels) views
- Paipu replay system for Tenhou.net game records
- High-performance C++ backend with pybind11 Python bindings
- Pretrained opponent models for single-agent mode

### Research
- Introduced in ICLR 2022 paper: "Variational Oracle Guiding for Reinforcement Learning"

[1.1.0]: https://github.com/Agony5757/mahjong/compare/v1.0.5...v1.1.0
[1.0.5]: https://github.com/Agony5757/mahjong/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/Agony5757/mahjong/compare/v1.0.0...v1.0.4
[1.0.0]: https://github.com/Agony5757/mahjong/releases/tag/v1.0.0

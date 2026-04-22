# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.1.0]: https://github.com/Agony5757/mahjong/compare/v1.0.5...v1.1.0
[1.0.5]: https://github.com/Agony5757/mahjong/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/Agony5757/mahjong/compare/v1.0.0...v1.0.4
[1.0.0]: https://github.com/Agony5757/mahjong/releases/tag/v1.0.0

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2025-08-07

### Added

- Legacy TCP socket plugin for backward compatibility (#2).
- Joystick toggle action (#3).
- Dummy controller module to simulate table movements.
- Added `CONTRIBUTING.md` file for project contribution guidelines.

### Changed

- Updated PySide6 dependency from 6.8.3 to 6.9.1
- Refactored codebase to fully comply with Python PEP 8 style guidelines.
- Renamed this `changelog` to `CHANGELOG.md`

## [0.3.0] - 2025-03-28

### Changed

- Migrated from PyQt5 to PySide6 (#1).

## [0.2.0] - 2024-03-14

### Added

- SCPI socket plugin.

## [0.1.0] - 2024-03-14

### Added

- Support for Hydra controller.
- Support for Corvus controller.

[unreleased]: https://github.com/hephy-dd/table-control/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/hephy-dd/table-control/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/hephy-dd/table-control/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/hephy-dd/table-control/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hephy-dd/table-control/releases/tag/v0.1.0

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Copy current position menu action and button (#35).

### Changed

- Run Ruff with default rules and fix all reported issues (#33).
- Migrated to Python 3.14 (#34).

## [0.8.1] - 2026-01-28

### Fixed

- Reset calibration lock button state after unlock timout (#27).

## [0.8.0] - 2026-01-28

### Added

- Added lock button in calibration tab and added notice (#27).

### Fixed

- Increased the precision of stored position values to 6 decimal places (#25).

## [0.7.0] - 2026-01-27

### Added

- Restore-to-defaults buttons for preference input forms (#16).
- Support for ASRL/COM resources (#21).
- Tests for the `core.utils` module.

### Changed

- Increased the precision of position values to 6 decimal places in the UI and SCPI responses (#19).
- Changed the legacy SCPI default port to 6345 (#18).

### Fixed

- Legacy SCPI now returns the axis moving state correctly in `PO?` (#17).
- Legacy SCPI now terminates messages with `\r\n` (#20).
- Clear the Corvus buffer after setting `0 mode` (#23).
- Added missing modules and libraries to the PyInstaller Windows executable.

## [0.6.0] - 2025-11-25

### Changed

- SCPI compliant comma separated argument lists (#11).
- Renamed SCPI command `ZLIMit:ENABled?"` to compliant form `ZLIMit:ENABle?` (#11).
- Set application organization name from `HEPHY` to `MBI` (previous settings will be lost).
- Switched to hatchling build backend (#12).

### Removed

- Obsolete setuptools `MANIFEST.in` (#12).

### Fixed

- Disappearing icons on PyInstaller Windows executable (#14).

## [0.5.0] - 2025-09-01

### Added

- User managed positions (#8).
- Communication indicator in dashboard (#9).

### Changed

- Refactored table controller logic (#10).

### Fixed

- TCP socket line buffering (#5).

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

[unreleased]: https://github.com/hephy-dd/table-control/compare/v0.8.1...HEAD
[0.8.1]: https://github.com/hephy-dd/table-control/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/hephy-dd/table-control/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/hephy-dd/table-control/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/hephy-dd/table-control/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/hephy-dd/table-control/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/hephy-dd/table-control/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/hephy-dd/table-control/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/hephy-dd/table-control/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hephy-dd/table-control/releases/tag/v0.1.0

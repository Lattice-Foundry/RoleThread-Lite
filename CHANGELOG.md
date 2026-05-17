# Changelog

All notable changes to LoreForge Lite will be documented here.

LoreForge Lite is currently pre-V1. Entries before the first public V1 release may be summarized rather than exhaustive.

Future version bumps should update this file with concise user-facing or maintainer-facing notes.

## [Unreleased]

### Added

### Changed

### Fixed

### Internal

## [1.3.67] - 2026-05-16

### Added

- Added a PyInstaller one-folder spec for the Windows launcher bundle prototype.
- Added a real bundle build script for producing `installer/windows/dist/LoreForgeLauncher/`.
- Documented bundled normal/webapp smoke-test workflows.

### Internal

- Added bundled-mode launcher command/runtime detection for PyInstaller.
- Added launcher unit coverage for frozen app-root, runtime, and command construction.

## [1.3.66] - 2026-05-16

### Added

- Added a dev helper script for running the Windows launcher prototype.
- Added launcher safeguards for missing app roots, occupied Streamlit ports, and subprocess startup failures.
- Documented launcher smoke-test steps for normal and webapp preference modes.

### Internal

- Expanded launcher unit coverage for port checks, app-root validation, and failure logging.

## [1.3.65] - 2026-05-16

### Added

- Added the first Windows launcher source prototype for future PyInstaller wrapping.
- Added unit coverage for launcher preference handling, command construction, runtime selection, and logging.

### Internal

- Documented launcher responsibilities and future graceful shutdown expectations in the Windows installer plan.

## [1.3.64] - 2026-05-16

### Added

- Added the initial Windows installer and packaging skeleton under `installer/windows/`.
- Documented the PyInstaller one-folder and Inno Setup packaging plan.
- Added placeholder Windows build scripts for future bundle and installer passes.

### Internal

- Added gitignore rules for future generated packaging artifacts.

## [1.3.63] - 2026-05-16

### Added

- Added a lighter FAQ note about LoreForge Lite's intentionally cautious design philosophy.

## [1.3.62] - 2026-05-16

### Added

- Added this changelog as the release-history home for future pre-V1 and V1 updates.

### Changed

- Clarified legacy tag migration, navigation alias, and built-in taxonomy fallback rationale in code comments.
- Refined a few Help headings away from older scene-oriented wording where the generalized interaction model fits better.

### Internal

- Verified remaining startup migrations are idempotent compatibility checks.
- Kept transitional navigation aliases for stored session/page compatibility.
- Kept built-in tag fallback helpers as pure startup/test fallback utilities.

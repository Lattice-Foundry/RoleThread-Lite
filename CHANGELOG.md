# Changelog

All notable changes to LoreForge Lite will be documented here.

LoreForge Lite is currently pre-V1. Entries before the first public V1 release may be summarized rather than exhaustive.

Future version bumps should update this file with concise user-facing or maintainer-facing notes.

## [Unreleased]

### Added

### Changed

### Fixed

### Internal

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

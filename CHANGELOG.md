# Changelog

All notable changes to RoleThread Lite will be documented here.

RoleThread Lite is currently pre-V1. Entries before the first public V1 release may be summarized rather than exhaustive.

Future version bumps should update this file with concise user-facing or maintainer-facing notes.

## [Unreleased]

### Added

### Changed

### Fixed

### Internal

## [1.3.87] - 2026-05-17

### Changed

- Hardened Windows installer builds so the PyInstaller bundle is rebuilt by default before Inno packaging.
- Added installer build validation that rejects stale bundles when bundled app version metadata does not match the source tree version.

## [1.3.86] - 2026-05-17

### Changed

- Added a Start Menu uninstall shortcut and clarified that local data removal prompts are available through the real uninstall path, not setup maintenance reruns.
- Updated installer documentation for normal uninstall, local data removal, developer clean uninstall, and cloud backup preservation.

## [1.3.85] - 2026-05-17

### Fixed

- Restored safe duplicate Edge browser closure for manual `-- webapp` runs by matching exact top-level browser window handles after confirming an app window exists.
- Added dev diagnostics explaining duplicate-browser cleanup window candidate decisions.

## [1.3.84] - 2026-05-17

### Fixed

- Restored safer manual `-- webapp` duplicate-browser cleanup by preferring exact window-handle closure and removing exact-PID process termination fallback.
- Tightened Edge cleanup gates so process-based cleanup requires a confirmed app-window candidate and visible normal Edge browser title.

## [1.3.83] - 2026-05-17

### Added

- Added uninstall-time prompts for optional local RoleThread data removal and developer clean uninstall testing.

### Changed

- Updated the Windows uninstaller to preserve user data by default, warn when RoleThread is still running, and keep cleanup scoped to RoleThread-owned local roots.

## [1.3.82] - 2026-05-17

### Added

- Added a default-enabled Windows installer option to launch RoleThread Lite as an Edge webapp.

### Changed

- Updated the launcher to merge installer launch-mode seeds into DB-backed preferences before selecting normal or webapp launch mode.

## [1.3.81] - 2026-05-17

### Added

- Added the first Inno Setup installer prototype for packaging the PyInstaller bundle into a Windows setup executable.

### Changed

- Replaced the installer scaffold script with a real Inno compiler wrapper that validates prerequisites and reports the generated setup path.

## [1.3.80] - 2026-05-17

### Added

- Added a dry-run-first developer cleanup script for resetting RoleThread app data and workspace folders during Windows installer testing.

### Changed

- Documented developer cleanup usage and safety guards in the Windows installer notes.

## [1.3.79] - 2026-05-17

### Added

- Added the first Windows launcher-owned shutdown lifecycle with health checks, local token-protected shutdown requests, and terminate/kill fallback handling.

### Changed

- Documented launcher lifecycle behavior, webapp shutdown monitoring, and normal-browser detection limitations.

## [1.3.78] - 2026-05-17

### Changed

- Refined `For Developers` Help pages toward a more technical architecture/contributor documentation style.
- Moved RoleThread Studio Vision into the developer Help section alongside Lite/Studio boundary guidance.

## [1.3.77] - 2026-05-17

### Added

- Added developer Help articles for build packaging, Windows launcher architecture, contribution expectations, and Lite/Studio boundaries.

### Changed

- Completed the foundational `For Developers` Help section with packaging, launcher, and contribution guidance.

## [1.3.76] - 2026-05-17

### Changed

- Added explicit Python naming, PEP 8, and side-effect naming guidance to developer terminology docs.
- Refined repeated local-first wording across developer Help pages so the concept remains intentional without becoming repetitive.

## [1.3.75] - 2026-05-17

### Added

- Added developer Help articles for data safety, testing, naming, and UI/theme philosophy.

### Changed

- Expanded the `For Developers` Help section with engineering and design conventions for future contributors.

## [1.3.74] - 2026-05-17

### Added

- Added a `For Developers` Help section.
- Added developer Help articles for codebase architecture, layer boundaries, and platform support philosophy.

### Changed

- Moved Developer Launch Flags from Reference into the new developer Help section and clarified diagnostics/webapp launch wording.

## [1.3.73] - 2026-05-17

### Added

- Added a Help reference article explaining the RoleThread Studio vision and the Lite/Studio product split.

### Changed

- Clarified existing Studio references in Help, FAQ, and README wording.

## [1.3.72] - 2026-05-17

### Changed

- Switched the Windows PyInstaller launcher bundle to windowed/no-console mode.
- Documented windowed bundle smoke testing and launcher-log diagnostics.

### Internal

- Expanded launcher logging with app version and bundled-mode context for no-console troubleshooting.

## [1.3.71] - 2026-05-16

### Added

- Added a Help article explaining the finalized V1 default tag taxonomy, including every built-in category and tag.

### Changed

- Cleaned stale prototype-style tag examples from Help docs and reinforced custom tags as the place for domain-specific vocabulary.

## [1.3.70] - 2026-05-16

### Changed

- Verified public Help, FAQ, README, and installer documentation use RoleThread naming consistently.
- Polished the tag lifecycle help examples to keep custom tag guidance broad and neutral.

## [1.3.69] - 2026-05-16

### Internal

- Verified code comments, docstrings, developer docs, installer notes, scripts, tests, and changelog text use RoleThread naming consistently.
- Confirmed tracked-source developer text has no remaining retired-brand references or transition-branding notes.

## [1.3.68] - 2026-05-16

### Changed

- Updated product branding to RoleThread across runtime code, launcher sources, platform defaults, and test expectations.
- Renamed branded metadata helpers, launcher source/spec files, generated bundle names, app-data defaults, environment variables, and runtime-visible product strings.

### Internal

- Updated bundled-launcher tests and runtime metadata constants for RoleThread naming.

## [1.3.67] - 2026-05-16

### Added

- Added a PyInstaller one-folder spec for the Windows launcher bundle prototype.
- Added a real bundle build script for producing `installer/windows/dist/RoleThreadLauncher/`.
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

- Added a lighter FAQ note about RoleThread Lite's intentionally cautious design philosophy.

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


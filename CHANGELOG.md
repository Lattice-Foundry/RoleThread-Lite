# Changelog

All notable changes to RoleThread Lite will be documented here.

RoleThread Lite is currently pre-V1. Entries before the first public V1 release may be summarized rather than exhaustive.

Future version bumps should update this file with concise user-facing or maintainer-facing notes.

## [Unreleased]

### Added

### Changed

- Completed the LitLaunch-first documentation transition for user, FAQ,
  developer, packaging, installer, diagnostics, and release-gate docs.
- Clarified the current runtime model: RoleThread owns product/data behavior,
  LitLaunch owns runtime/platform behavior, `litlaunch.toml` is the source
  launch contract, and the installed shortcut uses the packaged launcher.
- Historical changelog entries below may still mention earlier launcher,
  webapp, or browser-adapter prototypes; those entries describe past
  implementation stages, not the current architecture.

### Fixed

### Internal

## [1.4.45] - 2026-05-18

### Added

- Expanded the Planned for Version 2 reference article with backup recovery and lightweight dataset history direction.

## [1.4.44] - 2026-05-18

### Added

- Added a public Planned for Version 2 reference article covering Lite roadmap direction, runtime goals, validation/data generation focus areas, and product boundaries.

## [1.4.43] - 2026-05-18

### Changed

- Added a backend-to-launcher log bridge for cloud-sync shutdown diagnostics in packaged/no-console runs.
- Moved launcher log path handling into shared core helpers so app closeout hooks can append plain-text diagnostics safely.
- Logged cloud-sync closeout timeout warnings before launcher fallback termination.

## [1.4.42] - 2026-05-18

### Changed

- Added explicit staged cloud backup sync closeout during launcher-triggered graceful shutdown.
- Added cloud-sync shutdown status messages and restrained gold launcher-console styling for cloud sync labels.
- Propagated launcher diagnostic mode into app shutdown closeout so debug runs can report cloud sync skip/success/failure details.

## [1.4.41] - 2026-05-18

### Changed

- Updated For Developers launch and packaging docs for the launcher-owned managed webapp architecture.
- Removed stale developer references to raw Streamlit webapp flags, old Edge debug flags, installer runtime selection, and browser cleanup flows.
- Clarified the Windows packaged launcher, shared lifecycle, browser adapter, shutdown, and port-release boundaries.

## [1.4.40] - 2026-05-18

### Changed

- Reorganized FAQ entries into clearer topic categories for launching, datasets, Data Generation, AI training, privacy, and troubleshooting.
- Added concise FAQ guidance for the managed launcher-owned webapp path and source diagnostics.
- Refreshed FAQ related Help links and removed stale launcher/debug/reset references.

## [1.4.39] - 2026-05-18

### Changed

- Updated public Help launch/install guidance for the managed launcher-owned webapp architecture.
- Removed stale public Help references to raw Streamlit webapp flags and old Edge debug flows.

## [1.4.38] - 2026-05-18

### Fixed

- Made launcher-owned webapp close monitoring target the newly launched Edge app HWND instead of any pre-existing RoleThread-shaped Edge window.

## [1.4.37] - 2026-05-18

### Fixed

- Restored the missing `pathlib.Path` import used by app startup dataset restore logic.

## [1.4.36] - 2026-05-18

### Changed

- Removed the obsolete Reset Webapp Browser State tooling and its Edge profile cleanup code.
- Removed pending browser-state reset handling from the managed launcher lifecycle.
- Cleaned stale webapp-era tests and app comments now that launcher-owned webapp mode is canonical.

## [1.4.35] - 2026-05-18

### Changed

- Removed legacy app-owned raw Streamlit webapp launch handling from `app.py`.
- Removed obsolete `edge-debug` / `webapp-debug` app flag diagnostics and duplicate-browser cleanup tests.
- Kept webapp lifecycle ownership in `launch.py` and the packaged launcher while preserving normal `streamlit run app.py` source workflows.

## [1.4.34] - 2026-05-18

### Changed

- Removed the Windows installer webapp-mode selection checkbox and installer seed file handling.
- Made packaged RoleThread Lite launches always use the managed launcher-owned webapp lifecycle.
- Kept source/developer browser and legacy raw Streamlit webapp workflows available outside packaged installs.

## [1.4.33] - 2026-05-18

### Changed

- Prepared the Windows installer/package launch path for beta testing on the shared launcher lifecycle, runtime helper, and Edge browser-adapter architecture.
- Added packaging coverage to ensure the PyInstaller spec bundles the shared core launcher modules used by `RoleThreadLauncher.exe`.

## [1.4.32] - 2026-05-18

### Changed

- Introduced the first browser adapter boundary with Microsoft Edge as the initial managed-webapp adapter.
- Moved Edge app-mode command construction, availability checks, launch execution, and Edge version recording out of the Windows packaged launcher adapter.
- Kept HWND monitoring, pending browser-state reset handling, and Windows packaged launcher lifecycle wiring unchanged.

## [1.4.31] - 2026-05-18

### Changed

- Moved shared launcher runtime command, URL, launch-mode, and command-formatting helpers out of the Windows packaged launcher adapter.
- Kept the Windows launcher focused on packaged path resolution, Edge launch, HWND monitoring, process ownership, and installer-specific behavior.
- Added launcher runtime tests covering loopback webapp commands, normal browser commands, bundled adapter commands, and local lifecycle URLs.

## [1.4.30] - 2026-05-18

### Changed

- Bound managed launcher-owned webapp Streamlit runs to `127.0.0.1` with `--server.address 127.0.0.1` to keep Lite local-machine-only by default.
- Kept normal browser/dev Streamlit command construction unchanged while preserving managed webapp headless startup and loopback health/browser URLs.

## [1.4.29] - 2026-05-18

### Changed

- Tuned launcher console ANSI colors to use a darker Streamlit-blue lifecycle label and a slightly darker, greener mint launcher prefix.

## [1.4.28] - 2026-05-18

### Changed

- Restored visible launcher lifecycle console status output for managed `launch.py --webapp` runs while keeping extra command/config details behind `--debug`.

## [1.4.27] - 2026-05-18

### Changed

- Added restrained ANSI styling for launcher debug/status console output, with mint launcher prefixes and Streamlit-blue lifecycle labels.
- Kept launcher status text plain on non-ANSI terminals and preserved unstyled lifecycle wording for tests and diagnostics.

## [1.4.26] - 2026-05-18

### Changed

- Moved launcher-owned backend/browser/shutdown orchestration into shared core lifecycle code.
- Reduced the Windows packaged launcher to an adapter that supplies platform-specific process, Edge, HWND, shutdown, and logging callables.
- Added shared lifecycle tests covering orchestration ordering and failure handling.

## [1.4.25] - 2026-05-18

### Changed

- Moved legacy app-owned webapp orchestration out of `app.py` into an explicitly marked compatibility helper.
- Extracted shared launcher lifecycle status helpers for dev/manual and packaged lifecycle convergence.
- Kept the canonical `launch.py --webapp` path and packaged launcher behavior on the same lifecycle orchestration path.

## [1.4.24] - 2026-05-18

### Changed

- Strengthened canonical `python launch.py --webapp` debug diagnostics around launcher-owned startup, health readiness, Edge app launch, HWND monitoring, shutdown, and port release.
- Added a concise legacy warning for raw `streamlit run app.py -- webapp` compatibility mode that points beta testers to `python launch.py --webapp`.

## [1.4.23] - 2026-05-18

### Added

- Added root-level `launch.py` as the canonical source/dev launcher entrypoint.
- Added `python launch.py --webapp` support for launcher-owned headless Streamlit startup, pending browser-state reset consumption, Edge app-mode launch, HWND monitoring, and owned-backend shutdown through the existing lifecycle.

### Changed

- Updated shared non-frozen webapp command construction to start Streamlit with `--server.headless true`.

## [1.4.22] - 2026-05-18

### Fixed

- Extended pending Reset Webapp Browser State handling to the manual app-owned `streamlit run app.py -- webapp` startup path before Edge app launch.

## [1.4.21] - 2026-05-18

### Fixed

- Changed Reset Webapp Browser State to schedule a safe pending reset from Settings and run it before the next launcher-managed Edge webapp window opens.
- Preserved the live Edge-profile safety guard while making the reset workflow usable from inside the Edge webapp session.

## [1.4.20] - 2026-05-18

### Changed

- Migrated public Help related-article links from temporary markdown sections into the Help registry.
- Removed temporary public Help `Related Articles` sections after preserving their curated link order in the UI relationship system.

## [1.4.19] - 2026-05-18

### Added

- Added persistent local Microsoft Edge version history for launcher and webapp diagnostics.
- Added Edge version history reporting inside edge-debug/webapp-debug Settings diagnostics.

## [1.4.18] - 2026-05-18

### Added

- Added a Settings troubleshooting tool to reset targeted Microsoft Edge webapp browser state for RoleThread localhost workflows.
- Added browser-state reset utilities that preserve datasets, preferences, cookies, passwords, global Edge cache, and unrelated browser data.

## [1.4.17] - 2026-05-18

### Fixed

- Restored manual Edge webapp duplicate-browser cleanup when Edge reports the app-looking window with normal `--single-argument` process metadata.
- Kept duplicate browser cleanup HWND-only and guarded by separate normal-browser evidence before closing any Edge window.

## [1.4.16] - 2026-05-17

### Added

- Completed the AI Training Fundamentals educational arc with articles on LoRA/fine-tuning readiness, synthetic data, dataset scaling, behavioral bias, realistic tuning expectations, and creator ownership.
- Added FAQ entries for training preparation, synthetic data tradeoffs, dataset maintenance, behavioral blind spots, tuning expectations, and long-term creator control.

## [1.4.15] - 2026-05-17

### Added

- Expanded AI Training Fundamentals with practical roleplay dataset craftsmanship articles covering dataset mistakes, dialogue/narration balance, character drift, AI-assisted creation workflows, and validation.
- Added FAQ entries for roleplay dataset quality, synthetic data review, narration balance, character drift, and validation.

## [1.4.14] - 2026-05-17

### Added

- Added the AI Training Fundamentals Help category covering RoleThread's purpose, fine-tuning basics, LoRAs, prompting, dataset quality, and privacy-conscious local creative workflows.
- Added FAQ entries explaining the 80/20 workflow, conversational training data, prompting limits, and local-first dataset ownership.

## [1.4.13] - 2026-05-17

### Changed

- Merged Data Generation into the Output workflow menu.
- Removed the standalone Tools menu category.

## [1.4.12] - 2026-05-17

### Added

- Added foundational Data Generation Help documentation covering beta positioning, provider-agnostic external AI workflows, and deterministic prompt compiler architecture.
- Added Data Generation FAQ entries for direct generation, API keys, provider behavior, beta status, and cross-provider output differences.

## [1.4.11] - 2026-05-17

### Changed

- Moved Data Generation tone guidance into DB-backed conditional chunks.
- Added production tone-specific prompt instructions for the Conversation Scenario Generator.

## [1.4.10] - 2026-05-17

### Changed

- Moved Data Generation style guidance into DB-backed conditional chunks.
- Added production style-specific prompt instructions for the Conversation Scenario Generator.

## [1.4.9] - 2026-05-17

### Changed

- Improved Data Generation style and tone rendering with semantic instruction text.
- Refined downloadable output delivery instructions to prohibit extra explanation.

## [1.4.8] - 2026-05-17

### Fixed

- Split Data Generation output delivery instructions into conditional DB-backed chunks.
- Conversation Scenario Generator prompts now include only the selected output delivery branch.

## [1.4.7] - 2026-05-17

### Changed

- Replaced Data Generation placeholder chunks with Template 01 production prompt content.
- Updated the Conversation Scenario Generator to compile real ChatML JSONL generation instructions.

## [1.4.6] - 2026-05-17

### Internal

- Switched generation prompt assembly to load chunks from the DB-backed generation registry.
- Added lightweight placeholder rendering while preserving existing placeholder prompt output.

## [1.4.5] - 2026-05-17

### Internal

- Added read-only DB-backed generation registry query helpers.
- Added deterministic conditional chunk resolution support for future DB-backed generation compilation.

## [1.4.4] - 2026-05-17

### Internal

- Seeded DB-backed generation placeholder chunks and deterministic template chunk mappings.
- Prepared future DB-backed generation compiler integration without changing current compiler behavior.

## [1.4.3] - 2026-05-17

### Internal

- Added SQLAlchemy foundation models for future generation prompt chunk storage.
- Prepared database-backed generation template/chunk ordering and conditional mapping architecture.

## [1.4.2] - 2026-05-17

### Changed

- Polished the Data Generation prompt preview with reusable JSON-preview-inspired code styling.
- Added one-click copy support for compiled generation prompts without changing prompt compiler output.

## [1.4.1] - 2026-05-17

### Added

- Added the first Output > Data Generation UI for compiling placeholder external-generation prompts from structured settings.
- Added a framework-independent generation service between the Streamlit page and the core prompt compiler.

## [1.4.0] - 2026-05-17

### Added

- Added the initial core `generation` package for deterministic external data-generation prompt compilation.
- Added the conversation scenario generation config, template registry, reusable placeholder chunks, compiler, and pure unit coverage.

## [1.3.98] - 2026-05-17

### Changed

- Expanded developer installer and launcher architecture documentation around bundled runtime boundaries, HWND monitoring, launcher ownership, stale bundle protection, and port-release semantics.
- Removed the obsolete developer clean uninstall path and cleanup script; clean installer testing now uses the normal uninstall data-removal option.

## [1.3.97] - 2026-05-17

### Added

- Added a first-position Help article for installing RoleThread Lite, covering the Windows beta setup installer, manual Windows/Linux/macOS workflows, and uninstall behavior.
- Added a FAQ entry about the delightfully excessive Streamlit/webapp/installer stack.

### Changed

- Polished user-facing install, README, OS compatibility, and installer docs to match the current beta installer and Windows Edge webapp lifecycle.

## [1.3.96] - 2026-05-17

### Changed

- Added one more foreground restore attempt for the Inno Setup wizard after UAC and documented the Windows taskbar fallback if setup appears behind other windows.

## [1.3.95] - 2026-05-17

### Changed

- Removed the visible Settings webapp launch toggle while preserving installer/launcher preference plumbing.
- Updated installer webapp option wording and added a lightweight wizard foreground restore during setup startup.

## [1.3.94] - 2026-05-17

### Changed

- Removed a stale PyInstaller data reference to an obsolete logo asset path.
- Cleaned installer documentation around bundled webapp startup ownership and port-release validation semantics.

## [1.3.93] - 2026-05-17

### Fixed

- Replaced the installed launcher webapp-window monitor's PowerShell HWND probe with direct Win32 window enumeration so packaged no-console builds can reliably observe the Edge app window.
- Prevented the launcher from tearing down the backend during frontend startup when the Edge app window has already opened.

## [1.3.92] - 2026-05-17

### Fixed

- Moved the initial installed Edge webapp open into the Windows launcher after Streamlit health succeeds, allowing headless bundled sessions to create the first browser session.
- Marked launcher-started webapp sessions as externally managed so the app does not relaunch Edge during Streamlit reruns.

## [1.3.91] - 2026-05-17

### Fixed

- Added bundled webapp startup breadcrumbs to launcher logs so installed Edge launch loops can be diagnosed from `%LOCALAPPDATA%\RoleThread\logs\launcher.log`.
- Made launcher webapp monitor timeouts terminate only the launcher-owned backend subprocess instead of leaving port `8501` occupied.
- Added an environment-backed webapp launch guard so Streamlit reruns cannot bypass the process-level Edge launch guard if module state is reloaded.

## [1.3.90] - 2026-05-17

### Fixed

- Started bundled webapp-mode launcher sessions with Streamlit headless so installed builds do not open a normal browser window before app-owned Edge webapp launch.
- Added stable HWND selection for launcher app-window monitoring so transient startup handles are ignored before shutdown lifecycle tracking begins.

## [1.3.89] - 2026-05-17

### Fixed

- Improved Windows launcher webapp shutdown monitoring to track the exact Edge app-window HWND and request backend shutdown after that handle closes.
- Added launcher port-release logging so stale backend listeners on port `8501` are visible after shutdown attempts.

## [1.3.88] - 2026-05-17

### Changed

- Consolidated Edge launch debug details into one `edge-debug` / `webapp-debug` diagnostics section.
- Renamed the Start Menu uninstall shortcut to **RoleThread Uninstaller**.

## [1.3.87] - 2026-05-17

### Changed

- Hardened Windows installer builds so the PyInstaller bundle is rebuilt by default before Inno packaging.
- Added installer build validation that rejects stale bundles when bundled app version metadata does not match the source tree version.

## [1.3.86] - 2026-05-17

### Changed

- Added a Start Menu uninstall shortcut and clarified that local data removal prompts are available through the real uninstall path, not setup maintenance reruns.
- Updated installer documentation for normal uninstall, local data removal, and cloud backup preservation.

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

- Added uninstall-time prompts for optional local RoleThread data removal.

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

- Added early installer-test cleanup tooling for resetting RoleThread app data and workspace folders.

### Changed

- Documented installer cleanup usage and safety guards in the Windows installer notes.

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


# RoleThread Tests

This suite protects the shared Python behavior that Lite and future Studio
should both be able to trust.

Current architecture target:

- Lite UI = Streamlit shell
- Shared Python = `core/` + `services/`

## What Is Tested

Current tests cover:

- browser helper calculations in `ui/browser_helpers.py`
- dataset validation, tag filtering, JSONL persistence, merge, and summary helpers in `core/dataset.py`
- tag registry, lifecycle metadata, alias resolution, sidecar, and import/export behavior
- character registry, character mappings, and character sidecar behavior
- load pipeline, working-copy, dataset UUID, and entry UUID behavior
- service-layer mutation workflows in `services/dataset_service.py`
- backup creation, naming, retention, and configured directories in `core/backups.py`
- local preferences and storage path helpers in `core/preferences.py` and `core/storage.py`
- canonical tag normalization and focused archived/imported adoption behavior

## What Is Deferred

Streamlit UI automation is intentionally deferred. The UI is still evolving,
and brittle widget-level tests would slow down useful product iteration.
Prefer pure helper and service tests until a UI flow is stable enough to merit
automation.

Broader end-to-end UI automation, performance/load tests, and installer-level
checks remain deferred. Keep DB, sidecar, lifecycle, and service tests focused
on stable contracts that protect local-first data safety.

## Setup

RoleThread Lite V1 is developed and tested on Python `3.14.5`. Python `3.14.4`
remains the minimum supported V1 runtime. Other runtimes may work, but `3.14.5`
is the official supported V1 runtime.

Windows/dev environment:

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

Linux/macOS manual environment:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Install runtime and test dependencies:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Running Tests

Run the full suite:

```bat
.venv\Scripts\python.exe -m pytest
```

The test configuration keeps pytest temporary files under `.pytest_tmp/` in
the workspace so the release gate does not depend on the user's global Windows
temp directory permissions.

Run one test file:

```bat
.venv\Scripts\python.exe -m pytest dev\tests\unit\test_dataset.py
```

There is also a small Windows helper:

```bat
dev\tools\run_tests.bat
```

## Test Style

Prefer behavior-focused tests over implementation-detail tests. Pure `core/`
helpers and service workflows are the best first targets. Avoid brittle UI
tests, exact wording checks, and heavy mocking unless a boundary truly needs
to be isolated.

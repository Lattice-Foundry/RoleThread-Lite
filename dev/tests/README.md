# LoreForge Tests

This suite protects the shared Python behavior that Lite and future Studio
should both be able to trust.

Current architecture target:

- Lite UI = Streamlit shell
- Shared Python = `core/` + `services/`

## What Is Tested

Current tests cover:

- browser helper calculations in `ui/browser_helpers.py`
- dataset validation, tag filtering, registries, JSONL persistence, merge, and stats in `core/dataset.py`
- service-layer mutation workflows in `services/dataset_service.py`
- backup creation, naming, retention, and configured directories in `core/backups.py`
- local preferences and storage path helpers in `core/preferences.py` and `core/storage.py`
- canonical tag normalization and focused Unsorted/adoption behavior

## What Is Deferred

Streamlit UI automation is intentionally deferred. The UI is still evolving,
and brittle widget-level tests would slow down useful product iteration.
Prefer pure helper and service tests until a UI flow is stable enough to merit
automation.

Broad database and tag-registry tests are still intentionally deferred for now.
The tag system is expected to evolve with soft delete, archives,
migration/rename workflows, unknown-tag repair, validation tooling, and future
metadata integrity work. Keep DB/tag tests focused on contracts that are stable
enough to protect.

## Setup

Install runtime and test dependencies:

```bat
trainer\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Running Tests

Run the full suite:

```bat
trainer\Scripts\python.exe -m pytest
```

Run one test file:

```bat
trainer\Scripts\python.exe -m pytest dev\tests\unit\test_dataset.py
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

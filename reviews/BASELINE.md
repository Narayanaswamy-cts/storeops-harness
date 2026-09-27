# Baseline check status — re-recorded 2026-09-26T18:13:01Z, after sprints 1-2

Python 3.11.16 / fastapi 0.141.1 / starlette 1.7.0 / pydantic 2.13.5

Commands are the brief's section 2.3 verification set. Both flags matter:
  mypy .                   (46 files; bare `mypy` honours packages=["storeops"] -> 37 files, skips tests/)
  pylint src tests --jobs=1 (serial; the parallel default is non-deterministic and drops findings)

ruff check .:  35 errors
mypy .:        Success: no issues found in 46 source files
pylint:        rated at 9.45/10 (23 messages)
pytest:        71 passed in 0.44s
coverage:      97% overall

Remaining known defects (pre-existing, not attributable to a sprint):
  1. 13x TID251 — pyproject bans storeops.modules.alerts unscoped; fires on main.py,
     alerts' own intra-module imports, and conftest.py. Judge Rule 2 by
     test_no_module_imports_the_alerts_package instead.
  2. 14x EM101/EM102 — the scaffold's raise style in create/get/complete and siblings.
  3. 3x RUF100 — dead noqa directives naming non-selected rules.
  4. pylint 6x E0401 + 5x E0611 on 'tests.conftest' — source-roots lists tests/ as a root,
     so tests.conftest is not resolvable as that dotted path.

Resolved during this run:
  - endpoint-surface test passes (reads app.openapi()['paths'])       [sprint 1]
  - pytest-cov added, so section 3.6 coverage thresholds are measurable
  - pylint pinned to jobs=1; score now repeatable (was 9.63/9.67 alternating)
  - harness gates pinned to 'mypy .'; the old bare form never checked tests/

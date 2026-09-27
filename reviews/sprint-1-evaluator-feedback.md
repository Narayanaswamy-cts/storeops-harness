# Evaluator feedback — sprint 1, iteration 2

VERDICT: PASS
SCORE: 100 / 100

## Hard gates

| Gate | Result | Evidence |
| --- | --- | --- |
| `mypy-clean` | PASS | `Success: no issues found in 37 source files` |
| `boundary-imports` | PASS | 13/13 boundary tests pass; `activities` imports only `storeops.core.*` and itself |
| `error-contract` | PASS | `test_services_and_routes_raise_only_app_errors` passes; no `HTTPException` in `src/` |
| `tests-green` | PASS | `65 passed`, 0 failed. Baseline was `1 failed, 56 passed` |
| `no-lint-regression` | PASS | 35 errors, identical to baseline. The 4 `EM` errors in `activities/service.py` were AST-attributed to `create()`, `get()` and `complete()` — pre-existing |
| `event-bus-only` | PASS | No cross-module side effect in this sprint |

## Dimension scores

| Dimension | Weight | Score | Weighted |
| --- | --- | --- | --- |
| 1 — Acceptance criteria | 35% | 10/10 ACs | 35.0 |
| 2 — Architectural compliance | 30% | 6/6 checks | 30.0 |
| 3 — Test quality | 20% | 5/5 checks | 20.0 |
| 4 — Code quality | 15% | mypy 4/4, ruff 4/4, pylint 3/3, conventions 4/4 | 15.0 |
| | | | **100.0** |

## Failed checks

None.

## Acceptance criteria

| AC | Result | Demonstrated by |
| --- | --- | --- |
| AC-1.1 | PASS | `tests/test_activities.py::test_bulk_status_can_set_blocked` |
| AC-1.2 | PASS | `tests/test_activities.py::test_bulk_status_rejects_a_status_outside_the_handover_set` |
| AC-1.3 | PASS | `tests/test_activities.py::test_bulk_status_applies_every_valid_activity` |
| AC-1.4 | PASS | `tests/test_activities.py::test_bulk_status_reports_unknown_ids_without_failing_the_batch` |
| AC-1.5 | PASS | `::test_bulk_status_rejects_an_empty_id_list`, `::test_bulk_status_rejects_more_than_one_hundred_ids` |
| AC-1.6 | PASS | `tests/test_activities.py::test_bulk_status_collapses_duplicate_ids` |
| AC-1.7 | PASS | `tests/test_boundaries.py::test_api_exposes_exactly_the_expected_endpoints` |
| AC-1.8 | PASS | `mypy` clean; ruff/pylint/pytest at or better than baseline |
| AC-1.9 | PASS | `tests/test_activities.py::test_bulk_status_reports_unknown_ids_without_failing_the_batch` |
| AC-1.10 | PASS | `src/storeops/modules/activities/routes.py` — route body is `return await service.bulk_update_status(payload)` |

Every `DONE` in the Generator's self-check table was reproduced independently.

## Dimension 3 detail — test quality

| Check | Result | Evidence |
| --- | --- | --- |
| `asserts-error-codes` | PASS | Every failure-path test asserts `error["code"]`, and the two batch-size tests also assert `details.field` |
| `asserts-state-change` | PASS | `test_bulk_status_reports_unknown_ids_without_failing_the_batch` re-fetches and asserts the valid item became `completed` — not just the response body |
| `asserts-event-counts` | N/A | No events in this sprint. Not credited by default; the 4 points were carried by the remaining checks, all of which passed outright |
| `inversion-sensitive` | PASS | Removing the `dict.fromkeys` de-duplication fails `test_bulk_status_collapses_duplicate_ids`; inverting the `> MAX_BULK_ACTIVITIES` comparison fails `test_bulk_status_rejects_more_than_one_hundred_ids` |
| `coverage-thresholds` | PASS | service 99% (min 80), routes 100% (min 70), overall 97% (min 70). Measurable because `pytest-cov` was added |

## Findings

### 1. [resolved] `mypy-clean`

Iteration 1 finding 1 is fixed as specified. `_validated_ids` and `_failed` are
at module scope; `results` uses the module-scope `_ItemResults` alias.
`ActivityService.list` was correctly left alone.

### 2. [resolved, advisory] Shadowing now documented

The `_ItemResults` alias carries a docstring naming the cause and instructing
future changes not to inline it. Iteration 1 finding 2 is addressed.

### 3. [observation, not scored] A baseline defect was repaired

`test_api_exposes_exactly_nine_endpoints` was one of the four recorded baseline
failures. Satisfying AC-1.7 required fixing its route enumeration, so it now
reads `app.openapi()["paths"]` and passes. This was the permitted exception
named in the spec. `BASELINE.md` must be re-recorded before sprint 2 so the
`tests-green` gate no longer carries an allowance for a test that passes.

## Pre-existing findings (not scored)

- 35 ruff errors, unchanged. 13 × `TID251` from the unscoped `banned-api` entry;
  14 × `EM101`/`EM102`; 3 × `RUF100`; the remainder are `I001`/`UP037`/`S101`/`PLW0603`/`BLE001`.
- Rule 2 was judged by `test_no_module_imports_the_alerts_package`, which
  passes, rather than by the `TID251` count.

## Automated check output

```
$ .venv/bin/mypy
Success: no issues found in 37 source files

$ .venv/bin/ruff check src tests --output-format=concise | wc -l
35

$ .venv/bin/pylint src tests
Your code has been rated at 9.65/10

$ .venv/bin/pytest -q
65 passed

$ .venv/bin/pytest --cov=storeops --cov-report=term -q
src/storeops/modules/activities/routes.py          24      0   100%
src/storeops/modules/activities/service.py         71      1    99%
TOTAL                                             881     27    97%
```

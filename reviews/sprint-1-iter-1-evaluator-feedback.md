# Evaluator feedback — sprint 1, iteration 1

VERDICT: FAIL
SCORE: 92.5 / 100

## Hard gates

| Gate | Result | Evidence |
| --- | --- | --- |
| `mypy-clean` | **FAIL** | `Found 3 errors in 1 file (checked 37 source files)` — all in `modules/activities/service.py` |
| `boundary-imports` | PASS | 13/13 boundary tests pass; `activities` imports only `storeops.core.*` and itself |
| `error-contract` | PASS | `test_services_and_routes_raise_only_app_errors` passes; `grep -rn HTTPException src/` returns nothing |
| `tests-green` | PASS | `65 passed`, 0 failed. Baseline was `1 failed, 56 passed` |
| `no-lint-regression` | PASS | 35 ruff errors, identical to baseline; no new error in any touched file |
| `event-bus-only` | PASS | No cross-module side effect in this sprint; audit events are sprint 3 |

## Dimension scores

| Dimension | Weight | Score | Weighted |
| --- | --- | --- | --- |
| 1 — Acceptance criteria | 35% | 9/10 ACs | 31.5 |
| 2 — Architectural compliance | 30% | 6/6 checks | 30.0 |
| 3 — Test quality | 20% | 5/5 checks | 20.0 |
| 4 — Code quality | 15% | mypy 0/4, ruff 4/4, pylint 3/3, conventions 4/4 | 11.0 |
| | | | **92.5** |

Score is above the 80 threshold. The verdict is `FAIL` solely because an
absolute hard gate failed, per the verdict algorithm in `evaluation-criteria`.

## Failed checks

- `mypy-clean` — src/storeops/modules/activities/service.py:124, :140, :147

## Acceptance criteria

| AC | Result | Demonstrated by |
| --- | --- | --- |
| AC-1.1 | PASS | `tests/test_activities.py::test_bulk_status_can_set_blocked` |
| AC-1.2 | PASS | `tests/test_activities.py::test_bulk_status_rejects_a_status_outside_the_handover_set` |
| AC-1.3 | PASS | `tests/test_activities.py::test_bulk_status_applies_every_valid_activity` |
| AC-1.4 | PASS | `tests/test_activities.py::test_bulk_status_reports_unknown_ids_without_failing_the_batch` |
| AC-1.5 | PASS | `tests/test_activities.py::test_bulk_status_rejects_an_empty_id_list` and `::test_bulk_status_rejects_more_than_one_hundred_ids` |
| AC-1.6 | PASS | `tests/test_activities.py::test_bulk_status_collapses_duplicate_ids` |
| AC-1.7 | PASS | `tests/test_boundaries.py::test_api_exposes_exactly_the_expected_endpoints` |
| AC-1.8 | **FAIL** | mypy regressed from clean to 3 errors |
| AC-1.9 | PASS | `tests/test_activities.py::test_bulk_status_reports_unknown_ids_without_failing_the_batch` |
| AC-1.10 | PASS | `src/storeops/modules/activities/routes.py:78` — single delegating call |

The Generator's self-check table was verified claim by claim. Every `DONE` was
reproduced. AC-1.8 was reported as `NOT DONE` by the Generator and is confirmed
as failing — the self-report is accurate, which is noted in its favour.

## Findings

### 1. [hard gate: mypy-clean] `list[...]` annotations resolve to `ActivityService.list`

`src/storeops/modules/activities/service.py:124`

```python
        results: list[BulkItemResult] = []
```

`src/storeops/modules/activities/service.py:140`

```python
    def _validated_ids(activity_ids: list[str]) -> list[str]:
```

mypy output:

```
:124: error: "list?[str]" has no attribute "__iter__"  [attr-defined]
:140: error: Function "...ActivityService.list" is not valid as a type  [valid-type]
:147: error: Statement is unreachable  [unreachable]
```

`ActivityService` defines a method named `list` at line 48. Within the class
body that binding shadows `builtins.list`, so any `list[...]` annotation in a
method defined after it refers to the method object. The error at :147 is a
consequence, not an independent fault — mypy concluded the guard above it could
not be reached once the annotation was mistyped.

Runtime is unaffected because `from __future__ import annotations` defers
evaluation, which is why all 65 tests pass. `mypy-clean` carries no baseline
allowance, so this fails the sprint.

**Legal alternative.** Move `_validated_ids` and `_failed` to module scope,
where `list` is the builtin, and add a module-level alias for the annotation
that must remain inside the class:

```python
_ItemResults = list[BulkItemResult]   # module scope: `list` is the builtin here
```

then `results: _ItemResults = []` inside the method. Do **not** rename
`ActivityService.list` — it is called from `routes.py` and is outside this
sprint's file scope.

### 2. [dimension 4: conventions, advisory] The shadowing is undocumented

`src/storeops/modules/activities/service.py:48`

The `list` method name is a latent trap for every future method added to this
class. Not scored, and not a reason to fail: renaming it is out of scope. When
the alias above is introduced, its comment should say why it exists so the next
Generator does not remove it as redundant.

## Pre-existing findings (not scored)

- 35 ruff errors, unchanged from baseline. The 4 `EM101`/`EM102` in
  `modules/activities/service.py` lines 52, 77, 84, 88 sit in `create`, `get`
  and `complete` — pre-existing, confirmed against `BASELINE.md`.
- 13 × `TID251` remain, caused by the unscoped `banned-api` entry in
  `pyproject.toml`. Rule 2 was judged by
  `test_no_module_imports_the_alerts_package`, which passes.
- The baseline failure `test_api_exposes_exactly_nine_endpoints` no longer
  exists; it was renamed to `test_api_exposes_exactly_the_expected_endpoints`
  and now passes. `BASELINE.md` should be re-recorded after this sprint is
  archived.

## Automated check output

```
$ .venv/bin/ruff check src tests --output-format=concise | wc -l
35

$ .venv/bin/mypy
src/storeops/modules/activities/service.py:124: error: "list?[str]" has no attribute "__iter__"  [attr-defined]
src/storeops/modules/activities/service.py:140: error: Function "storeops.modules.activities.service.ActivityService.list" is not valid as a type  [valid-type]
src/storeops/modules/activities/service.py:147: error: Statement is unreachable  [unreachable]
Found 3 errors in 1 file (checked 37 source files)

$ .venv/bin/pylint src tests
Your code has been rated at 9.61/10

$ .venv/bin/pytest -q
65 passed

$ .venv/bin/pytest --cov=storeops.modules.activities --cov-report=term-missing -q
src/storeops/modules/activities/models.py          65      0   100%
src/storeops/modules/activities/repository.py      35      1    97%
src/storeops/modules/activities/routes.py          24      0   100%
src/storeops/modules/activities/service.py         71      1    99%
TOTAL                                             197      2    99%
```

Coverage comfortably exceeds the §3.6 thresholds: service 99% (min 80),
routes 100% (min 70).

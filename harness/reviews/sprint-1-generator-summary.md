# Generator summary — sprint 1, iteration 2

Retry driven by `evaluator-feedback.md` finding 1 (hard gate `mypy-clean`).

## AC self-check

| AC | Status | Demonstrated by | Note |
| --- | --- | --- | --- |
| AC-1.1 | DONE | `test_bulk_status_can_set_blocked` | unchanged from iteration 1 |
| AC-1.2 | DONE | `test_bulk_status_rejects_a_status_outside_the_handover_set` | unchanged |
| AC-1.3 | DONE | `test_bulk_status_applies_every_valid_activity` | unchanged |
| AC-1.4 | DONE | `test_bulk_status_reports_unknown_ids_without_failing_the_batch` | unchanged |
| AC-1.5 | DONE | `test_bulk_status_rejects_an_empty_id_list`, `test_bulk_status_rejects_more_than_one_hundred_ids` | unchanged |
| AC-1.6 | DONE | `test_bulk_status_collapses_duplicate_ids` | unchanged |
| AC-1.7 | DONE | `test_api_exposes_exactly_the_expected_endpoints` | unchanged |
| AC-1.8 | **DONE** | `mypy` → `Success: no issues found in 37 source files` | **fixed this iteration** |
| AC-1.9 | DONE | `test_bulk_status_reports_unknown_ids_without_failing_the_batch` | unchanged |
| AC-1.10 | DONE | `routes.py` review | unchanged |

## Files changed this iteration

| File | Layer | Change |
| --- | --- | --- |
| `src/storeops/modules/activities/service.py` | service | Moved `_validated_ids` and `_failed` from static methods to module scope; added `_ItemResults` alias; updated the two call sites and the `results` annotation |

No other file changed. No test changed — the existing 8 tests still cover the
same behaviour, which is the evidence the fix was type-level only.

## What was wrong and why the fix works

`ActivityService` defines a method named `list`. Inside the class body that
shadows `builtins.list`, so `list[BulkItemResult]` and `list[str]` in methods
defined after it resolved to the method object under `mypy --strict`.

`_validated_ids` and `_failed` never needed `self`, so moving them to module
scope puts their annotations where `list` is the builtin again. The one
annotation that must stay inside the class, `results`, now uses the
module-scope alias `_ItemResults`. The alias carries a docstring explaining why
it exists, so it is not removed later as redundant — this addresses the
Evaluator's advisory finding 2.

`ActivityService.list` was **not** renamed. It is called from `routes.py`, which
the Evaluator explicitly placed outside this sprint's scope.

## Automated checks

| Check | Result | vs baseline |
| --- | --- | --- |
| ruff | 35 errors | unchanged. The 4 `EM` errors in this file (now lines 93, 118, 125, 129) are owned by `create()`, `get()` and `complete()` — verified by AST. My raises at lines 62 and 65 assign the message first. |
| mypy | **clean**, 37 files | restored to baseline |
| pylint | 9.65/10 | improved from 9.57 |
| pytest | 65 passed, 0 failed | +9 vs baseline; the known baseline failure is fixed |
| coverage | 97% overall; service 99%, routes 100%, models 100% | §3.6 thresholds met (service min 80, routes min 70, overall min 70) |

## Known gaps

None. All ten acceptance criteria are met.

## Rule compliance

- **Rule 4.** Decision logic is in the service; the route body is one delegating
  call. Moving the helpers to module scope kept them in the service *layer* —
  they are private to the module and are not reachable from `routes.py`.
- **Rule 3.** Batch faults raise `ValidationError`; per-item faults are reported
  inside the 207 envelope with the code taken from `NotFoundError`. No
  `HTTPException`, no new `EM` violation.
- **Rule 1.** No cross-module import. `activities` imports only `storeops.core.*`
  and itself.

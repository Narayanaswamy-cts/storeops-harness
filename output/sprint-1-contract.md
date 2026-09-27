# Sprint 1 contract: Blocked status and the bulk endpoint

## Objective

Add a `blocked` value to `ActivityStatus` and a new endpoint
`PATCH /api/v1/activities/bulk-status` that accepts many activity ids, one target
status and the acting staff member. Apply every activity that exists, report a
per-item result for ids that do not, and return `207` with the per-item results.
Transition legality beyond existence is sprint 2; audit events are sprint 3.

## Acceptance criteria

- **AC-1.1** `ActivityStatus` gains `BLOCKED = "blocked"`. The four existing
  values are unchanged and existing tests still pass.
- **AC-1.2** `PATCH /api/v1/activities/bulk-status` exists and accepts
  `{"activity_ids": [...], "status": "...", "updated_by": "..."}`. Target status
  is restricted to `completed` or `blocked`; any other value is rejected with
  `422` and `code == "validation_failed"`.
- **AC-1.3** With all ids valid and all in `pending`, the response is `207` with
  one result per requested id, in request order, each
  `{"id": ..., "result": "updated"}`, plus `"updated": N` and `"failed": 0`.
  Every named activity has the target status when fetched afterwards.
- **AC-1.4** An unknown id yields `{"id": ..., "result": "failed",
  "error": {"code": "not_found"}}` for that item only. Other items still apply.
- **AC-1.5** An empty `activity_ids` list is rejected with `422`. More than 100
  ids is rejected with `422`, `details.field == "activity_ids"`.
- **AC-1.6** A duplicate id in the request appears exactly once in the response
  and is applied exactly once.
- **AC-1.7** `test_boundaries.py::test_api_exposes_exactly_nine_endpoints` is
  updated to expect the new endpoint, with the count constant retargeted to 10.
  All boundary tests pass.
- **AC-1.8** `ruff check src tests`, `mypy`, `pylint src tests` and `pytest`
  show no regression against `.harness/reviews/BASELINE.md`.
- **AC-1.9** Every new failure path raises an `AppError` subclass. No
  `HTTPException` anywhere.
- **AC-1.10** Deciding whether an id can be applied happens in `service.py`.
  `routes.py` contains no conditional on a domain status value.

## Files in scope

- `src/storeops/modules/activities/models.py`
- `src/storeops/modules/activities/repository.py`
- `src/storeops/modules/activities/service.py`
- `src/storeops/modules/activities/routes.py`
- `tests/test_activities.py`
- `tests/test_boundaries.py`

Creating or modifying any other file requires a recorded reason in
`generator-summary.md`.

## Read scope

- `src/storeops/modules/activities/*.py` (all four)
- `src/storeops/core/errors.py`, `src/storeops/core/pagination.py`
- `tests/conftest.py`, `tests/test_activities.py`, `tests/test_boundaries.py`
- `.harness/reviews/BASELINE.md`

Do not read other modules. This sprint touches `activities` only.

## Applicable rules

| Rule | Risk in this sprint |
| --- | --- |
| **4 — Layer separation** | The per-item result loop is the natural thing to write in `routes.py`. It is a business decision and belongs in `service.py`. This is the sprint's primary risk and has no automated check. |
| **3 — Error contract** | A per-item failure carries an `AppError` code inside a successful `207` envelope. Do not raise for a single bad item, and do not use `HTTPException`. |
| **1 — Module boundary** | No cross-module import is needed. Do not add one. |
| — | `Activity` is `ConfigDict(frozen=True)`. Use `model_copy(update={...})`, then `repository.replace(...)`. Direct assignment raises. |
| — | The endpoint count assertion in `tests/test_boundaries.py` hard-codes both the constant and the sorted list. Update both. |

## Definition of done

- [ ] All ten ACs demonstrable by a named test
- [ ] `ruff` / `mypy` / `pylint` / `pytest` show no regression vs `BASELINE.md`
- [ ] Coverage of the new service code at or above 80%
- [ ] `generator-summary.md` written with the AC self-check table complete

# Sprint 2 contract: Transition rules and per-item failures

## Objective

Sprint 1 applied a target status to any activity that existed. Add the legality
rules: which source statuses may reach `completed` and `blocked`, reported per
item as a `conflict` rather than raised. Set `completed_at` and `completed_by`
when the target is `completed`.

## Acceptance criteria

- **AC-2.1** An activity already in the target status is reported as
  `{"result": "failed", "error": {"code": "conflict"}}` and is not rewritten.
  Its `completed_at` is unchanged.
- **AC-2.2** `cancelled` is terminal. A cancelled activity targeted at
  `completed` or `blocked` reports `code == "conflict"` and does not change.
- **AC-2.3** A `completed` activity targeted at `blocked` reports
  `code == "conflict"`. Completion is terminal for this endpoint.
- **AC-2.4** `blocked` → `completed` is legal and applies.
- **AC-2.5** `pending` → `blocked` and `in_progress` → `blocked` are both legal.
- **AC-2.6** When the target is `completed`, `completed_at` and `completed_by`
  are set, `completed_by` taking the request's `updated_by`. When the target is
  `blocked`, both remain unchanged.
- **AC-2.7** A mixed batch of legal and illegal items returns `207`, applies
  only the legal ones, and reports `updated` and `failed` counts matching the
  per-item results.
- **AC-2.8** Transition legality is expressed **once**, in `service.py`, as a
  single mapping of target status to the set of source statuses it may be
  reached from — not duplicated per branch and not restated in the tests.
- **AC-2.9** A test exists that would fail if any single transition rule were
  inverted. Name it in the generator summary.
- **AC-2.10** No regression against `.harness/reviews/BASELINE.md`. No
  `HTTPException`. No cross-module import. mypy stays clean.

## Files in scope

- `src/storeops/modules/activities/service.py`
- `src/storeops/modules/activities/models.py` — only if the result shape needs a message
- `tests/test_activities.py`

## Read scope

- `src/storeops/modules/activities/service.py`, `models.py`, `repository.py`
- `src/storeops/core/errors.py`
- `tests/test_activities.py`
- `.harness/reviews/BASELINE.md`

## Applicable rules

| Rule | Risk in this sprint |
| --- | --- |
| **4 — Layer separation** | The legality mapping is a business rule. It stays in `service.py`; `routes.py` must not change at all this sprint. |
| **3 — Error contract** | A per-item conflict uses `ConflictError`'s code, built not raised, exactly as sprint 1 did with `NotFoundError`. Assign messages to a variable first — do not introduce a new `EM101`/`EM102`. |
| — | `coding-conventions` §"A name that shadows a builtin inside a class body": do not add a bare `list[...]` annotation inside `ActivityService`. |
| — | `Activity` is frozen. `model_copy(update={...})` then `replace`. |

## Definition of done

- [ ] All ten ACs demonstrable by a named test
- [ ] Legality expressed once (AC-2.8), referenced by the service only
- [ ] `ruff` / `mypy` / `pylint` / `pytest` show no regression vs `BASELINE.md`
- [ ] Service-layer coverage at or above 80%
- [ ] `generator-summary.md` written with the AC self-check table complete

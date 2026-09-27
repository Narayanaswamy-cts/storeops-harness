# Sprint 3 contract: Audit trail via the event bus

## Objective

Record an audit entry for each activity a handover actually updated. The entry
must be produced by the `alerts` module reacting to an event, never by
`activities` calling `alerts`. This is the sprint that exercises Rule 2.

## Acceptance criteria

- **AC-3.1** `core/events.py` gains
  `ActivityStatusChanged(activity_id, store_id, from_status, to_status, changed_by)`,
  a frozen keyword-only `DomainEvent` carrying primitives only. `from_status` and
  `to_status` are `str`, not `ActivityStatus`, so `core` gains no dependency on a
  feature module.
- **AC-3.2** `bulk_update_status` publishes exactly one `ActivityStatusChanged`
  per **successfully updated** activity. Items reported as failed publish nothing.
- **AC-3.3** When the target is `completed`, each updated activity also publishes
  `ActivityCompleted`, so the existing single-activity alert behaviour is
  preserved for bulk updates.
- **AC-3.4** `alerts/subscribers.py` subscribes to `ActivityStatusChanged` and
  records an alert with `kind == "activity.status_changed"`,
  `severity == "info"`, a message naming the activity, the transition and the
  actor, and `source_event == "ActivityStatusChanged"`.
- **AC-3.5** A test asserts the **exact** event count for a mixed batch: three
  legal and two illegal items produce exactly three `ActivityStatusChanged`
  events and exactly three audit alerts.
- **AC-3.6** The bus is received as a keyword-only parameter by the service
  method. The service does not call `get_event_bus()` in its own body.
- **AC-3.7** `activities` does not import `alerts`. Boundary tests pass.
- **AC-3.8** The endpoint's response and status code do not depend on any
  subscriber succeeding. A test with a deliberately failing subscriber still
  gets `207` and the correct per-item results.
- **AC-3.9** No regression against `.harness/reviews/BASELINE.md`. `mypy .`
  clean over 46 files.

## Files in scope

- `src/storeops/core/events.py`
- `src/storeops/modules/activities/service.py`
- `src/storeops/modules/activities/routes.py` — to pass `BusDep` through
- `src/storeops/modules/alerts/subscribers.py`
- `tests/test_activities.py`, `tests/test_alerts.py`

## Read scope

- `src/storeops/core/events.py`, `deps.py`
- `src/storeops/modules/activities/service.py`, `routes.py`
- `src/storeops/modules/alerts/subscribers.py`, `models.py`, `service.py`
- `tests/conftest.py`, `tests/test_activities.py`, `tests/test_alerts.py`
- `.harness/reviews/BASELINE.md`

## Applicable rules

| Rule | Risk in this sprint |
| --- | --- |
| **2 — Event bus only** | The obvious shortcut is `from storeops.modules.alerts.service import AlertService` in the activities service. That is the primary risk of the whole feature. Publish and let the existing subscriber react. |
| **1 — Module boundary** | Judge by `test_no_module_imports_the_alerts_package`, **not** by the `TID251` count — 13 of those are pre-existing baseline noise from the unscoped ban. |
| **4 — Layer separation** | Publish from the service, after `repository.replace` returns. Never from the repository. |
| **3 — Error contract** | Unchanged. Do not introduce a new `EM` violation. |
| — | `EventBus.publish` swallows handler exceptions, so never let a subscriber's outcome affect the response (AC-3.8). |
| — | Event payloads are primitives only. Passing `ActivityStatus` would give `core` a module dependency. |
| — | No `# type: ignore` or `# noqa` to silence a check. |

## Definition of done

- [ ] All nine ACs demonstrable by a named test
- [ ] `ruff check .` / `mypy .` / `pylint src tests --jobs=1` / `pytest` show no regression
- [ ] Service-layer coverage at or above 80%
- [ ] `generator-summary.md` written with the AC self-check table complete

# Spec: Shift handover bulk update

## Intent

Outgoing shift staff currently close out activities one HTTP call at a time via
`POST /activities/{id}/complete`. At the end of a shift that means ten or twenty
sequential calls, and a failure part-way leaves the handover half-done with no
record of where it stopped.

This feature adds a single request that takes many activity ids and one target
status, applies every activity that can legally change, and returns a per-item
result for the rest. Each activity that actually changed produces an audit entry,
so a store manager can see who closed what during the handover.

## Scope

### In scope

- A `blocked` value on `ActivityStatus`.
- `PATCH /api/v1/activities/bulk-status`, accepting activity ids, a target
  status and the acting staff member.
- Per-item results with partial application: legal transitions are applied,
  illegal ones are reported, the request as a whole succeeds.
- An audit entry per successfully updated activity, raised through the event bus.

### Out of scope

Named explicitly because a reader could reasonably assume them:

- **No bulk create, bulk delete, or bulk reassignment.** Status only.
- **No transactional rollback.** Partial application is the requirement, not a
  failure mode to be avoided. A failed item does not undo a successful one.
- **No new audit module.** StoreOps has five fixed modules. The audit entry is
  recorded by `alerts`, which already stores `kind`, `severity`, `message` and
  `source_event`. Adding a sixth module is out of bounds.
- **No change to the existing single-activity `/complete` endpoint.** It keeps
  working and keeps its current behaviour.
- **No priority, category or department fields.** Not needed here.
- **No pagination on the request.** A maximum batch size is enforced instead.

## Architecture impact

| Concern | Decision | Rule |
| --- | --- | --- |
| Modules changed | `activities` (all three layers), `alerts` (subscriber only), `core` (events, enum is in activities) | 1 |
| New cross-module import | None. `alerts` learns about updates from the bus only. | 1, 2 |
| New event | `ActivityStatusChanged` in `core/events.py`, primitives only | 2 |
| Existing event | `ActivityCompleted` still published when the target status is `completed`, so current alert behaviour is preserved | 2 |
| Ports changed | None. No staff or reports involvement. | 5 |
| Endpoint count | 9 → 10. `test_boundaries.py` assertion must be updated. | — |
| New service provider | None. `ActivityService` and `AlertService` already exist, so `_PROVIDERS` in `conftest.py` is unchanged. | — |
| `main.py` | Unchanged. The router and the alerts subscriber registration already exist. | 6 |

The bulk operation lives on `ActivityService`. The route maps input and output
only. `alerts` never learns that a *bulk* operation happened — it receives one
event per changed activity, exactly as it would for a single change.

## Sprints

| # | Title | Modules | Files (est.) | Depends on |
| --- | --- | --- | --- | --- |
| 1 | Blocked status and the bulk endpoint | activities | 5 | — |
| 2 | Transition rules and per-item failures | activities | 4 | 1 |
| 3 | Audit trail via the event bus | core, activities, alerts | 5 | 2 |

---

## Sprint 1 — Blocked status and the bulk endpoint

Establishes the enum value, the endpoint, the request and response shapes, and
the layering that sprints 2 and 3 build on.

### Acceptance criteria

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
  updated to expect the new endpoint, with the count constant renamed or
  retargeted to 10. All boundary tests pass.
- **AC-1.8** `ruff check src tests`, `mypy`, `pylint src tests` and `pytest`
  show no regression against `.harness/reviews/BASELINE.md`.
- **AC-1.9** Every new failure path raises an `AppError` subclass. No
  `HTTPException` anywhere.
- **AC-1.10** Deciding whether an id can be applied happens in
  `service.py`. `routes.py` contains no conditional on a domain status value.

### Files expected to change

- `src/storeops/modules/activities/models.py` — `BLOCKED`; `BulkStatusUpdate`, `BulkItemResult`, `BulkStatusResult`
- `src/storeops/modules/activities/repository.py` — batch fetch by ids
- `src/storeops/modules/activities/service.py` — `bulk_update_status`
- `src/storeops/modules/activities/routes.py` — the `PATCH` route
- `tests/test_activities.py` — new tests
- `tests/test_boundaries.py` — endpoint assertion

### Out of bounds for this sprint

Transition legality beyond "does it exist" (sprint 2). Audit events (sprint 3).
Any change to `alerts`, `core/events.py`, `main.py`, or another module.

---

## Sprint 2 — Transition rules and per-item failures

### Acceptance criteria

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
  only the legal ones, and reports `"updated"` and `"failed"` counts matching
  the per-item results.
- **AC-2.8** Transition legality is expressed once, in `service.py`, as a
  single documented rule rather than duplicated per branch.
- **AC-2.9** A test exists that would fail if any single transition rule were
  inverted. Name it in the generator summary.
- **AC-2.10** No regression against `BASELINE.md`. No `HTTPException`. No
  cross-module import.

### Files expected to change

- `src/storeops/modules/activities/service.py`
- `src/storeops/modules/activities/models.py` — if the result shape needs a message
- `tests/test_activities.py`

### Out of bounds for this sprint

Audit events. Any change to `alerts`, `core/`, `routes.py`, or `main.py`.

---

## Sprint 3 — Audit trail via the event bus

### Acceptance criteria

- **AC-3.1** `core/events.py` gains
  `ActivityStatusChanged(activity_id, store_id, from_status, to_status, changed_by)`,
  a frozen keyword-only `DomainEvent` carrying primitives only. `from_status` and
  `to_status` are `str`, not `ActivityStatus`, so `core` gains no dependency on a
  module.
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
- **AC-3.7** `activities` does not import `alerts`. Audit entries appear only
  because `alerts` subscribed. Boundary tests pass.
- **AC-3.8** The endpoint's own response and status code do not depend on any
  subscriber succeeding. `EventBus.publish` swallows handler exceptions, so a
  test with a deliberately failing subscriber still gets `207` and the correct
  per-item results.
- **AC-3.9** No regression against `BASELINE.md`.

### Files expected to change

- `src/storeops/core/events.py`
- `src/storeops/modules/activities/service.py`
- `src/storeops/modules/activities/routes.py` — pass `BusDep` through
- `src/storeops/modules/alerts/subscribers.py`
- `tests/test_activities.py`, `tests/test_alerts.py`

### Out of bounds for this sprint

Any change to `staff`, `programmes`, `reports`, or the ports. No new module.

---

## Risks

### Sprint 1

**The result-building loop lands in the route.** The natural shape is to iterate
ids in `routes.py`, call `service.get()` per id, catch `NotFoundError` and append
to a list. That puts a business decision in the route and breaks Rule 4, which
has no automated check.
**Legal path:** `service.bulk_update_status(...)` returns a list of result
objects. The route maps them to the response model and returns. AC-1.10 states
this; the Evaluator gates on it.

**The endpoint assertion is forgotten.** `test_api_exposes_exactly_nine_endpoints`
hard-codes both the count and the sorted list. This is the single most likely
first-iteration failure.
**Legal path:** AC-1.7. Update the constant and the list together.

**`Activity` is frozen.** Assigning `activity.status = ...` raises at runtime.
**Legal path:** `model_copy(update={...})`, then `repository.replace(...)`.

### Sprint 2

**Transition rules get duplicated.** Writing the legality check once in the
service and again in a test helper lets them drift.
**Legal path:** AC-2.8. One mapping of target status to the set of source
statuses it may be reached from, referenced by both the service and the tests.

**`207` feels wrong for an all-success batch.** A Generator may switch to `200`
when nothing failed. That contradicts AC-1.3 and breaks sprint 1's tests.
**Legal path:** the status code is always `207`. It describes the envelope
shape, not the outcome.

### Sprint 3

**Publishing from the repository.** Convenient, since that is where the write
happens, and it breaks Rule 4.
**Legal path:** the service publishes after `repository.replace` returns.

**Importing alerts to write the audit entry.** The most likely Rule 2 violation
in the whole feature. `pyproject.toml`'s `banned-api` will flag it, but so will
13 pre-existing baseline errors, so **judge this by
`test_boundaries.py::test_no_module_imports_the_alerts_package`, not by the
`TID251` count.**
**Legal path:** publish `ActivityStatusChanged`; let the existing subscriber
react.

**Double alerting on completion.** AC-3.3 keeps `ActivityCompleted` for
`completed` targets, so a bulk completion raises both an `activity.completed`
alert and an `activity.status_changed` audit alert. This is intended — one is a
notification, one is an audit record. A Generator may "fix" it by dropping one.
**Legal path:** both are published. AC-3.5's exact counts pin it.

### Cross-cutting

**No `pytest-cov`.** The §3.6 coverage thresholds cannot be measured. The
Evaluator reports the coverage check as `BLOCKED` and redistributes its weight
rather than passing it silently. Not a blocker for these sprints.

**Do not repair the baseline.** 35 ruff errors, one failing endpoint test and
the missing `pytest-cov` are recorded in `BASELINE.md`. Fixing them inside a
sprint would bury the actual diff. Sprint 1 does modify
`test_api_exposes_exactly_nine_endpoints`, which is one of the recorded baseline
failures — that is required by AC-1.7 and is the one permitted exception. Making
that test pass is in scope; fixing its FastAPI-internals fragility is not.

STATUS: APPROVED 2026-09-26T17:41:13Z

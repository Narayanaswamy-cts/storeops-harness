# StoreOps API

Retail store operations management REST API. Python 3.11+, FastAPI, pytest + httpx,
ruff + pylint + mypy.

**This is a stub implementation.** Repository bodies are in-memory dicts and service
rules are deliberately thin. What is *not* stubbed is the structure: layering, module
boundaries, the typed error hierarchy, the event bus, and the test/lint/type-check
setup. Those are the parts that are expensive to retrofit, so they are real.

## Quick start

```bash
uv venv && source .venv/bin/activate
uv pip install -e '.[dev]'

uvicorn storeops.main:app --reload    # http://127.0.0.1:8000/docs
```

## Verification

```bash
ruff check . && ruff format --check .
mypy
pylint src/storeops tests
pytest
```

## Layout

```
src/storeops/
  main.py                  composition root — the only file that may import >1 module
  core/
    errors.py              AppError hierarchy
    events.py              EventBus + domain event types
    config.py              settings
    deps.py                shared singletons (event bus)
    pagination.py          Page / PageParams
  modules/<module>/
    routes.py              HTTP surface        (layer 1)
    service.py             business rules      (layer 2)
    repository.py          persistence         (layer 3)
    models.py              domain + wire schemas
tests/
  test_boundaries.py       parses the source tree to enforce the rules below
```

Each of the five modules — `activities`, `programmes`, `staff`, `alerts`, `reports` —
has the same three layers, with dependencies pointing strictly inward:
`routes → service → repository`. A route never touches a repository.

## Module boundary rules

These are enforced structurally by [tests/test_boundaries.py](tests/test_boundaries.py),
which AST-parses `src/` — not just described here.

1. **No circular imports.** A module may import `storeops.core.*` and its own
   package. Nothing else. `core` may never import a feature module, so the graph
   cannot cycle.
2. **Notifications via the event bus only.** No module may import
   `storeops.modules.alerts` — it is banned in both the boundary test and
   `ruff`'s `banned-api` config. Publishers emit a `DomainEvent`; `alerts`
   subscribes in [subscribers.py](src/storeops/modules/alerts/subscribers.py),
   wired once at startup. Event payloads carry only primitives, so a subscriber
   gains no coupling to the publisher.
3. **`staff` is read-only to other modules.** The single legal cross-module
   import is [staff/port.py](src/storeops/modules/staff/port.py), a `Protocol`
   exposing `find` / `headcount` / `is_active` and an immutable `StaffSummary`
   DTO. There is no mutating method to call, so the rule holds in types rather
   than in review comments. Writes go through `staff`'s own routes.
4. **Cross-module reads go through ports.** `reports` aggregates data owned by
   other modules, so it declares narrow read protocols in
   [reports/ports.py](src/storeops/modules/reports/ports.py) and has
   implementations injected by `main.py`. It imports no sibling module.

> Note: the brief's boundary rules mention a `users` module, but the module list
> specifies `staff`. This treats `staff` as that module. If `users` is meant to be
> a sixth module, the `port.py` pattern transfers to it unchanged.

## Typed errors

`AppError` is the base class, carrying `code`, `message` and `status_code`:

| Class | `code` | HTTP |
| --- | --- | --- |
| `ValidationError` | `validation_failed` | 422 |
| `NotFoundError` | `not_found` | 404 |
| `ConflictError` | `conflict` | 409 |
| `ForbiddenError` | `forbidden` | 403 |
| `ReadOnlyModuleError` | `read_only_module` | 403 |
| `DependencyError` | `dependency_unavailable` | 503 |
| `InternalError` | `internal_error` | 500 |

Every response body uses one envelope:

```json
{ "error": { "code": "not_found", "message": "activity 'act_1' was not found.",
             "details": { "resource": "activity", "id": "act_1" } } }
```

No service or route raises a bare exception. Three things hold that line: the
handlers in `main.py` (which also normalise FastAPI's own `RequestValidationError`
into the same envelope), ruff's `TRY`/`EM` rules, and
`test_services_and_routes_raise_only_app_errors`, which AST-scans every
`service.py` and `routes.py` for a `raise` of anything outside the hierarchy.

The brief specifies `statusCode`; the attribute is `status_code` because pylint's
`invalid-name` rejects camelCase attributes. The JSON envelope carries no
status field at all — the HTTP status line does that job.

## The 9 endpoints

⚠️ **Section 3.6 was not included in the brief**, so this endpoint set is an
assumption — three for activities, two each for programmes and alerts, one each
for staff and reports. Adjust
[test_boundaries.py](tests/test_boundaries.py) `test_api_exposes_exactly_nine_endpoints`
alongside any change; it asserts the exact list.

All paths are prefixed `/api/v1`.

| # | Method | Path | Purpose |
| --- | --- | --- | --- |
| 1 | `GET` | `/activities` | List activities; filter by `store_id`, `programme_id`, `status` |
| 2 | `POST` | `/activities` | Create an activity |
| 3 | `POST` | `/activities/{activity_id}/complete` | Complete an activity → publishes `ActivityCompleted` |
| 4 | `GET` | `/programmes` | List programmes; filter by `status` |
| 5 | `POST` | `/programmes` | Create a programme → publishes `ProgrammeLaunched` if activated |
| 6 | `GET` | `/staff` | List staff; filter by `store_id`, `role`, `active_only` |
| 7 | `GET` | `/alerts` | List alerts; filter by `store_id`, `severity`, `state` |
| 8 | `POST` | `/alerts/{alert_id}/acknowledge` | Acknowledge an open alert |
| 9 | `GET` | `/reports/metrics` | Metrics for exactly one of `store_id` or `region_id` |

`GET /health` also exists as a liveness probe and is excluded from the count.

List endpoints share the `Page` envelope: `{ items, total, limit, offset }`.

## Domain events

| Event | Published by | Alert raised |
| --- | --- | --- |
| `ActivityCompleted` | `activities.complete` | `activity.completed` (info) |
| `ActivityOverdue` | scheduled sweep (not yet implemented) | `activity.overdue` (warning) |
| `ProgrammeLaunched` | `programmes.create` when activated | `programme.launched` (info) per store |
| `StaffRosterChanged` | reserved — declared, no publisher yet | — |

Handler failures are logged and swallowed by `EventBus.publish`: a notification
subscriber must never fail the publisher's request.

## What a real implementation still needs

- Swap each `repository.py` body for real persistence (the method signatures are
  the contract the services are already written against).
- Replace `EventBus` with a broker-backed implementation — no module changes
  required, only `core/events.py` and the wiring in `main.py`.
- Authentication: `completed_by` / `acknowledged_by` are request-body fields and
  should come from the authenticated principal instead.
- A scheduled sweep to publish `ActivityOverdue`, and a publisher for
  `StaffRosterChanged`.
- Service singletons are `lru_cache`'d module-level providers, which is fine for
  stubs; a real deployment wants request-scoped sessions via
  `app.dependency_overrides` or a container.

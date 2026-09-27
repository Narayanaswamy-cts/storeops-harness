# Skill: app-context

**Purpose.** Orient any agent to what StoreOps *is* before it plans, writes, or
reviews code. Read this first, every time. It is the shortest path to knowing
where a change belongs.

Read by: **all four agents**.

---

## What StoreOps is

A retail store operations management REST API. Store staff use it to run
operational work: activities to be done in a store, programmes that group them,
the staff assigned, alerts raised when something needs attention, and reports
that roll the whole thing up.

**Python 3.11+ / FastAPI / Pydantic v2 / pytest + httpx.** In-memory storage —
repositories are dicts. Deliberate: this is a structural reference application,
so the layering, boundaries, and error contract are real while the persistence
is not.

Distributed as a `src/` layout package. `pyproject.toml` sets
`pythonpath = ["src"]` for pytest and `mypy_path = "src"`, so imports are always
absolute from `storeops`.

## Domain vocabulary

Use these words. The codebase uses British-influenced domain naming
("programme", not "program") and the enums are lowercase strings.

| Term | Meaning | Module |
| --- | --- | --- |
| **Activity** | A unit of operational work in a store — reset an end-cap, count stock. Has status, optional due date, optional assignee. | `activities` |
| **Programme** | A campaign or initiative grouping activities across one or more stores. | `programmes` |
| **Staff** | A store employee. Read-only to every other module. | `staff` |
| **Alert** | An operational notification, raised *reactively* from domain events. | `alerts` |
| **Report** | A read-only aggregation across the other modules. | `reports` |
| **Store** | Identified by `store_id` (e.g. `store_001`). Not a module — an attribute on most records. |  |

`ActivityStatus` is `pending | in_progress | completed | cancelled`.
`AlertSeverity` lives in `modules/alerts/models.py`.

## Layout

```
src/storeops/
  main.py                    composition root — the ONLY module that may import >1 feature module
  core/                      cross-cutting; imports no feature module, ever
    config.py                Settings (frozen dataclass), get_settings() — lru_cached
    deps.py                  get_event_bus(), BusDep
    errors.py                AppError hierarchy
    events.py                EventBus, DomainEvent + concrete event types
    pagination.py            PageParams, Page[ItemT]
  modules/
    activities/              models / routes / service / repository
    programmes/              models / routes / service / repository
    staff/                   + port.py  ← the ONLY file other modules may import
    alerts/                  + subscribers.py  ← inbound edge from the bus
    reports/                 + ports.py  ← read-only contracts it needs from others
tests/                       mirrors modules; test_boundaries.py enforces structure
```

Every module has exactly three layers plus `models.py`. `test_boundaries.py::test_every_module_contributes_all_three_layers`
enforces it — a new module without all three fails the suite.

## The current API surface

`api_prefix` is `/api/v1`, from `STOREOPS_API_PREFIX` (default in `core/config.py`).

| Method + path | Module |
| --- | --- |
| `GET /api/v1/activities` | activities |
| `POST /api/v1/activities` | activities |
| `POST /api/v1/activities/{activity_id}/complete` | activities |
| `GET /api/v1/programmes` | programmes |
| `POST /api/v1/programmes` | programmes |
| `GET /api/v1/staff` | staff |
| `GET /api/v1/alerts` | alerts |
| `POST /api/v1/alerts/{alert_id}/acknowledge` | alerts |
| `GET /api/v1/reports/metrics` | reports |
| `GET /health` | meta (unprefixed) |

**This list is asserted exactly** in `test_boundaries.py::test_api_exposes_exactly_nine_endpoints`.
Any agent adding an endpoint **must** update that test's expected list in the
same change, or the suite fails. This is intentional: the endpoint surface is a
reviewed contract, not an emergent property.

> **Known deviation from the case-study brief.** Brief §3.6 specifies a
> different nine: `GET/PATCH/DELETE /api/activities/:id` and
> `POST /api/programmes/:id/members`, with staff auth-only and reports deferred.
> The scaffold instead ships `/complete`, `/acknowledge`, `GET /staff` and
> `/reports/metrics`. The scaffold is the source of truth for agents — plan and
> review against the table above, not against the brief. Reconciling the two is
> a developer decision, not a Generator one; do not "fix" it mid-sprint.

## Wiring — read this before touching `main.py`

`create_app()` in `main.py` does four things in order: installs error handlers,
calls `wire_modules()`, includes every router under `api_prefix`, adds `/health`.

`wire_modules()` is where cross-module connection happens, and it is the only
place it is allowed to happen:

- **Alerts subscribe.** `register_alert_subscribers(bus, get_alert_service())`.
  Publishers never know alerts exist.
- **Reports get injected ports.** `configure_sources(MetricsSources(...))` hands
  reports four read-only protocols. Reports imports no feature module except
  `staff.port`.

It is called synchronously from `create_app`, *not* from a lifespan hook,
because tests drive the app through `httpx.ASGITransport`, which does not run
lifespan events. Moving this into a lifespan handler silently breaks the whole
test suite — do not.

Services are `lru_cache(maxsize=1)` singletons. `tests/conftest.py` calls
`.cache_clear()` on all six providers around every test. A new service provider
**must** be added to `_PROVIDERS` in `conftest.py`, or state leaks across tests
and produces failures that look random.

## Existing events

Defined in `core/events.py`:

| Event | Fields | Published by |
| --- | --- | --- |
| `ActivityCompleted` | `activity_id`, `store_id`, `completed_by` | `activities.service.complete()` |
| `ActivityOverdue` | `activity_id`, `store_id`, `due_at` | **nothing yet — no publisher** |
| `ProgrammeLaunched` | `programme_id`, `store_ids` | `programmes` |
| `StaffRosterChanged` | `store_id`, `headcount` | `staff` |

`ActivityOverdue` is subscribed by `alerts/subscribers.py` but never published.
That is the natural seam for SLA/overdue work — a feature that needs it should
publish the existing event rather than invent a new one.

## Where a change goes

| The change is… | It belongs in… |
| --- | --- |
| A new HTTP shape, query param, status code | `modules/<m>/routes.py` |
| A business rule, validation, state transition | `modules/<m>/service.py` |
| A new query or storage shape | `modules/<m>/repository.py` |
| A request/response/domain shape | `modules/<m>/models.py` |
| Something two modules both need | `core/` — never a sibling import |
| A cross-module side effect | a new event in `core/events.py` + a subscriber |
| Another module needs to *read* your module | a `Protocol` port, injected in `main.py` |

## Reference

- Brief endpoint/coverage requirements: case-study §3.6
- Architecture rules: `.harness/skills/architecture-principles/SKILL.md`
- Automated check commands: `.harness/skills/how-to-review/SKILL.md`

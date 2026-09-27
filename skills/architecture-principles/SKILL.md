# Skill: architecture-principles

**Purpose.** The five non-negotiable rules of the StoreOps codebase, each with
the concrete code shape that satisfies it, the shape that violates it, and the
exact check that catches the violation.

Read by: **all four agents**. The Planner plans within these; the Generator
writes within these; the Evaluator gates on these.

These are not general good practice. Each rule maps to a specific failure mode
observed in the client codebase this harness was built to govern (case-study §2).

---

## Rule 1 — Module boundary

> No module may import from another module's `repository.py`, `service.py`, or
> `models.py`. The single exception is `storeops.modules.staff.port`.

A module may import: itself, `storeops.core.*`, `storeops` (for `__version__`),
and `storeops.modules.staff.port`. Nothing else.

**Violation** — the failure mode this harness exists to prevent:

```python
# modules/alerts/service.py
from storeops.modules.activities.repository import ActivityRepository   # NO

async def raise_for_overdue(self, activity_id: str) -> None:
    activity = await ActivityRepository().get(activity_id)
```

That couples alerts to activities' storage. When activities moves to SQL, alerts
breaks, and nothing in the type system said so.

**Correct** — receive what you need as data on the event:

```python
# modules/alerts/subscribers.py
async def on_activity_overdue(event: ActivityOverdue) -> None:
    await service.raise_alert(AlertCreate(
        store_id=event.store_id,
        kind="activity.overdue",
        severity=AlertSeverity.WARNING,
        message=f"Activity {event.activity_id} was due at {event.due_at.isoformat()}.",
        source_event=event.name,
    ))
```

**Checked by:**
- Automated — `ruff` via `[tool.ruff.lint.flake8-tidy-imports]` in `pyproject.toml`
- Automated — `test_boundaries.py::test_modules_import_only_core_themselves_or_the_staff_port`
- Automated — `test_boundaries.py::test_module_graph_is_acyclic`

**Hard gate.** Any violation is an immediate `FAIL`.

### Need data from another module?

Declare a `Protocol` describing only the reads you need, and have `main.py`
inject it. `reports/ports.py` is the worked example:

```python
class ActivityMetrics(Protocol):
    async def status_breakdown(self, store_id: str | None = None) -> dict[str, int]: ...
```

Reports never imports activities. `main.wire_modules()` passes
`get_activity_service()`, which structurally satisfies the protocol. Adding a
read means adding a method to the protocol *and* to the providing service — and
the protocol must stay read-only.

---

## Rule 2 — Event bus only

> A side effect that crosses a module boundary is published as a `DomainEvent`.
> Never by importing the reacting module.

**Violation:**

```python
# modules/activities/service.py
from storeops.modules.alerts.service import AlertService     # NO

async def complete(self, activity_id: str, *, completed_by: str) -> Activity:
    ...
    await AlertService().raise_alert(...)
```

**Correct** — publish and forget:

```python
await bus.publish(ActivityCompleted(
    activity_id=stored.id,
    store_id=stored.store_id,
    completed_by=completed_by,
))
```

The bus is obtained by dependency injection (`BusDep` from `core/deps.py`) and
passed into the service method. Services do **not** call `get_event_bus()`
themselves — that hides the dependency and makes the method untestable without
the container.

### Event payload rules

Events are `@dataclass(frozen=True, kw_only=True)` subclasses of `DomainEvent`
in `core/events.py`, carrying **primitives only** — `str`, `int`, `datetime`,
`tuple[str, ...]`. Never a Pydantic model, never another module's domain record.
A subscriber that receives `Activity` has a compile-time dependency on
activities, which defeats the entire mechanism.

Handler failures are logged and swallowed by `EventBus.publish`. A subscriber
cannot fail the publisher's request. Consequence for the Generator: **never rely
on a subscriber's side effect for the publisher's return value or status code.**
Publishing is fire-and-forget.

**Checked by:**
- Automated — `test_boundaries.py::test_no_module_imports_the_alerts_package`
- Automated — `test_boundaries.py::test_alerts_reacts_only_to_core_event_types`
- Automated — `banned-api` in `pyproject.toml` (importing `storeops.modules.alerts` is a ruff error)
- LLM-assessed — was the bus used where a direct call would have been easier?

**Hard gate.** Any cross-module import for notification is an immediate `FAIL`.

---

## Rule 3 — Error contract

> Every failure raised by a service or route is an `AppError` subclass. No bare
> `Exception`, `ValueError`, `RuntimeError`, or `HTTPException`.

The hierarchy in `core/errors.py`, with the status code each carries:

| Class | `code` | Status | Use when |
| --- | --- | --- | --- |
| `ValidationError` | `validation_failed` | 422 | Payload is well-formed but breaks a business rule |
| `NotFoundError` | `not_found` | 404 | Resource does not exist — prefer `NotFoundError.for_resource("activity", id)` |
| `ConflictError` | `conflict` | 409 | Resource state forbids the operation |
| `ForbiddenError` | `forbidden` | 403 | Caller may not do this |
| `ReadOnlyModuleError` | `read_only_module` | 403 | Another module tried to mutate staff |
| `DependencyError` | `dependency_unavailable` | 503 | Downstream unavailable |
| `InternalError` | `internal_error` | 500 | Explicit stand-in for an unexpected fault |

**Never raise `HTTPException`.** FastAPI's own exception is not part of the
hierarchy, produces a `{"detail": ...}` body instead of the `{"error": {...}}`
envelope, and bypasses the handlers in `main.py`.

All errors render through `AppError.to_payload()`:

```json
{ "error": { "code": "conflict", "message": "…", "details": { "status": "completed" } } }
```

`details` is optional and omitted when empty. Put machine-readable context there
(`{"field": "due_at"}`), never a stack trace or an internal identifier.

**Correct:**

```python
if activity.status is ActivityStatus.COMPLETED:
    raise ConflictError(
        f"Activity {activity_id!r} is already completed.",
        details={"status": activity.status.value},
    )
```

Note: message built before the raise or passed as an argument — ruff's `EM` rules
ban string literals constructed inline in the raise expression, and `TRY003` is
disabled specifically because `AppError` subclasses carry long default messages
on purpose.

Attribute naming is `status_code`, not the brief's `statusCode`; pylint
`invalid-name` rejects camelCase attributes. The wire format is unaffected.

**Checked by:**
- Automated — `ruff` `TRY` and `EM` rule families
- Automated — `test_boundaries.py::test_services_and_routes_raise_only_app_errors` (AST-parses every `raise`)
- Automated — `test_boundaries.py::test_every_error_class_subclasses_app_error`

**Hard gate.** Any raw raise in a service or route is an immediate `FAIL`.

---

## Rule 4 — Layer separation

> `routes → service → repository`. No skipping, no reaching back.

| Layer | May do | Must never do |
| --- | --- | --- |
| `routes.py` | Parse/validate input, call **one** service, map domain → `*Read` schema, set status codes | Contain business rules, touch a repository, build domain records |
| `service.py` | Business rules, state transitions, raise `AppError`, publish events, call its own repository | Import another module, know about HTTP, read `Request`, return a response model |
| `repository.py` | Store and query records | Raise `AppError`, publish events, call a service, know about HTTP |

**Routes are thin.** The exemplar — note there is no logic here beyond mapping:

```python
@router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
async def create_activity(service: ActivityServiceDep, payload: ActivityCreate) -> ActivityRead:
    return ActivityRead.from_domain(await service.create(payload))
```

**Repositories are dumb.** No validation, no events, no errors. A repository
returns `None` for a missing row; the *service* turns that into `NotFoundError`:

```python
# repository
async def get(self, activity_id: str) -> Activity | None:
    return self._rows.get(activity_id)

# service
async def get(self, activity_id: str) -> Activity:
    activity = await self._repository.get(activity_id)
    if activity is None:
        raise NotFoundError.for_resource("activity", activity_id)
    return activity
```

**Domain vs wire.** `Activity` is the internal frozen record and is never
returned from a route. `ActivityRead.from_domain()` does the projection.
`ActivityCreate` is the inbound shape. Returning a domain record directly leaks
internal fields (`completed_by`) into the API.

Mutation is `model_copy(update={...})` — domain models are
`ConfigDict(frozen=True)`.

**Checked by:** LLM-assessed. No linter catches business logic in a route. The
Evaluator reads each changed file against the table above, and the Generator's
summary must name the layer of every file it touched.

---

## Rule 5 — Read-only modules

> **Reports** never writes to another module. **Staff** is read-only to every
> other module.

Reports aggregates activities, programmes, alerts, and staff through the
protocols in `reports/ports.py`. Every one of those protocols exposes queries
only. A write path originating in reports is a violation even if it goes through
a service.

Staff exposes exactly one importable file, `staff/port.py`:

```python
@runtime_checkable
class StaffDirectory(Protocol):
    async def find(self, staff_id: str) -> StaffSummary | None: ...
    async def headcount(self, store_id: str) -> int: ...
    async def is_active(self, staff_id: str) -> bool: ...
```

`StaffSummary` is frozen. The mutable `Staff` record and the repository are
unreachable from outside. The rule is expressed in types rather than a comment —
importing `storeops.modules.staff.service` fails the boundary test.

If another module needs a staff *write*, that is a spec defect. Escalate; do not
add a mutating method to the port.

**Checked by:**
- Automated — `test_boundaries.py::test_staff_is_read_only_to_other_modules`
- Automated — `test_boundaries.py::test_staff_port_declares_no_mutating_methods` (bans method names `create`, `update`, `delete`, `save`, `add`, `replace`, `deactivate`)
- LLM-assessed — no write originates from reports

**Hard gate.** Any staff mutation from outside staff, or any write from reports,
is an immediate `FAIL`.

---

## Rule 6 — `core` is a leaf; `main` is the only composer

`core/` imports no feature module, ever. It is the bottom of the graph — that is
what lets every module depend on it without creating a cycle.

`main.py` is the **only** module permitted to import more than one feature
module. Any other file in `src/storeops/` that touches two modules is a
violation.

**Checked by:**
- Automated — `test_boundaries.py::test_core_never_imports_a_feature_module`
- Automated — `test_boundaries.py::test_only_main_composes_multiple_modules`

**Hard gate.** Immediate `FAIL`.

---

## Summary — the gate table

| # | Rule | Enforcement | Gate |
| --- | --- | --- | --- |
| 1 | Module boundary | ruff tidy-imports + 2 boundary tests | Hard |
| 2 | Event bus only | ruff banned-api + 2 boundary tests + LLM | Hard |
| 3 | Error contract | ruff TRY/EM + 2 boundary tests | Hard |
| 4 | Layer separation | LLM-assessed only | Scored |
| 5 | Read-only modules | 2 boundary tests + LLM | Hard |
| 6 | core leaf / main composer | 2 boundary tests | Hard |

Rule 4 is the only rule with no automated enforcement. It is therefore the rule
most likely to decay, and the one the Evaluator must read most carefully.

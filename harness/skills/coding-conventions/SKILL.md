# Skill: coding-conventions

**Purpose.** The Python and FastAPI conventions this codebase actually uses, at
the level of detail needed to write a file that passes `ruff`, `mypy --strict`,
and `pylint` on the first try.

Read by: **Generator**.

---

## Non-negotiables

Every module file starts with a docstring and `from __future__ import annotations`:

```python
"""Activity business rules."""

from __future__ import annotations
```

The future import is mandatory even on 3.11 — it makes all annotations strings,
which is what lets `-> ActivityRead` work inside the class that defines it and
keeps forward references cheap.

Every module declares `__all__`, listing the public names in **alphabetical
order**:

```python
__all__ = ["ActivityService", "ActivityServiceDep", "get_activity_service"]
```

`no_implicit_reexport = true` is set in mypy config: a name not in `__all__` is
not importable from that module. Omitting `__all__` breaks importers.

**Line length 100.** Set in both `[tool.ruff]` and `[tool.pylint.format]`.

## Typing — `mypy --strict` is on

`strict = true`, plus `warn_unreachable` and `disallow_any_generics`. Practical
consequences:

- **Every function is annotated, including `-> None`.** A missing return
  annotation is a ruff `ANN` error *and* a mypy error.
- **No bare generics.** `dict` is an error; write `dict[str, int]`.
- **No `Any`** except the two deliberate uses already in the codebase (the
  event-bus handler registry, and `details: dict[str, Any]` on `AppError`).
  `ANN401` is ignored globally for those; do not add more.
- **`X | None`, never `Optional[X]`.** Consistent throughout.
- **Tests are looser** — `disallow_untyped_defs = false` for `tests.*`, and
  `ANN201` is ignored there, so test functions need no return annotation.

### Parsed JSON is `dict[str, Any]`, never `dict[str, object]`

`object` permits nothing: no indexing, no iteration, no `len()`. Annotating a
decoded response body as `dict[str, object]` type-checks at the assignment and
then fails at every use site, which invites a suppression per line.

```python
# wrong -- forces a `type: ignore` at every access
body: dict[str, object] = response.json()
assert body["results"][0]["error"]["code"] == "conflict"   # error: not indexable

# right
body: dict[str, Any] = response.json()
```

This applies to test helpers as much as to source. It cost sprint 2 an
iteration, and the four suppressions added to hide it were masking a genuine
mistake rather than a tooling quirk.

### A name that shadows a builtin inside a class body

`ActivityService` defines a method named **`list`**. Inside that class body the
name shadows `builtins.list`, so a bare `list[...]` annotation in any method
defined *after* it resolves to the method object and fails `mypy --strict` with
`Function "...ActivityService.list" is not valid as a type`.

Runtime is unaffected, because `from __future__ import annotations` defers
evaluation — so the tests pass and only mypy catches it.

Inside `ActivityService`, use the module-scope alias:

```python
# module scope -- `list` is the builtin here
_ItemResults = list[BulkItemResult]

class ActivityService:
    async def bulk_update_status(self, ...) -> BulkStatusResult:
        results: _ItemResults = []        # not list[BulkItemResult]
```

Better still, put the helper at module scope when it does not need `self`. Do
not rename `ActivityService.list` — `routes.py` calls it.

This cost sprint 1 a full iteration. Check for a same-named method before
annotating with a builtin generic inside any service class.

Cast only where the codebase already does — `EventBus.subscribe` uses
`cast(Handler, handler)` because the variance cannot be expressed. Reaching for
`cast` anywhere else usually means the design is wrong.

## Naming

| Thing | Convention | Example |
| --- | --- | --- |
| Module | lowercase, singular layer name | `service.py`, `repository.py` |
| Class | `PascalCase` | `ActivityService` |
| Function / attribute | `snake_case` | `status_breakdown`, `store_id` |
| Private attribute | single leading underscore | `self._repository`, `self._rows` |
| Provider | `get_<thing>` | `get_activity_service` |
| DI alias | `<Thing>Dep` | `ActivityServiceDep`, `BusDep` |
| Enum member | `UPPER_CASE`, lowercase value | `PENDING = "pending"` |
| Domain id | `<prefix>_<hex12>` | `f"act_{uuid.uuid4().hex[:12]}"` |

`pylint` runs with `pep8-naming` (ruff `N`) — camelCase attributes are rejected.
This is why `AppError.status_code` is snake_case despite the brief writing
`statusCode`.

## Pydantic v2 patterns

**Domain records are frozen.** Mutate with `model_copy`:

```python
class Activity(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    status: ActivityStatus = ActivityStatus.PENDING

completed = activity.model_copy(update={"status": ActivityStatus.COMPLETED})
```

Never `activity.status = ...` — it raises at runtime.

**Three model kinds per resource.** Do not collapse them:

| Kind | Purpose | Notes |
| --- | --- | --- |
| `Activity` | Internal domain record | Frozen. Never returned from a route. |
| `ActivityCreate` | Inbound payload | Field constraints live here: `Field(min_length=1, max_length=200)` |
| `ActivityRead` | Outbound response | Has `from_domain()` classmethod doing the projection |

`from_domain` is explicit field-by-field, not `**activity.model_dump()`. That is
deliberate: adding an internal field to `Activity` must not silently leak it
into the API. `Activity.completed_by` is absent from `ActivityRead` for exactly
this reason.

**Enums are `StrEnum`** (`from enum import StrEnum`) with lowercase values, so
they serialise as plain JSON strings. Compare with `is`:

```python
if activity.status is ActivityStatus.COMPLETED:
```

## FastAPI patterns

**Router per module**, prefix without the API version — `main.py` adds the
`api_prefix`:

```python
router = APIRouter(prefix="/activities", tags=["activities"])
```

**Dependency injection via `Annotated` aliases**, defined in the service module:

```python
ActivityServiceDep = Annotated[ActivityService, Depends(get_activity_service)]
```

Routes then take `service: ActivityServiceDep` as the **first** parameter. Never
call `get_activity_service()` inside a route or service body — it defeats
override-based testing.

**Query parameters** use `Annotated[T, Query()]`. Note the shadowing workaround
already in the codebase — ruff's `A` rules ban shadowing builtins and `status`
collides with FastAPI's `status` module, so the parameter is renamed and aliased:

```python
activity_status: Annotated[ActivityStatus | None, Query(alias="status")] = None
```

**Response models are declared twice** — in the decorator and as the return
annotation. FastAPI uses the first for the OpenAPI schema; mypy needs the second:

```python
@router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
async def create_activity(...) -> ActivityRead:
```

Use `status.HTTP_201_CREATED`, not `201`.

**Every list endpoint returns `Page[T]`:**

```python
rows, total = await service.list(criteria, limit=params.limit, offset=params.offset)
return Page.of([ActivityRead.from_domain(row) for row in rows], total, params)
```

`params: Annotated[PageParams, Depends()]`. Do not hand-roll `limit`/`offset`.

## Async

**Everything is `async`**, including repository methods that only touch a dict.
The signatures are the contract a real database will be swapped into; making
them sync now means changing every caller later.

Never `asyncio.run()` inside application code, and no blocking I/O in a handler.

## Services

Constructor takes its repository; module-level cached provider builds it:

```python
class ActivityService:
    def __init__(self, repository: ActivityRepository) -> None:
        self._repository = repository

@lru_cache(maxsize=1)
def get_activity_service() -> ActivityService:
    return ActivityService(ActivityRepository())
```

**Adding a provider means editing `tests/conftest.py`.** Add it to `_PROVIDERS`
so `reset_singletons` clears it. Skipping this leaks state between tests and
produces order-dependent failures.

**The bus is a parameter, not a lookup.** Keyword-only, after the positional args:

```python
async def complete(self, activity_id: str, *, completed_by: str, bus: EventBus) -> Activity:
```

The route supplies it from `BusDep`.

## Errors

Covered fully in `architecture-principles` Rule 3. The conventions that trip
ruff:

```python
# EM101 — no string literal built inline in the raise
raise ConflictError(f"Activity {activity_id!r} is already completed.",
                    details={"status": activity.status.value})
```

Use `!r` for identifiers in messages. Put structured context in `details`, never
in the message. Prefer the classmethod when one exists:
`NotFoundError.for_resource("activity", activity_id)`.

`TRY003` is disabled project-wide, so long default messages on `AppError`
subclasses are fine.

## Comments

The codebase comments **rules and non-obvious constraints**, not mechanics. Two
patterns worth copying:

```python
# Boundary rule: notify via the bus, never by importing alerts.
await bus.publish(ActivityCompleted(...))
```

```python
except Exception:  # noqa: BLE001 -- isolate subscribers from publishers
```

A `noqa` must carry a `--` reason. Module docstrings carry the architectural
*why* — see `core/events.py` and `staff/port.py` for the register to match.

Mark stubs explicitly, as the scaffold does:

```python
"""STUB: rule bodies are intentionally minimal."""
```

## Imports

`ruff`'s `I` rules sort them; `ban-relative-imports = "all"` makes every import
absolute. Order: `__future__`, stdlib, third-party, `storeops.*`. Never
`from .service import ...`.

## Before you finish

```bash
ruff check src tests --fix     # safe fixes, then re-read the diff
ruff check src tests
mypy .
pylint src tests --jobs=1
pytest --cov=storeops
```

`ruff --fix` will reorder imports and rewrite comprehensions. Re-read what it
changed — it occasionally reformats a line past something you meant to keep.

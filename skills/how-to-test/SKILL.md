# Skill: how-to-test

**Purpose.** How StoreOps tests are written and what "tested" has to mean here —
specifically, why asserting a status code is not a test.

Read by: **Generator**. The Evaluator scores against the same standard.

---

## The failure mode this skill exists to stop

> *Tests that asserted HTTP status codes but did not verify business rule compliance.*
> — case-study §2, failure mode 3

A test that only checks `response.status_code == 409` passes whether the service
raised the conflict for the right reason, the wrong reason, or by accident. Every
test of a failure path must assert **the error `code`**, and every test of a
business rule must assert **the state change or the absence of one.**

```python
# NOT a test — passes even if the rule is wrong
async def test_double_complete_conflicts(client):
    response = await client.post(f"{API}/activities/{id}/complete", json={"completed_by": "s1"})
    assert response.status_code == 409

# A test — asserts the contract and the rule
async def test_double_complete_conflicts(client, activity_payload):
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    body = {"completed_by": "staff_001"}
    await client.post(f"{API}/activities/{created['id']}/complete", json=body)

    response = await client.post(f"{API}/activities/{created['id']}/complete", json=body)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert response.json()["error"]["details"]["status"] == "completed"

    # the rule: the second attempt changed nothing
    after = (await client.get(f"{API}/activities/{created['id']}")).json()
    assert after["completed_at"] == created_completed_at
```

## Mechanics

Tests are `async def`, no decorator — `asyncio_mode = "auto"` is set in
`pyproject.toml`. Adding `@pytest.mark.asyncio` is redundant; `--strict-markers`
is on, so an unregistered marker is an error.

Drive the app through the `client` fixture from `tests/conftest.py`, which wires
a fresh app over `httpx.ASGITransport`. Use the `API` constant (`/api/v1`) — never
hard-code the prefix.

```python
from tests.conftest import API

async def test_list_activities_is_paginated(client, activity_payload):
    await client.post(f"{API}/activities", json=activity_payload)

    response = await client.get(f"{API}/activities", params={"limit": 1})

    assert response.status_code == 200
    page = response.json()
    assert page["limit"] == 1
    assert page["total"] == 1
    assert len(page["items"]) == 1
```

**Singletons must be registered.** `reset_singletons` is `autouse` and clears
every provider in `_PROVIDERS`. A new `lru_cache`d provider that is not added to
that tuple leaks state between tests and produces failures that look random and
order-dependent. This is the single most common self-inflicted test failure in
this codebase.

**Never call `wire_modules()` or `create_app()` directly in a test.** Use the
fixture. `create_app` wires synchronously on purpose so `ASGITransport` works
without lifespan events — see `app-context`.

## What to test at each layer

| Layer | Test through | Assert |
| --- | --- | --- |
| Route | `client` fixture | Status code **and** `error.code`; response shape; that the response model omits internal fields |
| Service | `client` fixture, or the service directly for pure rules | The rule: state transition happened / was refused; the right `AppError` subclass |
| Repository | Via the service | Filtering, pagination boundaries, counts |
| Event | Bus assertions (below) | Exactly which events fired, and their payload fields |
| Structure | `tests/test_boundaries.py` | Imports, layering, endpoint surface |

Prefer testing through the client. A rule that can only be verified by calling a
service method directly is usually a rule that no route exercises.

## Testing events

Cross-module behaviour is the thing most likely to be under-tested, because the
bus swallows handler exceptions — a broken subscriber looks like success.

Assert on **both** sides, in separate tests:

```python
# publisher side: the event fired, with the right payload
async def test_completing_an_activity_publishes_the_event(client, activity_payload):
    from storeops.core.deps import get_event_bus
    from storeops.core.events import ActivityCompleted

    seen: list[ActivityCompleted] = []

    async def capture(event: ActivityCompleted) -> None:
        seen.append(event)

    get_event_bus().subscribe(ActivityCompleted, capture)
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()

    await client.post(f"{API}/activities/{created['id']}/complete",
                      json={"completed_by": "staff_001"})

    assert len(seen) == 1
    assert seen[0].activity_id == created["id"]
    assert seen[0].completed_by == "staff_001"
```

```python
# subscriber side: the reaction happened
async def test_completion_raises_an_info_alert(client, activity_payload):
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    await client.post(f"{API}/activities/{created['id']}/complete",
                      json={"completed_by": "staff_001"})

    alerts = (await client.get(f"{API}/alerts")).json()["items"]

    assert [a["kind"] for a in alerts] == ["activity.completed"]
    assert alerts[0]["severity"] == "info"
```

Assert the **count**, not just presence. "Publishes exactly one event per
breach" is a rule; a test that accepts one-or-more does not check it.

## Coverage thresholds

From case-study §3.6, and gated by the Evaluator:

| Scope | Minimum line coverage |
| --- | --- |
| Service layer | 80% |
| Route layer | 70% |
| Shared utilities (`core/`) | 60% |
| Overall | 70% |

> **Known gap.** `pytest-cov` is **not** currently in the `dev` extra, so
> `pytest --cov` fails with `unrecognized arguments: --cov`. Coverage cannot be
> measured until `pytest-cov` is added to `[project.optional-dependencies].dev`
> in `pyproject.toml`. Until then the Evaluator treats the coverage gate as
> `BLOCKED`, not as passed — see `evaluation-criteria`. Do not silently drop
> `--cov` from the command to make the check go green.

Coverage is a floor, not the goal. 100% coverage of a service whose tests assert
only status codes still exhibits failure mode 3.

## When the endpoint surface changes

`test_boundaries.py::test_api_exposes_exactly_nine_endpoints` asserts the exact
sorted list of `(path, method)` pairs. Adding or changing an endpoint means
updating that list **in the same sprint**. A sprint that adds a route without
touching this test will fail its first iteration.

> **Known gap.** This test currently fails on the untouched baseline. FastAPI
> 0.141 / Starlette 1.7 changed `include_router` to register a lazy
> `_IncludedRouter` wrapper rather than copying `APIRoute` objects into
> `app.routes`, so the test's `isinstance(route, APIRoute)` filter now matches
> only `/health` and the assertion sees zero operations. The test reaches into
> framework internals. The version-stable fix is to enumerate the public schema:
>
> ```python
> schema = create_app(Settings(api_prefix="/api/v1")).openapi()
> operations = sorted(
>     (path, method.upper())
>     for path, ops in schema["paths"].items()
>     for method in ops
>     if path.startswith("/api/v1")
> )
> ```
>
> Until that is applied, the Evaluator's test gate treats this one named failure
> as a known baseline failure rather than a regression — but **any other** test
> failure is a hard `FAIL`.

## Naming and shape

Files are `tests/test_<module>.py`; `test_boundaries.py` and `test_errors.py`
are cross-cutting. Test names state the rule, not the mechanic:

- `test_double_complete_conflicts` — good
- `test_complete_activity_returns_409` — describes the mechanic
- `test_complete_2` — no

One behaviour per test. Arrange / act / assert, separated by blank lines, as in
the examples above.

Fixtures for shared payloads go in `conftest.py` (`activity_payload` is the
pattern). Do not build a fixture used by one test.

## Before you finish

```bash
.venv/bin/pytest -q          # every test
.venv/bin/pytest tests/test_boundaries.py -v   # structure, always
```

Run the boundary suite explicitly. It is the one that catches an architecture
violation, and it is the one whose failure means the sprint cannot pass.

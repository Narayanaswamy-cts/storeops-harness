# Skill: sprint-decomposition

**Purpose.** How to split a StoreOps feature into sprints that the
Generator/Evaluator loop can actually close inside 3 iterations.

Read by: **Planner**.

---

## What a sprint is here

A sprint is **one vertical slice that leaves the repository green.** After every
sprint, all four automated checks pass and all nine (or more) endpoints still
work. A sprint is not a layer, not a file, and not a phase.

The anti-pattern, and why it fails this harness:

```
Sprint 1: add the repository method
Sprint 2: add the service rule
Sprint 3: add the route
```

Sprints 1 and 2 add unreachable code with no test that exercises it, so coverage
drops and `pytest --cov` fails the hard gate. The Evaluator fails a sprint that
cannot be demonstrated. Slice vertically instead:

```
Sprint 1: PATCH /activities/bulk-status — happy path, all items valid
Sprint 2: partial-failure handling — 207 with per-item results
Sprint 3: audit entry per updated activity, published via the bus
```

Each one ships route + service + repository + tests together.

## Sizing

Target **2 to 4 sprints**. One sprint is fine for a genuinely small feature.

A sprint is correctly sized when it touches **1 module plus at most `core/`**,
changes **roughly 3–6 files**, and adds **2–5 acceptance criteria**.

Split when a candidate sprint would:

- touch two feature modules — the cross-module half becomes its own sprint, because event publishing and event handling are independently testable
- add a new event type *and* its subscriber *and* a new endpoint
- need a new `core/` abstraction *and* use it — add it in sprint N, use it in N+1
- change the nine-endpoint assertion in `test_boundaries.py` more than once

Do **not** split when the halves cannot each leave the repo green.

## Sprint ordering

1. **`core/` first.** A new `DomainEvent`, `Settings` field, or error class goes
   in the earliest sprint that needs it. `core` is a leaf, so this never blocks.
2. **Publisher before subscriber.** Publishing `ActivityOverdue` comes before
   alerts reacting to it. The reverse leaves a handler nothing can trigger, and
   the subscriber's test would have to fake the event.
3. **Write before read.** Reports aggregating a new field requires the field.
4. **Happy path before edge cases.** Lets sprint 1 establish the layering the
   Evaluator will hold later sprints to.

## Writing acceptance criteria

Every acceptance criterion is written as **GIVEN / WHEN / THEN**. The three
clauses are not decoration -- each one forces a decision that prose lets you
skip:

- **GIVEN** the starting state. Forces you to name the fixture the test needs.
  "GIVEN three activities in `pending`" is a setup step; "GIVEN some activities"
  is not.
- **WHEN** the single action under test. One request, one service call. Two
  WHENs means two criteria.
- **THEN** the observable outcome, including the status code, the response
  field, *and* the resulting state. A THEN that stops at the status code is the
  failure mode this harness exists to prevent.

```markdown
**AC-1.4** — unknown ids are reported, not fatal
  GIVEN one activity exists in `pending`
    AND the request also names an id that does not exist
  WHEN  PATCH /api/v1/activities/bulk-status is called with both ids
        and status `completed`
  THEN  the response is 207
    AND the result for the real id is `{"result": "updated"}`
    AND the result for the unknown id is
        `{"result": "failed", "error": {"code": "not_found"}}`
    AND re-fetching the real activity shows status `completed`
```

That last `AND` is the one that matters. Without it the criterion is satisfied by
code that returns the right response body and never writes anything.

A criterion is finished when you can name the single test that would fail if it
were violated, and the file that test would point at.



Each AC must be **independently verifiable by a test**, and must name the
observable outcome. The Generator self-checks against these; the Evaluator
scores against them. Vague ACs are the single largest cause of a sprint burning
all 3 iterations.

| Bad | Good |
| --- | --- |
| Handle partial failure | Returns `207` with `results: [{id, status, error?}]`, one entry per requested id, in request order |
| Validate the input | Rejects >100 ids with `422` and `code: "validation_failed"`, `details.field == "activity_ids"` |
| Fire an alert | Publishes exactly one `ActivityOverdue` per breached activity; `alerts` gains one `WARNING` alert with `kind == "activity.overdue"` |
| Good test coverage | Service layer ≥80% line coverage; a test asserts the `ConflictError` branch, not just the 409 status |

Write each AC so its failure names a file. "Returns 207 with per-item results"
fails in `routes.py`; "publishes exactly one event per breach" fails in
`service.py`.

## Mandatory ACs — add these to every sprint

These catch the four client failure modes. The Evaluator gates on them whether
or not the Planner writes them, so writing them makes the contract honest:

1. `ruff check src tests`, `mypy`, `pylint src tests`, `pytest --cov` all pass.
2. No new cross-module import; new cross-module reads go through a `Protocol`
   port injected in `main.py`.
3. Every new failure path raises an `AppError` subclass — no `HTTPException`, no
   bare raises.
4. Every new cross-module side effect is published on the event bus.
5. If the endpoint surface changed, `test_boundaries.py::test_api_exposes_exactly_nine_endpoints`
   is updated in the same sprint.
6. If a new `lru_cache`d service provider was added, it is registered in
   `_PROVIDERS` in `tests/conftest.py`.

ACs 5 and 6 are the two that most reliably cause an otherwise-correct sprint to
fail its first iteration. State them explicitly.

## `spec.md` structure

The Planner writes `.harness/output/spec.md` with exactly these sections:

```markdown
# Spec: <feature name>

## Intent
What the user gets, in 2–4 sentences. Business outcome, not implementation.

## Scope
### In scope
### Out of scope          ← name what a reasonable reader might assume is included

## Architecture impact
| Concern | Decision | Rule |
Which modules change; which events are added; which ports change;
whether the endpoint count changes. Cite architecture-principles rule numbers.

## Sprints
| # | Title | Modules | Files (est.) | Depends on |

## Sprint N — <title>
### Acceptance criteria
AC-N.1 … (numbered, independently testable)
### Files expected to change
### Out of bounds for this sprint

## Risks
Where the Generator is most likely to break a rule, and the legal alternative.

STATUS: AWAITING APPROVAL
```

The final line must be exact. The orchestrator's approval gate greps for it.

## `sprint-N-contract.md` structure

Written at the start of each sprint. It is the Generator's **only** statement of
what to build, so it must be self-contained — the Generator has not read
`spec.md`.

```markdown
# Sprint N contract: <title>

## Objective
One paragraph.

## Acceptance criteria
AC-N.1 … (copied verbatim from spec.md — do not paraphrase)

## Files in scope
Explicit list. The Generator may not create or modify a file outside it
without recording the reason in generator-summary.md.

## Read scope
The narrowest set of existing files to read. Bounds context (CLAUDE.md §6).

## Applicable rules
Rule numbers from architecture-principles, with the specific risk for
this sprint.

## Definition of done
- [ ] All ACs demonstrable by a named test
- [ ] ruff / mypy / pylint / pytest --cov pass
- [ ] Coverage thresholds met (how-to-test)
- [ ] generator-summary.md written with the AC self-check table
```

## The "Risks" section earns its place

For each sprint, name where the Generator will be tempted to break a rule and
give the legal path. This is the highest-leverage thing the Planner writes —
most first-iteration failures are predictable from the feature description.

> **Risk.** The escalation AC needs the Department Lead for a store. The
> Generator will reach for `storeops.modules.staff.service` (violates Rule 1 and
> Rule 5). `StaffDirectory` exposes only `find`, `headcount`, `is_active` —
> there is no lead lookup. **Legal path:** none exists. The port must gain
> `lead_for(store_id, department)` first. If this sprint is approved without
> that, expect escalation — raise it during spec review instead.

If no legal path exists, say so in the spec. Do not let the loop discover it
three iterations later.

## Re-planning

On `@planner --resume`, read the existing `spec.md`, preserve any sprint already
archived in `.harness/reviews/`, and re-emit only the remaining sprints. Never
renumber a completed sprint — the run log references it by number.

# Harness Design Brief — StoreOps Development Harness

Reference application: **StoreOps API** (Python 3.11 / FastAPI, `src/` layout,
five feature modules, in-memory repositories).
Demonstrated feature: **shift handover bulk update** — three sprints, all `PASS`.

This brief explains the reasoning behind [`CLAUDE.md`](CLAUDE.md),
[`.harness/agents/`](.harness/agents/) and [`.harness/skills/`](.harness/skills/).
The harness exists to prevent four failure modes observed in the client codebase
(§2): cross-module repository imports, raw `Error` throws, tests that assert
status codes without verifying business rules, and side effects that bypass the
event bus. Every decision below traces to one of those four.

---

## Section A — Intent Decomposition

### One prompt to four agent responsibilities

The developer supplies `@planner <feature>`. Intent splits along **what each agent
may write** — the only boundary that can be mechanically enforced.

| Agent | Owns the question | Writes |
| --- | --- | --- |
| Planner | *What should exist, in what order?* | `spec.md`, `sprint-N-contract.md` |
| Generator | *How is this sprint built?* | `src/`, `tests/`, `generator-summary.md` |
| Evaluator | *Does it comply?* | `evaluator-feedback.md` only |
| Monitor | *Is the harness improving?* | `sprint-N-run-log.md` only |

The Evaluator may not edit `src/`. This is the load-bearing separation: an agent
that can fix what it finds will fix rather than report, and the audit trail loses
the finding. A single write-and-self-review agent was rejected for the reason a
developer does not approve their own pull request.

### Why the sprint boundaries fall where they do

One rule: **each sprint leaves the repository green and demonstrable.**

| Sprint | Boundary | Why here |
| --- | --- | --- |
| 1 | Endpoint exists; unknown ids reported | Thinnest callable slice. Fixes the response envelope that sprints 2–3 extend without renegotiating. |
| 2 | Transition legality | Independently testable against sprint 1's envelope; needs no new module or event. |
| 3 | Audit trail via the event bus | The only cross-module sprint, isolated deliberately so the sprint risking Rule 2 changes nothing else. |

The rejected alternative was layer-wise decomposition — repository, then service,
then route. It fails mechanically: sprints 1 and 2 would add unreachable code with
no test exercising it, coverage would fall, and `coverage-thresholds` would fail a
sprint that was in fact correct.

Ordering follows one further rule, **publisher before subscriber**: sprint 3 adds
the publisher and its `alerts` handler together, because a handler shipped first
has nothing to trigger it and its test must fabricate the event.

### What makes a criterion testable

Criteria are written **GIVEN / WHEN / THEN**. Each clause forces a decision prose
lets you skip: GIVEN names the fixture, WHEN names exactly one action, THEN names
the observable outcome. The rule doing the real work: **THEN must assert the
resulting state, not only the response.** A criterion ending at the status code is
satisfiable by code that returns the right body and writes nothing — failure mode
3 exactly.

### Example sprint contract entry, in full

From [`sprint-1-contract.md`](.harness/reviews/sprint-1-contract.md), AC-1.4:

```
AC-1.4 — an unknown id is reported per item, not fatal to the batch

GIVEN one activity exists with status `pending`
  AND the request also names an activity id that does not exist
WHEN  PATCH /api/v1/activities/bulk-status is called with both ids
      and status `completed`
THEN  the response status is 207
  AND the result for the real id is {"result": "updated"}
  AND the result for the unknown id is
      {"result": "failed", "error": {"code": "not_found"}}
  AND re-fetching the real activity shows status `completed`

Demonstrated by: tests/test_activities.py::
  test_bulk_status_reports_unknown_ids_without_failing_the_batch
Layer: the decision belongs in service.py; routes.py may contain no
  conditional on a domain status value (Rule 4)
```

The final `AND` is the point. Without it, partial application is unproven.

**Disclosure.** The archived contracts state these criteria as numbered prose
assertions rather than GIVEN/WHEN/THEN clauses. The content is identical — each
names a starting state, one action, a status code and a state assertion — but the
syntax was adopted in `sprint-decomposition/SKILL.md` after the run. The
artefacts were left unedited as a historical record.

---

## Section B — Governance Framework

### Skill file strategy

Skill files are feedforward: read before acting, never written to. They are
divided by which agent needs them, so no agent loads governance it cannot act on.

| Skill file | Read by | Encodes, specific to StoreOps |
| --- | --- | --- |
| `app-context` | all four | Five modules; `main.py` as sole legal composer; `wire_modules()` must stay synchronous because tests drive the app over `httpx.ASGITransport` with no lifespan events |
| `architecture-principles` | all four | Six rules, each with violating shape, legal shape, and the test that catches it |
| `sprint-decomposition` | Planner | Sprints leave the repo green; publisher-before-subscriber; six mandatory ACs |
| `coding-conventions` | Generator | `ActivityService` defines a method named `list`, so a bare `list[...]` annotation in that class fails `mypy --strict`; parsed JSON is `dict[str, Any]`, never `dict[str, object]` |
| `how-to-test` | Generator | Failure-path tests assert `error["code"]`, not just status; `EventBus.publish` swallows handler exceptions, so event counts must be exact |
| `how-to-review` | Evaluator | The four commands with required flags; reading each against the baseline |
| `evaluation-criteria` | Evaluator | Dimensions, weights, hard gates, verdict algorithm |

The first two are shared because every role needs them: the Planner cannot place
work without the module map, and the Evaluator cannot judge a boundary violation
without the same map the Generator built against. One correction propagates to
every role at once.

None of these would transfer to another codebase. `coding-conventions` naming
`ActivityService.list` as a hazard is not a Python convention; it is a fact about
this class, discovered when it cost sprint 1 an iteration.

### `.harness/reviews/` as a governance audit trail

Per sprint: the contract (what was asked), the generator summary (what was
claimed, with an AC self-check table), the evaluator feedback (verdict, per-check
results, file-and-line findings), the run log (iterations, score trend, cost,
drift vs baseline), plus every failed iteration and `BASELINE.md`.

The chain is **contract → claim → verdict**, which makes a `PASS` auditable
rather than assertive. It is committed, so anyone with repository read access sees
it: reviewers, tech leads, the next developer into the module.
`.harness/output/` is gitignored, since in-flight scratch would dirty every tree.
Failed iterations are retained deliberately — a sprint passing on iteration 3 is
not equivalent to one passing on iteration 1, and deleting the failures hides
whether the harness converges or thrashes.

**How a recurring issue surfaces.** The Monitor reads every prior run log and
reports *Recurring findings*, naming the skill file that should have prevented
each repeat. Here that produced the run's most useful observation: **all three
sprints failed their first iteration on something `pytest` could not see** — a
shadowed builtin, a wrong annotation, then ten lint messages — with a fully green
suite each time, and no sprint ever broke an architecture rule. That told me the
architecture skills were working and `coding-conventions` was the weak file, a
conclusion no single sprint's feedback could reach.

### One skill rule traceable to a StoreOps constraint

From `architecture-principles`, **Rule 2 — Event bus only:**

> A side effect crossing a module boundary is published as a `DomainEvent`, never
> by importing the reacting module. Payloads carry primitives only — never a
> Pydantic model or another module's domain record.

**What breaks without it.** Sprint 3 needed an audit entry per updated activity.
The direct implementation is three lines:

```python
from storeops.modules.alerts.service import AlertService    # violation
await AlertService().raise_alert(...)
```

That compiles, passes every functional test, and produces correct entries. It
also makes `activities` unable to build without `alerts`. The moment `alerts`
needs anything from `activities` — an activity title for a message — the cycle is
real and both must be rewritten together. Nothing in the type system warns you,
and the failure appears months later in an unrelated module.

The second clause matters as much: an event carrying an `Activity` model
re-creates the dependency through the payload, since the subscriber must import
`activities` to read it. `ActivityStatusChanged` carries `from_status` and
`to_status` as `str`, which also keeps `core/` a leaf.

Enforced by `test_no_module_imports_the_alerts_package`. Deliberately **not** by
ruff's `banned-api`: that entry is unscoped in `pyproject.toml` and reports 13
violations on the untouched baseline, including `main.py`'s legitimate
composition-root imports and ten cases of `alerts` importing itself.

---

## Section C — Non-Determinism Strategy

### Dimensions and weights

| # | Dimension | Wt. | Why this weight for StoreOps |
| --- | --- | --- | --- |
| 1 | Acceptance criteria satisfaction | 35% | Largest share: a sprint that complies perfectly and delivers nothing is still a failure. |
| 2 | Architectural compliance | 30% | Three of the four client failure modes are architectural. |
| 3 | Test quality | 20% | The fourth failure mode *is* shallow tests. Needs its own dimension because coverage does not detect it. |
| 4 | Code quality and conventions | 15% | Smallest: most automatable, least likely to cause an incident. |

Dimensions 2 and 3 total 50% because architecture drift and shallow tests are the
two things a passing CI pipeline does not catch — the harness's whole reason to
exist.

### Hard gates

A hard gate fails the sprint regardless of score. Five of six are a tool's exit
state or a named test result, with no judgement.

| Gate | Failure mode prevented | Why it cannot be soft |
| --- | --- | --- |
| `mypy-clean` | Type errors invisible to tests. Sprint 1 shipped 3 mypy errors with **65 of 65 tests passing**, because `from __future__ import annotations` defers evaluation. | A soft check gets outscored. Sprint 1 scored 92.5 — above the 80 threshold — and would have shipped. |
| `boundary-imports` | Cross-module repository imports (mode 1) | An import cycle is not a matter of degree. |
| `error-contract` | Raw `Error` throws (mode 2) | One bare raise breaks the `{"error": {...}}` envelope for every client. |
| `tests-green` | Regression | A failing test states the code is wrong. No partial credit. |
| `no-lint-regression` | Accumulating debt | Measured against the recorded baseline, not zero. |
| `event-bus-only` | Bypassing the bus (mode 4) | Cheap to write, invisible in behaviour — every test passes either way. |

The `mypy-clean` row is the empirical argument for hard gates. It happened, the
numbers are in
[`sprint-1-iter-1-evaluator-feedback.md`](.harness/reviews/sprint-1-iter-1-evaluator-feedback.md),
and a score-only design would have shipped it.

### Producing the same verdict from variable output

Four rules. **Push determinism into tools**: five of six gates are an exit state.
**Narrow binary questions**: not "is the layering good" but *does this route
contain a conditional whose branches depend on a domain status value?*
**Evidence or discard**: a finding without `file:line` and a quoted excerpt is
dropped before scoring, guarding against both a lenient run inventing credit and
a harsh one inventing faults. **Ambiguity resolves to `BLOCKED`, never `PASS`**:
silence is never success.

**Worked example — sprint 1, iteration 1.** The output was variable in every way
that mattered: the Generator chose the helper names, response model shape,
de-duplication strategy and test names, none of it specified. The verdict was
still forced:

```
1. Run the four commands.
   mypy . -> "Found 3 errors in 1 file"        [captured verbatim]
2. Evaluate the six hard gates, BEFORE scoring.
   mypy-clean: exit status non-zero            -> FAIL
   remaining five: pass
3. Score the dimensions.
   9/10 ACs, 6/6 architecture, 5/5 tests,
   mypy 0/4 within dimension 4                 -> 92.5
4. Apply the algorithm.
   any hard gate FAIL                          -> VERDICT: FAIL
```

Any run on that code reaches `FAIL`, because step 2 reads a process exit status
and precedes all judgement. The score is still reported, because the Monitor
needs the trend: 92.5 then 100 is convergence, 92.5 twice is thrashing. Iteration
2 moved two helpers to module scope and the same algorithm returned `PASS` at 100.

### Escalation path

**Triggers.** Three iterations exhausted; or `VERDICT: BLOCKED` (contradictory
criteria, a criterion unsatisfiable without breaking a hard rule, a gate that
cannot run); or one sprint exceeding ~200k tokens. A `BLOCKED` escalates
immediately and **does not consume an iteration** — a wrong `PASS` ships an
architecture violation, a wrong `BLOCKED` costs five minutes.

**Contents** of `escalation.md`: sprint id and title, iterations used, trigger,
estimated token cost, the blocking issue with **file and line**, a per-iteration
table of verdicts and failed gates, a diagnosis separating a spec defect from a
Generator defect, and a named recommended action.

**Recipient.** The developer who started the run. The orchestrator stops the whole
run — it does not advance, because later work on unmerged code compounds the
failure — and prints the path.

**Expected response.** Act on the recommendation, then `@planner --resume`, which
preserves archived sprints and re-emits only what remains. The realistic case is
in `CLAUDE.md` §5: a criterion needs a Department Lead lookup, `StaffDirectory`
exposes only `find`, `headcount` and `is_active`, no legal path exists, and the
escalation names `staff/port.py` as the file that must change first. **An
escalation is a successful outcome** — strictly better than a Generator that
satisfies the criterion by quietly breaking a boundary rule.

---

## Section D — Architectural Decisions

### Decision 1 — Gate on regression from a recorded baseline, not on zero

**Decision.** Hard gates compare against `BASELINE.md`. The recorded baseline was
35 ruff errors, one failing test, and `pytest-cov` absent.

**Alternatives.** (a) Absolute gates — zero errors, all tests green. (b) Repair
the baseline first, then gate absolutely.

**Rationale.** (a) fails every sprint on faults it did not cause, and a verdict
that is always `FAIL` is one developers learn to ignore. (b) is right long-term
but front-loads unrelated work before the harness runs once, conflating "fix the
scaffold" with "demonstrate the harness". The baseline made every `FAIL` in this
run attributable.

**Assumption.** The baseline is re-recorded whenever it legitimately changes. This
nearly failed: sprint 1 repaired the failing endpoint test, so `tests-green`
briefly carried an allowance for a test that no longer existed. A stale baseline
silently widens every gate. `BASELINE.md` was re-recorded twice.

### Decision 2 — Fresh subagent per invocation, handoff by file only

**Decision.** Every invocation is a new subagent; agents communicate only through
structured files in `.harness/output/`; the orchestrator routes **paths, never
content**, and never reads `src/`.

**Alternatives.** (a) One long-lived conversation. (b) Orchestrator reads each
artefact and passes content onward.

**Rationale.** (a) degrades — by sprint 3 the context holds every file every agent
touched, and the Generator reasons about sprint 1's review while writing sprint 3.
(b) makes orchestrator context grow with run length for no benefit. Routing paths
keeps it constant and produces the audit trail for free: the handoff files *are*
the archive, so observability is a property of the communication mechanism rather
than added instrumentation.

**Assumption.** Handoff files are complete enough to act on without the
originating conversation — hence fixed headings and a mandatory AC self-check
table, since a retry reads the feedback file, not the previous transcript. It
held: iteration 2 of each sprint was written with no access to iteration 1's
reasoning.

### Decision 3 — The audit trail is recorded by `alerts`, not a sixth module

**Decision.** `activities` publishes `ActivityStatusChanged`; `alerts` subscribes
and records an `info` entry with `kind == "activity.status_changed"`.

**Alternatives.** (a) A new `audit` module. (b) An `audit_log` written directly by
the activities service.

**Rationale.** (a) breaks the fixed five-module structure that `app-context` and
`test_every_module_contributes_all_three_layers` both encode, and a Generator
inventing a module mid-sprint is the improvisation the harness exists to prevent.
(b) keeps the write in one module but makes the trail invisible to the system and
bypasses the bus, demonstrating nothing. `alerts` already stores `kind`,
`severity`, `message` and `source_event`; an audit entry is an alert nobody needs
to action.

**Assumption.** Audit entries and operational alerts can share a store,
distinguished by `kind`. This is the design's weakest assumption. Audit records
are normally immutable and longer-retained, and `alerts` exposes
`POST /alerts/{id}/acknowledge` — so an audit entry is currently acknowledgeable.
At real volume the concerns diverge and the `audit` module becomes correct.
Acceptable for a reference application with in-memory storage, and recorded here
so the next architect knows it was a considered trade, not an oversight.

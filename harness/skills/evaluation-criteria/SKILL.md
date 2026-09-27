# Skill: evaluation-criteria

**Purpose.** The graded evaluation framework: four weighted dimensions, their
hard gates, every check with explicit pass/fail criteria, and the rules that
make an LLM-produced verdict deterministic.

Read by: **Evaluator**. Method lives in `how-to-review`; this file is the rubric.

---

## Verdict algorithm

Evaluate in this exact order. Do not reorder — gates are checked before scoring
so that a boundary violation cannot be outweighed by good tests.

```
1. Run all automated checks. Any tool fails for an environmental reason  → BLOCKED
2. Evaluate all 6 hard gates.  Any gate FAIL                            → FAIL  (score still reported)
3. Score all 4 dimensions. Weighted total < 80                          → FAIL
4. Any finding you cannot pin to file+line, or contradictory ACs        → BLOCKED
5. Otherwise                                                            → PASS
```

The pass threshold is **80**. Rationale: with hard gates already catching every
architecture violation, the score measures completeness and test quality. 80
allows one under-tested edge case through; it does not allow a missing
acceptance criterion, which costs more than 20 points in Dimension 1.

Report the score even on `FAIL` — the Monitor reads the score trend across
iterations to tell convergence from thrashing.

## Dimensions

| # | Dimension | Weight | What it measures |
| --- | --- | --- | --- |
| 1 | Acceptance criteria satisfaction | 35% | Does the sprint do what the contract said |
| 2 | Architectural compliance | 30% | The six rules in `architecture-principles` |
| 3 | Test quality | 20% | Do the tests verify rules, not status codes |
| 4 | Code quality and conventions | 15% | Automated checks and `coding-conventions` |
| | | **100%** | |

Weighting reflects the failure modes this harness governs. Dimensions 2 and 3
together are 50% because architecture drift and status-code-only tests are two
of the four client failure modes and neither is caught by a pipeline.

---

## Hard gates

A hard gate fails the sprint regardless of score. Each is **deterministic**:
same check result, same verdict, every run. Four of the six are a tool's exit
state or a named test's result, with no judgement at all.

| Gate | Determined by | Fails when |
| --- | --- | --- |
| `mypy-clean` | `.venv/bin/mypy .` exit code | Any error. Absolute — baseline is clean, so there is no allowance. Must be `mypy .` (46 files); bare `mypy` honours `packages = ["storeops"]` and skips `tests/`. |
| `boundary-imports` | `pytest tests/test_boundaries.py -k "import or acyclic or staff_read_only or core_never or only_main"` | Any listed test fails |
| `error-contract` | `pytest tests/test_boundaries.py -k "raise_only_app_errors or subclasses_app_error"` + grep for `HTTPException` | Either test fails, or `HTTPException` appears in `src/` |
| `tests-green` | `.venv/bin/pytest -q` | Any failure other than the one known baseline failure, or fewer passing than baseline |
| `no-lint-regression` | `.venv/bin/ruff check src tests` count vs `BASELINE.md` | Error count exceeds baseline, or any new error in a file this sprint touched |
| `event-bus-only` | LLM-assessed, single question | A cross-module side effect is executed by direct import/call rather than `bus.publish` |

### Why `boundary-imports` uses the test suite and not `ruff`

The obvious automated check for Rule 1 would be ruff's `banned-api`. It is
unusable as a gate: `pyproject.toml` bans `storeops.modules.alerts` unscoped, so
it reports 13 violations on the untouched baseline — `main.py`'s three
legitimate composition-root imports, ten of alerts importing itself, and
`conftest.py`. Gating on it fails every sprint immediately.

`tests/test_boundaries.py` implements the same rule correctly, because it knows
which module owns each file (`_owning_module`) and permits intra-module imports,
`core`, and `staff.port`. It is therefore the authority for Rule 1 and Rule 2.

### `event-bus-only` — the one judged gate

Reduced to a single yes/no question, asked once per changed file:

> Does this file cause an effect in a module other than its own, by any means
> other than `bus.publish(...)`?

Yes → gate fails, cite file and line. No → passes. Do not weigh intent,
convenience, or whether the direct call is tidier.

---

## Dimension 1 — Acceptance criteria satisfaction (35%)

Per AC in `sprint-N-contract.md`:

| Result | Criteria | Credit |
| --- | --- | --- |
| `PASS` | A named test demonstrates it, and that test asserts the outcome the AC states | Full |
| `PARTIAL` | Behaviour implemented and a test exists, but the test asserts less than the AC states (e.g. AC says "exactly one event", test accepts one-or-more) | Half |
| `NOT DEMONSTRATED` | No test, or the named test does not exercise the AC | Zero |
| `FAIL` | Implemented incorrectly, or absent | Zero |

Score = `(sum of credit / count of ACs) × 35`.

Determinism rules:
- Name the test as `path::test_name`. Cannot name one → `NOT DEMONSTRATED`.
- Read the test body. A matching name is not evidence.
- Code that looks correct with no test is `NOT DEMONSTRATED`, never `PASS`.
- An AC requiring a capability that does not legally exist → `BLOCKED`, not zero.

## Dimension 2 — Architectural compliance (30%)

Six checks, 5 points each. Any failure here also trips a hard gate, so this
dimension is about *where* the violation is, for the feedback.

| Check | Fails when |
| --- | --- |
| `layer-routes-thin` | A route holds a business rule, calls a repository, or builds a domain record |
| `layer-service-clean` | A service references HTTP, or imports another feature module |
| `layer-repo-dumb` | A repository raises, publishes, or calls a service |
| `domain-wire-split` | A domain record is returned from a route without a `*Read` projection |
| `ports-read-only` | A port gained a mutating method, or `reports` originates a write |
| `core-is-leaf` | `core/` imports a feature module, or a non-`main` file composes two modules |

`layer-routes-thin` is judged by one question: *does this route contain a
conditional whose branches depend on a domain state value?* Shape validation
(`if payload.ids is None`) is legal. State logic (`if activity.status is
COMPLETED`) belongs in the service.

## Dimension 3 — Test quality (20%)

Five checks, 4 points each. This is the dimension that catches failure mode 3.

| Check | Fails when |
| --- | --- |
| `asserts-error-codes` | Any failure-path test asserts only `status_code`, without `error["code"]` |
| `asserts-state-change` | Any business-rule test asserts the response but not the resulting state |
| `asserts-event-counts` | An event test asserts presence without asserting the exact count |
| `inversion-sensitive` | Inverting a comparison in a changed service method would leave the suite green |
| `coverage-thresholds` | Below §3.6 thresholds — service 80%, routes 70%, `core` 60%, overall 70% |

`coverage-thresholds` is currently **unmeasurable**: `pytest-cov` is absent from
the `dev` extra, so `pytest --cov` exits with `unrecognized arguments: --cov`.
Handling, in order of preference:

1. If `pytest-cov` is installed, measure and gate normally.
2. If not, record the check as `BLOCKED`, **redistribute its 4 points across the
   other four checks in this dimension** (5 points each), and state the
   substitution in the feedback. Do not award the 4 points by default, and do not
   silently drop `--cov`.

`inversion-sensitive` is assessed by reading, not by running: pick the most
important conditional the sprint added and ask whether any test would fail if it
were inverted. Name the test that would fail. If you cannot, the check fails.

## Dimension 4 — Code quality and conventions (15%)

| Check | Points | Fails when |
| --- | --- | --- |
| `mypy-strict` | 4 | Any error (also a hard gate) |
| `ruff-no-regression` | 4 | Errors above baseline, or a new error in a touched file |
| `pylint-no-regression` | 3 | Score below baseline 9.45/10, or any new `E` message. Run `pylint src tests --jobs=1` -- the parallel default is non-deterministic |
| `conventions` | 4 | Missing `__all__`, missing `from __future__ import annotations`, `Optional[X]` instead of `X | None`, camelCase attribute, mutation of a frozen model by assignment, or a `noqa` without a `--` reason |

All four are mechanical. `conventions` is a checklist read against
`coding-conventions`, not an aesthetic judgement.

---

## Handling LLM output variability

The Generator produces different code for the same contract on different runs.
These rules keep the *verdict* stable anyway.

**1. Push determinism into tools.** Four of six hard gates are a tool's exit
state. The evaluation is therefore mostly not an LLM judgement at all — which is
the point. When adding a gate, prefer one a tool can decide.

**2. Narrow, binary questions.** Each check is one yes/no about observable code.
No check asks whether something is "clean", "idiomatic", or "well-designed" —
those vary between runs. `layer-routes-thin` asks about a conditional on a domain
state value; two reviewers agree on that.

**3. Evidence or discard.** A finding without `file:line` and a quoted excerpt is
dropped before scoring. This is the main guard against a lenient run inventing
credit or a harsh run inventing faults.

**4. No partial credit inside a check.** One violation fails the check. Half
credit exists only in Dimension 1, where `PARTIAL` has a written definition
("test asserts less than the AC states"). Granularity comes from 20 narrow
checks, not from graded opinions.

**5. Baseline-relative, never absolute.** Gates compare to `BASELINE.md`. An
absolute "zero ruff errors" gate would fail every sprint on 35 pre-existing
faults, and an Evaluator whose verdict is always `FAIL` teaches the developer to
ignore it.

**6. Ambiguity resolves to `BLOCKED`, never to `PASS`.** A missing or
unparseable verdict line is treated as `BLOCKED` by the orchestrator
(CLAUDE.md §4). Silence is never success.

**7. Fixed output shape.** The template in `how-to-review` has fixed headings so
the orchestrator parses one line and the Monitor reads one table. Free-form
feedback cannot be routed.

### Fallback when the Evaluator's own output is ambiguous

Self-check before emitting. If any holds, change the verdict to `BLOCKED` and
say which:

- The `VERDICT:` line is absent, or appears more than once.
- A finding has no `file:line`.
- `SCORE` disagrees with the dimension table's arithmetic.
- A hard gate is marked `FAIL` while the verdict is `PASS`.
- An AC is marked `PASS` with no test named.
- Two findings contradict each other.

The orchestrator escalates `BLOCKED` without consuming an iteration, so the
conservative choice is cheap. A wrong `PASS` ships an architecture violation; a
wrong `BLOCKED` costs a developer five minutes.

---

## Gate summary

| Gate | Type | Baseline allowance |
| --- | --- | --- |
| `mypy-clean` | Automated | None — absolute |
| `boundary-imports` | Automated | None |
| `error-contract` | Automated | None |
| `tests-green` | Automated | 1 known failure: `test_api_exposes_exactly_nine_endpoints` |
| `no-lint-regression` | Automated | 35 ruff errors; pylint 9.45/10 serial |
| `event-bus-only` | LLM-assessed | None |

Five of six are automated, satisfying the case-study §5.4 recommendation of at
least one automated hard gate per dimension. Every allowance is a named,
recorded baseline defect — not a tolerance band.

**When the baseline is repaired**, tighten in this order and update
`BASELINE.md`: scope the `TID251` ban via `per-file-ignores`, fix
`test_api_exposes_exactly_nine_endpoints` to read `app.openapi()["paths"]`, add
`pytest-cov` to the `dev` extra, then reduce the ruff allowance to zero and make
`coverage-thresholds` a hard gate.

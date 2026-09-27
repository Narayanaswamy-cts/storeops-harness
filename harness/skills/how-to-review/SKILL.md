# Skill: how-to-review

**Purpose.** The Evaluator's review procedure: which commands to run, in what
order, how to read their output, and how to turn a judgement into a per-check
pass/fail. Scoring and gate weights live in `evaluation-criteria`; this file is
the method.

Read by: **Evaluator**.

---

## Stance

You are a reviewer, not a fixer. **You may not edit `src/` or `tests/`.** If you
find a defect, report it with a file, a line, and the rule it breaks. A verdict
that says "fixed it" is a protocol violation.

Assume the Generator is competent and the spec is fallible. When code and
acceptance criterion disagree, say which you believe is wrong. An AC that cannot
be satisfied legally is a `BLOCKED`, not a `FAIL` — see §5.

## Procedure

Run in this order. Stop early only on a tooling failure you cannot attribute.

### Step 1 — Read the contract, not the code

Read `.harness/output/sprint-N-contract.md` first, then
`.harness/output/generator-summary.md`. Establish what was *claimed* before
looking at what was written. Reading code first anchors you to the
implementation's own logic.

### Step 2 — Scope the diff

```bash
git diff --stat HEAD
git diff HEAD -- src tests
```

Compare the changed-file list against **Files in scope** in the contract. A file
changed outside scope without a recorded reason in the summary is a finding.

Review only the diff plus the files it directly touches. Do not read the whole
of `src/` — see CLAUDE.md §6.

### Step 3 — Automated checks

Run all four from the repository root. Use the venv binaries; do not assume the
shell PATH.

```bash
.venv/bin/ruff check src tests --output-format=concise
.venv/bin/mypy .
.venv/bin/pylint src tests --jobs=1
.venv/bin/pytest -q
.venv/bin/pytest --cov          # see the coverage caveat below
```

There is no separate harness lint config. These read `pyproject.toml`, exactly
as CI does (CLAUDE.md §7).

#### Check what a gate actually covers, not just whether it passed

Print and read the scope line, not only the exit status. `mypy .` ends with
`checked 46 source files`; bare `mypy` says `37`. The `mypy-clean` gate ran the
narrow form for two sprints and reported success while four real errors sat in
`tests/`. A gate that cannot see a third of the tree gives false confidence, and
a passing gate is the hardest kind of defect to notice.

Same habit for the others: `pytest` prints the passing count, `pylint --jobs=1`
prints the message count. Compare both against `BASELINE.md`, not just the
headline.

#### Reading the output against the baseline

**The untouched repository does not pass all four checks.** Baseline state is
recorded in `.harness/reviews/BASELINE.md`. Gate on **regression from baseline**,
never on absolute zero, or every sprint fails on faults it did not cause.

| Check | Baseline | How to read it |
| --- | --- | --- |
| `ruff` | 35 errors | Count errors. More than baseline, **or any new error in a file the sprint touched**, is a fail. |
| `mypy` | clean (46 files) | Any error at all is a fail. This is the one absolute gate. Run `mypy .`, not bare `mypy`: `pyproject.toml` sets `packages = ["storeops"]`, so the bare form checks 37 files and never type-checks `tests/`. Section 2.3 of the brief documents `mypy .` as the verification command. |
| `pylint` | 9.45/10, 23 messages | Score below baseline, or any new `E`-category message, is a fail. Always pass `--jobs=1`: with the parallel default pylint's import resolution is order-dependent and drops findings, so the score is not repeatable. |
| `pytest` | 1 failed, 56 passed | The one known failure is `test_api_exposes_exactly_nine_endpoints`. Any *other* failure is a fail. A drop in passing count is a fail. |
| `pytest --cov` | unusable | `pytest-cov` is not installed. Record the coverage gate as `BLOCKED`. Do not drop `--cov` to force a pass. |

Re-derive the baseline yourself if `BASELINE.md` is older than the last
dependency change. A stale baseline silently widens the gates.

**The known baseline failures, and why they are not the sprint's fault:**

1. **13 × `TID251`** — `pyproject.toml` bans `storeops.modules.alerts` without
   scoping, so it fires on `main.py` (the legitimate composition root), on
   alerts' own ten intra-module imports, and on `tests/conftest.py`. The rule's
   *intent* — no other feature module imports alerts — is correctly enforced by
   `test_boundaries.py::test_no_module_imports_the_alerts_package`. Judge Rule 2
   by that test, not by the TID251 count.
2. **14 × `EM101`/`EM102`** — the scaffold's own `raise AppError("literal")`
   style violates the `EM` rules it enabled.
3. **3 × `RUF100`** — dead `noqa` directives naming rules (`BLE001`, `S101`,
   `PLW0603`) that are not in the `select` list.
4. **`test_api_exposes_exactly_nine_endpoints`** — FastAPI 0.141 / Starlette 1.7
   register a lazy `_IncludedRouter` instead of copying `APIRoute`s into
   `app.routes`, so the test's filter finds nothing.

None were introduced by a Generator. All four are defects in the baseline
repository, and each is a legitimate finding to *report* — but they may not
cause a sprint to fail.

### Step 4 — Architecture review

Automated checks cannot see Rule 4 at all (`architecture-principles`). Read each
changed file and answer these, each strictly yes/no:

**Layer separation** (`routes` → `service` → `repository`)

- Does any route contain a conditional that encodes a business rule, rather than
  input shape? A route may validate a shape; it may not decide a state transition.
- Does any route call a repository, or construct a domain record?
- Does any service reference `Request`, `Response`, a status code, or an HTTP verb?
- Does any repository raise an `AppError`, publish an event, or call a service?
- Is the domain record returned from a route without a `*Read` projection?

**Event bus**

- Is every cross-module side effect published, rather than called?
- Does any event payload carry a Pydantic model or another module's domain type
  instead of primitives?
- Does a service obtain the bus via `get_event_bus()` in its own body instead of
  receiving it as a parameter?
- Does any code depend on a subscriber's side effect for its own return value or
  status code? `EventBus.publish` swallows handler exceptions, so this is always
  a defect even when the test passes.

**Error contract**

- Is any `HTTPException` raised? (Not caught by the AST boundary test, which
  only checks the name is in `errors.__all__`.)
- Does the chosen subclass match the semantics — 409 for state conflict, 422 for
  a violated business rule, 404 for absent?
- Does `details` carry machine-readable context rather than prose or a trace?

**Read-only modules**

- Does anything outside `staff` import beyond `staff.port`?
- Does `reports` originate any write?
- Did `staff/port.py` gain a mutating method?

**Test quality** — the highest-value judgement you make

- Does each failure-path test assert `error.code`, not just the status?
- Does each business-rule test assert the state change, or its absence?
- Are event tests asserting the exact count?
- Is there a test that would fail if the rule were inverted? If flipping a
  comparison in the service leaves the suite green, the rule is untested.

### Step 5 — Acceptance criteria

For each AC in the contract, name the test that demonstrates it and give
`PASS` / `FAIL` / `NOT DEMONSTRATED`. An AC with no test is `NOT DEMONSTRATED`
and scores zero — regardless of whether the code looks right.

Cross-check against the Generator's self-check table. A claimed pass you cannot
reproduce is a finding in its own right, and a more serious one than a missing
test.

## Converting judgement into a binary result

LLM assessment varies run to run. These rules make it repeatable.

**1. Every check is a yes/no question about observable code.** Not "is the
layering good" but "does `routes.py` contain a conditional on a domain state
value". The second has one answer.

**2. Cite a file and line, or it did not happen.** A finding without a location
is discarded before scoring. This is the strongest single defence against
inventing problems.

**3. One violation fails the check.** No severity judgement, no partial credit
inside a check. Granularity comes from having many narrow checks.

**4. Quote the evidence.** Paste the offending line into the feedback. If you
cannot quote it, you cannot claim it.

**5. Absence of evidence is a fail, not a pass.** Cannot find the test for
AC-2.3? `NOT DEMONSTRATED`. Do not infer that it must exist.

**6. Judge the diff, not the repository.** Pre-existing violations in untouched
files are reported under `## Pre-existing findings` and excluded from scoring.

## When you cannot decide

Emit `VERDICT: BLOCKED`. It is the correct answer, not an admission of failure —
the orchestrator escalates to a human without consuming an iteration
(CLAUDE.md §4).

Use `BLOCKED` when:

- Two ACs contradict each other, or an AC contradicts `architecture-principles`.
- An AC cannot be satisfied without breaking a hard rule — e.g. it needs a staff
  lookup that `StaffDirectory` does not expose. **Name the missing capability
  and the file that must change.**
- A check cannot be run (`pytest-cov` missing) and it gates the verdict.
- A tool fails for an environmental reason — import error, missing dependency,
  wrong interpreter — rather than a code reason.
- You have written a finding you cannot pin to a line.

Do **not** use `BLOCKED` merely because a call is close. Prefer `FAIL` with the
reasoning stated; the Generator gets file-and-line feedback and one more attempt.

## `evaluator-feedback.md` structure

Write exactly this shape. The orchestrator parses the verdict line and the
failed-check list only.

```markdown
# Evaluator feedback — sprint N, iteration K

VERDICT: PASS | FAIL | BLOCKED
SCORE: 84 / 100

## Hard gates
| Gate | Result | Evidence |
| --- | --- | --- |
| mypy-clean | PASS | `Success: no issues found in 39 source files` |
| boundary-imports | FAIL | `src/storeops/modules/alerts/service.py:88` |

## Dimension scores
| Dimension | Weight | Score | Weighted |

## Failed checks
- `boundary-imports` — src/storeops/modules/alerts/service.py:88

## Acceptance criteria
| AC | Result | Demonstrated by |
| --- | --- | --- |
| AC-2.1 | PASS | `tests/test_alerts.py::test_breach_raises_alert` |
| AC-2.2 | NOT DEMONSTRATED | — |

## Findings
### 1. [hard gate: boundary-imports] Cross-module import into staff
`src/storeops/modules/alerts/service.py:88`
```python
from storeops.modules.staff.service import StaffService
```
Breaks architecture-principles Rule 1 and Rule 5. `staff` exposes only
`staff.port`. **Legal alternative:** `StaffDirectory` has no lead lookup, so
there is none — see BLOCKED guidance.

## Pre-existing findings (not scored)
- 35 baseline ruff errors, unchanged. See BASELINE.md.

## Automated check output
<the four commands and their tail output, verbatim>
```

Findings are ordered hard gates first, then by descending weight. Each one
carries a file, a line, a quoted excerpt, the rule broken, and the legal
alternative — or an explicit statement that none exists.

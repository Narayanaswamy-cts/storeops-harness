# Run log — sprint 3

SPRINT: 3 — "Audit trail via the event bus"
VERDICT: PASS
ITERATIONS USED: 2 of 3
ESCALATED: no
ESTIMATED TOKEN COST: ~61k (estimate: one Generator pass over 6 files, one lint-correction pass, two Evaluator reviews)
COMPLETED: 2026-09-26T18:30:00Z

## Iteration history

| K | Verdict | Score | Hard gates failed | Fixed from previous |
| --- | --- | --- | --- | --- |
| 1 | FAIL | — | `no-lint-regression` | — |
| 2 | PASS | 100 | — | 8 × C0415 hoisted, 1 × C1803, 1 × W0613, 1 × I001 |

## What the sprint delivered

An audit trail for shift handovers, produced without `activities` knowing that
`alerts` exists. `core/events.py` gained `ActivityStatusChanged`, carrying
primitives only so `core` stays a leaf. The activities service publishes one
event per successfully updated activity, after the write, and additionally
publishes `ActivityCompleted` when the target is `completed` so bulk completion
is indistinguishable from the single-activity route. `alerts/subscribers.py`
records an `info` alert per event. `main.py` was not touched.

## Quality trend

| Sprint | Iterations | Final score | First-iteration failure class |
| --- | --- | --- | --- |
| 1 | 2 | 100 | static typing (shadowed builtin) |
| 2 | 2 | 100 | static typing (wrong annotation, then suppressed) |
| 3 | 2 | 100 | lint conventions (imports, comparisons, unused arg) |

Three sprints, three passes, two iterations each, and **no architectural
violation in any first iteration.** Not one sprint broke a module boundary,
bypassed the bus, raised a bare error, or put business logic in a route — across
three sprints whose acceptance criteria were specifically designed to tempt each
of those.

The failure mode is consistently the same category: mechanical code quality that
`pytest` cannot see. All three first-iteration failures had a fully green test
suite. That is the clearest evidence in this run that tests alone are not a
quality gate, and it is the argument for keeping all four automated checks as
hard gates rather than relying on the test runner.

The trend also shows the skill files working: sprint 3's failure class moved
*away* from typing after `coding-conventions` was updated twice, and the
no-suppression rule added after sprint 2 was followed on its first opportunity
in sprint 3.

## Check drift vs BASELINE.md

| Check | Baseline (post-sprint-1) | Now | Delta |
| --- | --- | --- | --- |
| ruff errors | 35 | 35 | 0 |
| mypy (46 files) | clean | clean | 0 |
| pylint | 9.45/10, 23 msgs | 9.48/10, 23 msgs | +0.03 |
| pytest passing | 65 | 77 | +12 |
| pytest failing | 0 | 0 | 0 |
| coverage overall | 97% | 97% | 0 |

Coverage held at 97% while 12 tests and roughly 100 lines of source were added,
which means the new code is covered at about the same rate as the existing code
rather than diluting it.

## Recurring findings

- **Every first iteration fails on something `pytest` cannot see.** Three for
  three. Typing twice, lint once.
- **`TID251` remains useless as a signal.** 13 pre-existing errors, two of them
  now in `alerts/subscribers.py` — the file that legitimately imports its own
  module. Rule 2 was judged by `test_no_module_imports_the_alerts_package` in
  all three sprints, as `architecture-principles` instructs.
- **AC-2.2 is still untestable** (carried from sprint 2). `CANCELLED` is
  terminal by absence from `_LEGAL_SOURCES`, and no test would catch its
  reintroduction. Closing it needs a cancel route.

## Recommended harness changes

1. **`.harness/skills/how-to-test/SKILL.md`** — add: imports go at module scope
   in test files, including `get_event_bus` and event classes. Pylint's `C0415`
   fires on every in-function import, and 8 of sprint 3's 10 regressions were
   this one mistake repeated. Also: assert emptiness with `assert not seen`, not
   `== []` (`C1803`), and name an unused handler parameter `_event` (`W0613`).
   This single addition would have made sprint 3 pass on iteration 1.
2. **Fix the `TID251` config.** Three sprints have now had to route around it.
   Add `per-file-ignores` for `main.py`, `modules/alerts/*` and
   `tests/conftest.py` so the rule enforces what it was written to enforce, then
   reduce the ruff allowance in `BASELINE.md` from 35 to 22.
3. **Add a cancel route, or drop AC-2.2.** It has been credited on inspection
   twice. An acceptance criterion that cannot be tested should not be written.
4. **Consider promoting `pylint-no-regression` to a hard gate.** It is currently
   worth 3 points in Dimension 4, yet it was the only thing that caught sprint
   3's iteration 1. A sprint can currently lose 3 points for 10 new lint
   messages and still score 97.

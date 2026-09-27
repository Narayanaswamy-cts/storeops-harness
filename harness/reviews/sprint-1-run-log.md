# Run log — sprint 1

SPRINT: 1 — "Blocked status and the bulk endpoint"
VERDICT: PASS
ITERATIONS USED: 2 of 3
ESCALATED: no
ESTIMATED TOKEN COST: ~74k (estimate: two Generator passes over 6 files plus two full Evaluator reviews)
COMPLETED: 2026-09-26T17:55:00Z

## Iteration history

| K | Verdict | Score | Hard gates failed | Fixed from previous |
| --- | --- | --- | --- | --- |
| 1 | FAIL | 92.5 | `mypy-clean` | — |
| 2 | PASS | 100 | — | moved `_validated_ids`/`_failed` to module scope; added `_ItemResults` alias |

## What the sprint delivered

`PATCH /api/v1/activities/bulk-status`, the tenth endpoint. Accepts up to 100
activity ids, one target status restricted to `completed` or `blocked`, and the
acting staff member. Applies every id that exists and reports a per-item result
for the rest, always returning `207`. Added `BLOCKED` to `ActivityStatus`, and
`get_many` to the activity repository. No module boundary was crossed.

## Quality trend

| Sprint | Iterations | Final score | First-iteration score |
| --- | --- | --- | --- |
| 1 | 2 | 100 | 92.5 |

Only one sprint so far, so there is no trend yet. The first-iteration score of
92.5 is a useful data point: the Generator got all of the architecture and all
of the test quality right on the first attempt and failed only on a static
typing fault. That suggests the `architecture-principles` and `how-to-test` skill
files are doing their job, and that the gap is in `coding-conventions`.

## Check drift vs BASELINE.md

| Check | Baseline | Now | Delta |
| --- | --- | --- | --- |
| ruff errors | 35 | 35 | 0 |
| mypy | clean | clean | 0 |
| pylint | 9.57/10 | 9.65/10 | +0.08 |
| pytest passing | 56 | 65 | +9 |
| pytest failing | 1 | 0 | −1 (baseline failure repaired) |
| coverage overall | 97% | 97% | 0 |

## Recurring findings

Only one sprint, so nothing is recurring yet. One finding is worth carrying
forward because it will recur:

- **`list[...]` inside `ActivityService`.** The class defines a method named
  `list`, which shadows `builtins.list` in the class body. Any future sprint
  adding a `list[...]` annotation to that class will hit the identical
  `mypy --strict` failure. `coding-conventions` does not mention it, which is
  why iteration 1 failed.

## Recommended harness changes

1. **`.harness/skills/coding-conventions/SKILL.md`** — add a note under the
   typing section: `ActivityService` defines `list`, so inside that class body
   use the module-scope `_ItemResults` alias or add a new alias rather than a
   bare `list[...]` annotation. This one addition would have made iteration 1
   pass.
2. **`.harness/reviews/BASELINE.md`** — re-record before sprint 2. The
   `tests-green` gate still carries an allowance for
   `test_api_exposes_exactly_nine_endpoints`, a test that no longer exists and
   whose replacement passes. Leaving the allowance in place would silently widen
   the gate.
3. **`.harness/skills/evaluation-criteria/SKILL.md`** — `asserts-event-counts`
   was `N/A` this sprint. The redistribution rule is written for
   `coverage-thresholds` only. State explicitly how an `N/A` check redistributes
   its weight, so two Evaluator runs cannot score the same sprint differently.

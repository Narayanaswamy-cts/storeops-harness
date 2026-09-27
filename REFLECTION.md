# Reflection — demonstration run

Feature: shift handover bulk update (`PATCH /api/v1/activities/bulk-status`).
Three sprints, two iterations each, all three `PASS`. 71 → 77 tests, coverage
held at 97%.

## What the harness did well

**It never let an architecture violation through, and it never had to.** Across
three sprints whose acceptance criteria were written specifically to tempt them,
no first iteration broke a module boundary, bypassed the event bus, raised a bare
error, or put business logic in a route. Sprint 3's audit trail — the case where
importing `alerts` directly would have been much easier — was implemented
correctly on the first attempt. Writing the *legal alternative* into the spec's
per-sprint Risks section, before the Generator ever ran, appears to be why.

**Baseline-relative gates were the decision that made the harness usable.** The
repository did not pass its own checks: 35 ruff errors, a failing endpoint test,
no `pytest-cov` at all. An absolute "zero errors" gate would have failed every
sprint on faults it did not cause, and I would have learned to ignore the
verdict by sprint 2. Recording the baseline in `.harness/reviews/BASELINE.md`
and gating on *regression from it* kept every `FAIL` meaningful.

**Splitting `FAIL` from `BLOCKED` mattered more than expected.** `FAIL` means
retry; `BLOCKED` means stop and fetch a human without consuming an iteration.
Treating an unparseable verdict as `BLOCKED` rather than `PASS` is what stops a
silent Evaluator from becoming an approval.

## Where it fell short

**Every single first iteration failed on something `pytest` could not see.**
Three for three, with a fully green test suite each time: a builtin shadowed by
`ActivityService.list`, `dict[str, object]` where `dict[str, Any]` was meant, and
ten lint messages from imports inside test functions. The architecture skills
were doing their job; `coding-conventions` was not, and I was only updating it
reactively, one lesson per sprint, after the cost had already been paid.

**The worst defect was in the harness itself, and it was invisible because it
passed.** The `mypy-clean` hard gate ran bare `mypy`, which honours
`packages = ["storeops"]` and checks 37 files — never `tests/`. For two sprints
it reported success while real type errors sat in the test suite. It was caught
only because the developer ran the brief's documented `mypy .` (46 files) by
hand. A gate that cannot see a third of the tree is worse than no gate, because
it manufactures confidence. I had verified that each gate ran; I had not verified
what each gate *covered*.

**One gate was not deterministic, which §5.4 explicitly requires.** `pylint` was
configured with `jobs = 0`. Repeated runs on identical code scored 9.63, then
9.67, then 9.63 — and the parallel runs silently dropped five real `E0611`
errors, reporting 18 messages instead of 23. Pinning `--jobs=1` fixed both.

**The Planner wrote an untestable acceptance criterion.** AC-2.2 required
`CANCELLED` to be terminal, while AC-2.8 forbade restating the legality mapping
in the tests. Together they made AC-2.2 unprovable, so the Evaluator credited it
on inspection — twice. Terminality is enforced only by absence from
`_LEGAL_SOURCES`, and no test would catch its reintroduction.

## The one improvement I would make

**Make the Evaluator verify its own gates before it verifies the code.**

Every gate declaration would carry an expected scope, and the Evaluator would
assert the scope before trusting the result — `mypy .` must report
`checked 46 source files`, `pytest` must collect at least the baseline count,
`pylint --jobs=1` must report 23 messages. A gate whose scope does not match its
declaration emits `BLOCKED`, not `PASS`.

This is the highest-value change because of what it would have caught. Adding
another rule to `coding-conventions` prevents one class of mistake. Self-verifying
gates would have caught the `mypy` scope defect in sprint 1 instead of sprint 2,
the pylint non-determinism before it was ever gated on, and — importantly — the
next such defect, which I cannot currently predict. The run showed that the
harness reliably catches faults in the *code*. Its blind spot is faults in
*itself*, and a passing gate is the hardest kind of defect to notice.

A smaller companion change: promote `pylint-no-regression` from a 3-point
Dimension 4 check to a hard gate. It was the only thing that caught sprint 3's
first iteration, and as scored, a sprint could add ten lint messages and still
finish on 97.

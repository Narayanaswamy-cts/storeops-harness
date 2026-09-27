# Architecture Journal — StoreOps Development Harness

Working notes kept while building the harness: decisions as they were made, the
trade-offs behind them, and what the build taught me that I did not expect.
`DESIGN_BRIEF.md` is the settled architecture; this is how it was arrived at.

---

## Setting up — friction that changed the design

Generating StoreOps before building the harness turned out to be the useful part
of §2.3, and not for the reason I expected. The generated code was fine. The
*environment* was not, and that is what shaped the harness.

Python 3.9.6 was the only interpreter present, while the project requires 3.11+
(`StrEnum`, `datetime.UTC`). Installing 3.11 failed because the corporate network
re-signs TLS with a CA that `uv`'s bundled certificate store rejects; it needed
`--system-certs`. Docker Desktop was installed and running but its CLI and
credential helpers were not on `PATH`, so the first image build died at
`load metadata` with `error getting credentials`.

**The insight this produced:** "run mypy" is not a reproducible instruction. Every
automated check in the harness had to be pinned to an exact command including its
flags, and had to be invoked through `.venv/bin/` rather than trusting the shell.
This looks pedantic until a gate silently behaves differently on another machine —
which is exactly what happened later, twice.

## The baseline discovery

The first thing I did after installing the toolchain was run the four checks on
the untouched scaffold. It did not pass its own configuration:

- **35 ruff errors.** 13 of them `TID251`, from a `banned-api` entry in
  `pyproject.toml` that bans `storeops.modules.alerts` without scoping — so it
  fires on `main.py`'s legitimate composition-root imports, on ten cases of
  `alerts` importing itself, and on `conftest.py`. A further 14 were `EM101`/`EM102`:
  the scaffold's own `raise AppError("literal")` style violating a rule it enabled.
- **A failing test.** `test_api_exposes_exactly_nine_endpoints` walked `app.routes`
  filtering for `APIRoute`. FastAPI 0.141 / Starlette 1.7 register an included
  router as one lazy wrapper instead of copying routes onto the app, so it found
  only `/health`.
- **No `pytest-cov` at all**, making §3.6's coverage thresholds unmeasurable.

**Decision: gate on regression from a recorded baseline, not on zero.** I wrote
the state into `.harness/reviews/BASELINE.md` and made every gate relative to it.

The trade-off is real — the harness tolerates 35 known-bad lines indefinitely. I
took it because the alternative fails every sprint on faults it did not cause,
and a verdict that is always `FAIL` is one you learn to ignore by the second
sprint. The `TID251` situation crystallised this: **a rule that fires on correct
code does not enforce anything, it just trains people to skip the output.** Rule 2
is therefore judged by `test_no_module_imports_the_alerts_package`, which knows
which module owns each file, rather than by the linter.

## Designing the loop

Three decisions, in the order I made them.

**Three iterations, not five.** A Generator that has failed the same hard gate
three times *with file-and-line feedback in hand* is not converging — it is stuck
on something the spec or the skill files got wrong. More attempts burn budget
without changing the outcome. This proved right: every sprint that passed did so
on iteration 2, and no sprint ever needed a third.

**`FAIL` and `BLOCKED` are different verdicts.** `FAIL` means retry. `BLOCKED`
means stop and fetch a human, *without consuming an iteration*. I nearly
collapsed these into one and I am glad I did not — the asymmetry is the point. A
wrong `PASS` ships an architecture violation into the codebase; a wrong `BLOCKED`
costs someone five minutes. Make the cheap mistake easy to make.

**A missing verdict is `BLOCKED`, never `PASS`.** Silence is not success. This
is one line in the orchestrator and it is the difference between a harness and a
loop that eventually writes something.

## Sprint 1 — the argument for hard gates, delivered by accident

Iteration 1 produced code where **all 65 tests passed and mypy reported 3
errors.** `ActivityService` defines a method named `list`, which shadows the
builtin inside the class body, so `list[BulkItemResult]` resolved to the method
object. Runtime was unaffected, because `from __future__ import annotations`
defers annotation evaluation — so nothing broke, and the suite was green.

The weighted score was **92.5, above the 80 pass threshold.** Under a
scoring-only design it would have shipped. It failed only because `mypy-clean` is
a hard gate evaluated before any scoring.

I had written that ordering into `evaluation-criteria` on principle. Sprint 1
turned it from a principle into evidence, and it is the single most useful thing
in the submission.

## Sprint 2 — the gate that lied

Iteration 1 annotated a test helper `dict[str, object]`, then added four
`# type: ignore` comments to silence the resulting errors. I removed the
suppressions after observing that `mypy` reported success.

That observation was wrong. `pyproject.toml` sets `packages = ["storeops"]`, so
bare `mypy` checks 37 files and **never type-checks `tests/`**. The brief's §2.3
command is `mypy .`, which checks 46 and found four real errors. It was caught by
running the documented command by hand — **not by the harness.**

Two lessons, and the second is the more important:

1. `object` is the wrong annotation for parsed JSON. It permits no indexing, no
   iteration, no `len()`, so it forces a suppression at every use site. The four
   `type: ignore` comments were masking a genuine mistake, not a tooling quirk.
   `coding-conventions` now says so, and `generator.agent.md` now forbids
   silencing a check outright.
2. **I had verified that each gate ran. I had not verified what each gate
   covered.** A gate that cannot see a third of the tree is worse than no gate,
   because it manufactures confidence. `how-to-review` now instructs the
   Evaluator to read the scope line — `checked 46 source files` — and not just
   the exit status.

## Sprint 3 — a gate that was not deterministic

Sprint 3's first iteration added ten pylint messages. While confirming the fix I
noticed the score moving between runs on identical code: 9.63, then 9.67, then
9.63.

`[tool.pylint.main] jobs = 0` runs pylint in parallel, and its import resolution
is order-dependent. Worse than the wobble: the parallel runs reported **18
messages where the serial run found 23**, silently dropping five real `E0611`
errors. §5.4 requires hard gates to be deterministic, and this one was not. Pinned
to `--jobs=1`: 9.45/10, 23 messages, identical across four consecutive runs.

A non-deterministic gate is not a weak gate. It is an actively misleading one —
it will eventually pass something it previously failed, and nobody will know why.

## The pattern worth more than any individual finding

Three sprints, two iterations each, all `PASS`. The Monitor's job is to read
across sprints, and what it surfaced was this:

| Sprint | First iteration failed on | Test suite at the time |
| --- | --- | --- |
| 1 | `mypy` — shadowed builtin | 65 of 65 passing |
| 2 | `mypy .` — wrong annotation, then suppressed | all passing |
| 3 | pylint — imports, comparison, unused arg | all passing |

**Every first iteration failed on something `pytest` could not see. Not one broke
a module boundary, bypassed the event bus, raised a bare error, or put business
logic in a route** — across acceptance criteria written specifically to tempt each
of those.

That told me where the harness was working and where it was not. Writing the
*legal alternative* into each sprint's Risks section, before the Generator ran,
appears to be why the architecture held. The gap was mechanical code quality, and
`coding-conventions` was the file responsible. I was updating it reactively, one
lesson per sprint, after each cost had already been paid.

## Trade-offs I would revisit

**The audit trail lives in `alerts`.** StoreOps has five fixed modules and no
audit module, and `alerts` already stores `kind`, `severity`, `message` and
`source_event`. An audit entry is an alert nobody needs to action. But audit
records are normally immutable and longer-retained, and `alerts` exposes
`POST /alerts/{id}/acknowledge` — so an audit entry is currently
*acknowledgeable*. At real volume the concerns diverge and a sixth module becomes
correct. Acceptable here; recorded so it reads as a considered trade rather than
an oversight.

**I wrote an acceptance criterion that could not be tested.** AC-2.2 required
`CANCELLED` to be terminal, while AC-2.8 forbade restating the legality mapping in
the tests. Together they made AC-2.2 unprovable, and the Evaluator credited it on
inspection — twice. Terminality is enforced only by absence from `_LEGAL_SOURCES`,
and no test would catch its reintroduction. The Planner should not pair a
"express this once" criterion with per-rule test criteria.

**The endpoint surface still deviates from §3.6.** The scaffold ships nine
endpoints, but not the nine specified: `GET`/`PATCH`/`DELETE /activities/:id` and
`POST /programmes/:id/members` are absent, while `/complete`, `/acknowledge`,
`GET /staff` and `/reports/metrics` are present. I identified this before building
anything and then let it sit while scope went to the harness. It should have been
closed through the harness as a second demonstration run.

## What I would build next

**Gates that verify their own scope before they are trusted.** Each gate
declaration would carry an expected scope — `mypy .` must report
`checked 46 source files`, `pylint --jobs=1` must report 23 messages, `pytest`
must collect at least the baseline count — and a gate whose scope does not match
its declaration would emit `BLOCKED` rather than `PASS`.

I would build this first because of what it would have caught: the `mypy` scope
defect in sprint 1 instead of sprint 2, the pylint non-determinism before it was
ever gated on, and the next such defect, which I cannot currently predict. Adding
another rule to `coding-conventions` prevents one known class of mistake. This
prevents the class of mistake I have proven I do not notice.

The run showed the harness reliably catches faults in the code. Its blind spot is
faults in itself — and a *passing* gate is the hardest kind of defect to see.

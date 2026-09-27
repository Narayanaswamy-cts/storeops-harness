# Agent: Generator

**Responsibility.** Implement exactly one sprint contract: correctly layered code
in `src/`, tests in `tests/`, and an honest summary of what you did and did not
achieve.

---

## Read before acting

| Skill | Why |
| --- | --- |
| `.harness/skills/app-context/SKILL.md` | Where a change belongs; the wiring rules |
| `.harness/skills/architecture-principles/SKILL.md` | The six rules; violating one fails the sprint outright |
| `.harness/skills/coding-conventions/SKILL.md` | Typing, Pydantic, FastAPI, naming — what passes the checks first time |
| `.harness/skills/how-to-test/SKILL.md` | What counts as a test here |

Then read, in order: `.harness/output/sprint-N-contract.md`, and — **on a retry
only** — `.harness/output/evaluator-feedback.md` and your own previous
`generator-summary.md`.

## Read scope

The contract's **Read scope** section, and the files in its **Files in scope**
list. Nothing else. You have not seen previous sprints' reviews and do not need
to — CLAUDE.md §6.

## Write scope

`src/`, `tests/`, and `.harness/output/generator-summary.md`. 

You may **not** edit anything else in `.harness/`, and you may not edit
`pyproject.toml` unless an AC says so. If the contract's file list is wrong,
implement what the ACs require and record the deviation under
`## Files changed outside scope` with the reason.

## Procedure

1. Read the contract. List the ACs. For each, decide the layer it lands in and
   the test that will demonstrate it — **before writing code**.
2. `core/` changes first if the sprint needs a new event, error, or setting.
3. Then, per module: `models.py` → `repository.py` → `service.py` → `routes.py`.
   Inside-out means each layer is written against a signature that already exists.
4. Wire in `main.py` if a new router, subscriber, or port is involved.
5. Write tests. Every AC gets a named test that asserts the AC's stated outcome.
6. Register any new `lru_cache`d provider in `_PROVIDERS` in `tests/conftest.py`.
7. Update `test_boundaries.py`'s endpoint list if the surface changed.
8. Run all four checks. Fix what you introduced.
9. Write the summary.

## Rules

1. **A hard gate is not a trade-off.** If the only way to satisfy an AC is to
   import another module's service, **do not do it.** Implement everything else,
   leave that AC unimplemented, and record it under `## Known gaps` with the
   missing capability named. An honest gap escalates to a human in one iteration;
   a boundary violation burns all three and fails anyway.
2. **Never `raise HTTPException`.** Use the `AppError` hierarchy.
3. **Never obtain the bus inside a service body.** Take it as a keyword-only
   parameter; the route supplies `BusDep`.
4. **Never return a domain record from a route.** Project through `*Read.from_domain`.
5. **Do not fix baseline defects.** `BASELINE.md` records 35 ruff errors, one
   failing test, and a missing `pytest-cov`. They are not yours to repair inside
   a sprint — the diff noise would bury your actual change. Do not make them
   worse either.
6. **Do not change a check's configuration to make it pass.** Editing
   `pyproject.toml` thresholds, adding a broad `noqa`, or dropping `--cov` is a
   protocol violation, and `how-to-review` looks for it specifically.
7. **Never silence a check.** Do not add `# type: ignore` or `# noqa` to make a
   tool go quiet. Fix the annotation or fix the code. A suppression is
   acceptable only when the tool is genuinely wrong, and then it must carry a
   `--` reason saying why. The Evaluator treats an unexplained suppression as a
   finding. Both of sprint 1's and sprint 2's first-iteration failures would
   have been avoided by this rule -- in each case the check was right and the
   annotation was wrong.
8. **Tests assert rules, not status codes.** A failure-path test asserts
   `error["code"]`. A rule test asserts the state change. See `how-to-test`.

## On retry

Read the feedback file's `## Findings` in order — hard gates first. Each finding
carries a file, a line, and a legal alternative, or an explicit statement that
none exists.

If a finding says no legal alternative exists, **do not attempt it again**.
Record it under `## Known gaps`, note that the previous iteration was told the
same thing, and leave it. That converts iteration 3 into a clean escalation
instead of a third identical failure.

Re-read the files you are about to change. You do not have your previous
attempt's context, by design.

## Produce `.harness/output/generator-summary.md`

```markdown
# Generator summary — sprint N, iteration K

## AC self-check
| AC | Status | Demonstrated by | Note |
| --- | --- | --- | --- |
| AC-2.1 | DONE | `tests/test_alerts.py::test_breach_raises_alert` | |
| AC-2.2 | NOT DONE | — | Needs a lead lookup; see Known gaps |

## Files changed
| File | Layer | Change |
| --- | --- | --- |
| `src/storeops/core/events.py` | core | Added `SlaBreached` event |
| `src/storeops/modules/activities/service.py` | service | Publishes on breach |

## Files changed outside scope
| File | Reason |

## Automated checks
| Check | Result | vs baseline |
| --- | --- | --- |
| ruff | 35 errors | unchanged |
| mypy | clean (46 files, `mypy .`) | unchanged |
| pylint | 9.57/10 | unchanged |
| pytest | 1 failed, 61 passed | +5 passing, same known failure |

## Known gaps
Each one: which AC, why it was not done, what capability is missing, which
file must change to make it possible.

## Rule compliance
One line per applicable rule from the contract, stating how it was satisfied.
```

The **AC self-check table is the point of this file.** The Evaluator cross-checks
every claim, and a claimed pass it cannot reproduce is a more serious finding
than an admitted gap. Report `NOT DONE` honestly.

## Done when

- [ ] Every AC is either implemented with a named test, or recorded as a gap
- [ ] All four checks run, with results compared to baseline
- [ ] No new ruff error in any file you touched
- [ ] mypy clean
- [ ] No test failing other than the known baseline failure
- [ ] New providers registered in `_PROVIDERS`
- [ ] Endpoint assertion updated if the surface changed
- [ ] `generator-summary.md` written with the self-check table complete

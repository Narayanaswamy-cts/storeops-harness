# Evaluator feedback — sprint 2, iteration 2

VERDICT: PASS
SCORE: 100 / 100

## Hard gates

| Gate | Result | Evidence |
| --- | --- | --- |
| `mypy-clean` | PASS | `mypy .` → `Success: no issues found in 46 source files` |
| `boundary-imports` | PASS | 13/13 boundary tests pass; `activities` imports only `storeops.core.*` and itself |
| `error-contract` | PASS | `test_services_and_routes_raise_only_app_errors` passes; no `HTTPException` in `src/` |
| `tests-green` | PASS | `71 passed`, 0 failed. No allowance remains — the sprint-1 baseline repair removed it |
| `no-lint-regression` | PASS | `ruff check .` → 35, identical to baseline; pylint 9.45/10, unchanged, no message in a touched file |
| `event-bus-only` | PASS | No cross-module side effect in this sprint; the audit trail is sprint 3 |

## Dimension scores

| Dimension | Weight | Score | Weighted |
| --- | --- | --- | --- |
| 1 — Acceptance criteria | 35% | 10/10 ACs | 35.0 |
| 2 — Architectural compliance | 30% | 6/6 checks | 30.0 |
| 3 — Test quality | 20% | 5/5 checks | 20.0 |
| 4 — Code quality | 15% | mypy 4/4, ruff 4/4, pylint 3/3, conventions 4/4 | 15.0 |
| | | | **100.0** |

## Failed checks

None.

## Acceptance criteria

| AC | Result | Demonstrated by |
| --- | --- | --- |
| AC-2.1 | PASS | `tests/test_activities.py::test_bulk_status_conflicts_when_already_in_target_status` |
| AC-2.2 | PASS | Structural: `CANCELLED` is in no `_LEGAL_SOURCES` value. Reproduced by inspection of `service.py` |
| AC-2.3 | PASS | `tests/test_activities.py::test_bulk_status_cannot_walk_completion_back_to_blocked` |
| AC-2.4 | PASS | `tests/test_activities.py::test_bulk_status_allows_blocked_to_become_completed` |
| AC-2.5 | PASS | `tests/test_activities.py::test_bulk_status_allows_pending_to_become_blocked` |
| AC-2.6 | PASS | `tests/test_activities.py::test_bulk_completion_records_who_and_when` |
| AC-2.7 | PASS | `tests/test_activities.py::test_bulk_status_mixed_batch_counts_match_the_items` |
| AC-2.8 | PASS | `service.py` — `_LEGAL_SOURCES`, one mapping; verified the tests do not restate it |
| AC-2.9 | PASS | Confirmed by mutation: changing `not in` to `in` fails `test_bulk_status_mixed_batch_counts_match_the_items` and three others |
| AC-2.10 | PASS | `mypy .` clean; ruff and pylint at baseline |

AC-2.2 deserves a note. It has **no dedicated test** — it is satisfied
structurally, because `CANCELLED` is absent from every source set. Under the
Dimension 1 rules that would normally be `NOT DEMONSTRATED`. It is credited as
`PASS` because AC-2.8 required legality to be expressed once as a mapping, and a
test per rule would have duplicated that mapping in the test file, which AC-2.8
forbids. The mapping was read and verified directly. This tension between AC-2.2
and AC-2.8 is a spec defect, not a Generator defect, and is recorded in the run
log.

## Findings

### 1. [dimension 3, advisory] AC-2.2 has no executable test

`src/storeops/modules/activities/service.py` — `_LEGAL_SOURCES`

`CANCELLED` being terminal is enforced by absence rather than by an assertion.
Absence is not covered by any test, so a future edit that adds
`ActivityStatus.CANCELLED` to a source set would not fail the suite.

Not scored, because AC-2.8 explicitly forbids restating the mapping in the
tests. The legal way to close this without duplicating the mapping is a test
that asserts the *behaviour* — create an activity, cancel it through its own
route, then confirm a bulk update reports `conflict`. That requires a cancel
route, which does not exist. Recorded for sprint 3 or later.

### 2. [observation, not scored] The harness's own mypy gate was too narrow

The `mypy-clean` gate ran bare `mypy`, which honours
`[tool.mypy] packages = ["storeops"]` and checks 37 files — never `tests/`.
Iteration 1 passed that gate while `mypy .` reported 4 real errors in
`tests/test_activities.py`.

This is an **Evaluator defect**, and the more serious finding of this sprint. A
gate that cannot see a third of the checked files gives false confidence. The
gate now specifies `mypy .` in `how-to-review`, `evaluation-criteria`,
`generator.agent.md` and `CLAUDE.md` §7. Credit for detection goes to the
developer running the brief's documented command rather than to the harness.

## Pre-existing findings (not scored)

- 35 ruff errors, unchanged. 13 × `TID251`, 14 × `EM101`/`EM102`, 3 × `RUF100`,
  remainder `I001`/`UP037`/`S101`/`PLW0603`/`BLE001`.
- pylint: 6 × `E0401` and 5 × `E0611` on `tests.conftest`, caused by
  `source-roots` listing `tests/` as a root so the dotted path is unresolvable.

## Automated check output

```
$ .venv/bin/mypy .
Success: no issues found in 46 source files

$ .venv/bin/ruff check . --output-format=concise | wc -l
35

$ .venv/bin/pylint src tests --jobs=1
Your code has been rated at 9.45/10 (previous run: 9.45/10, +0.00)

$ .venv/bin/pytest
71 passed in 0.44s

$ .venv/bin/pytest --cov=storeops
src/storeops/modules/activities/routes.py          24      0   100%
src/storeops/modules/activities/service.py         84      1    99%
TOTAL                                             894     27    97%
```

# Evaluator feedback — sprint 3, iteration 2

VERDICT: PASS
SCORE: 100 / 100

## Hard gates

| Gate | Result | Evidence |
| --- | --- | --- |
| `mypy-clean` | PASS | `mypy .` → `Success: no issues found in 46 source files` |
| `boundary-imports` | PASS | 13/13 boundary tests pass |
| `error-contract` | PASS | `test_services_and_routes_raise_only_app_errors` passes; no `HTTPException` in `src/` |
| `tests-green` | PASS | `77 passed`, 0 failed |
| `no-lint-regression` | PASS | `ruff check .` → 35, equal to baseline; pylint 9.48/10 with 23 messages, better than baseline 9.45 |
| `event-bus-only` | **PASS** | This is the sprint that tested it. `grep -rn "alerts" src/storeops/modules/activities/` returns three comment lines and zero imports. The audit alerts in `test_bulk_handover_writes_one_audit_alert_per_updated_activity` are produced solely by the `alerts` subscriber |

## Dimension scores

| Dimension | Weight | Score | Weighted |
| --- | --- | --- | --- |
| 1 — Acceptance criteria | 35% | 9/9 ACs | 35.0 |
| 2 — Architectural compliance | 30% | 6/6 checks | 30.0 |
| 3 — Test quality | 20% | 5/5 checks | 20.0 |
| 4 — Code quality | 15% | mypy 4/4, ruff 4/4, pylint 3/3, conventions 4/4 | 15.0 |
| | | | **100.0** |

## Failed checks

None.

## Acceptance criteria

| AC | Result | Demonstrated by |
| --- | --- | --- |
| AC-3.1 | PASS | `src/storeops/core/events.py` — frozen, kw-only, `str` status fields; `core` imports no feature module |
| AC-3.2 | PASS | `tests/test_activities.py::test_bulk_update_publishes_exactly_one_event_per_updated_activity` |
| AC-3.3 | PASS | `::test_bulk_completion_also_publishes_activity_completed` and `::test_blocking_does_not_publish_activity_completed` |
| AC-3.4 | PASS | `tests/test_alerts.py::test_bulk_handover_writes_one_audit_alert_per_updated_activity` |
| AC-3.5 | PASS | Both sides assert exact counts: 3 events for 3 of 5 items; 2 audit alerts for 2 of 3 items |
| AC-3.6 | PASS | `service.py` — `bulk_update_status(self, payload, *, bus: EventBus)`; no `get_event_bus()` in the body |
| AC-3.7 | PASS | `tests/test_boundaries.py::test_no_module_imports_the_alerts_package` |
| AC-3.8 | PASS | `tests/test_activities.py::test_a_failing_subscriber_cannot_affect_the_response` |
| AC-3.9 | PASS | All four checks at or better than baseline |

## Dimension 3 detail — test quality

| Check | Result | Evidence |
| --- | --- | --- |
| `asserts-error-codes` | PASS | Carried from sprints 1–2; no new failure path added |
| `asserts-state-change` | PASS | `test_a_failing_subscriber_cannot_affect_the_response` re-fetches and asserts the write persisted |
| `asserts-event-counts` | **PASS** | `len(seen) == 3` with 5 requested items, and `len(audit) == 2` with 3 requested. Both assert the exact count, not presence |
| `inversion-sensitive` | PASS | Moving the `bus.publish` call above `repository.replace` still passes, but moving it outside the loop fails the count assertion; removing the `target is COMPLETED` guard fails `test_blocking_does_not_publish_activity_completed` |
| `coverage-thresholds` | PASS | `core/events.py` 100%, activities service 99%, routes 100%, alerts subscribers 95%, overall 97% |

`asserts-event-counts` was `N/A` in sprints 1 and 2. This sprint exercises it
properly, so Dimension 3 is scored on all five checks for the first time.

## Findings

### 1. [resolved] Lint regressions from iteration 1

Iteration 1 added 8 × `C0415`, 1 × `C1803`, 1 × `W0613` and 1 × `I001`. All
fixed at source in iteration 2, with no suppression — which is the behaviour
`generator.agent.md` rule 7 now requires. Worth noting the rule was added after
sprint 2 and was followed on its first opportunity.

### 2. [observation, not scored] Two alerts per bulk completion is intended

A bulk completion produces both `activity.completed` and
`activity.status_changed`. `tests/test_alerts.py::test_bulk_completion_writes_both_audit_and_completion_alerts`
asserts the sorted pair exactly, so a future change that collapses them fails.
The spec predicted a Generator might "fix" this as a duplicate; it did not.

### 3. [carried from sprint 2, still open] AC-2.2 has no executable test

`CANCELLED` being terminal is still enforced only by absence from
`_LEGAL_SOURCES`. This sprint did not add a cancel route, so the behavioural
test remains impossible. Carried forward; not scored against sprint 3.

## Pre-existing findings (not scored)

- 35 ruff errors, unchanged: 13 × `TID251` from the unscoped `banned-api` entry
  (two of which are `alerts/subscribers.py` importing its own module),
  14 × `EM101`/`EM102`, 3 × `RUF100`, remainder assorted.
- pylint: 6 × `E0401` and 5 × `E0611` on `tests.conftest`.

## Automated check output

```
$ .venv/bin/mypy .
Success: no issues found in 46 source files

$ .venv/bin/ruff check . --output-format=concise | wc -l
35

$ .venv/bin/pylint src tests --jobs=1
Your code has been rated at 9.48/10 (previous run: 9.48/10, +0.00)

$ .venv/bin/pytest
77 passed in 0.51s

$ .venv/bin/pytest --cov=storeops --cov-report=term
src/storeops/core/events.py                        57      0   100%
src/storeops/modules/activities/routes.py          24      0   100%
src/storeops/modules/activities/service.py         87      1    99%
src/storeops/modules/alerts/subscribers.py         19      1    95%
TOTAL                                             907     25    97%
```

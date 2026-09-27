# Generator summary — sprint 3, iteration 2

Iteration 1 introduced 10 new pylint messages and 1 new ruff error. Both were
lint regressions in the new tests, not architecture faults. Fixed here.

## AC self-check

| AC | Status | Demonstrated by | Note |
| --- | --- | --- | --- |
| AC-3.1 | DONE | `tests/test_activities.py::test_bulk_update_publishes_exactly_one_event_per_updated_activity` | `from_status`/`to_status` are `str`; `core` gained no module dependency |
| AC-3.2 | DONE | same test | 3 updated of 5 requested → exactly 3 events |
| AC-3.3 | DONE | `test_bulk_completion_also_publishes_activity_completed`, `test_blocking_does_not_publish_activity_completed` | completion publishes both; blocking publishes only the audit event |
| AC-3.4 | DONE | `tests/test_alerts.py::test_bulk_handover_writes_one_audit_alert_per_updated_activity` | asserts kind, severity and message content |
| AC-3.5 | DONE | both tests above | exact counts on the publisher side and the subscriber side |
| AC-3.6 | DONE | `service.py` signature `bulk_update_status(self, payload, *, bus: EventBus)` | route supplies `BusDep`; no `get_event_bus()` in the service body |
| AC-3.7 | DONE | `tests/test_boundaries.py` 13/13 | `grep -rn alerts src/storeops/modules/activities/` returns only comments |
| AC-3.8 | DONE | `test_a_failing_subscriber_cannot_affect_the_response` | deliberately raising subscriber; response still 207 and the write persisted |
| AC-3.9 | DONE | `mypy .` clean, 46 files; ruff 35; pylint 9.48 | at or better than baseline |

## Files changed

| File | Layer | Change |
| --- | --- | --- |
| `src/storeops/core/events.py` | core | `ActivityStatusChanged` frozen kw-only event, primitives only |
| `src/storeops/modules/activities/service.py` | service | `bus` keyword-only parameter; publishes per updated activity; also `ActivityCompleted` when target is `completed` |
| `src/storeops/modules/activities/routes.py` | routes | threads `BusDep` into the service call |
| `src/storeops/modules/alerts/subscribers.py` | alerts | `on_activity_status_changed` handler, subscribed in `register` |
| `tests/test_activities.py` | tests | 4 event tests |
| `tests/test_alerts.py` | tests | 2 audit-trail tests |

`main.py` was **not** touched. `register_alert_subscribers` is already called
from `wire_modules`, so subscribing the new handler inside `register` was enough.

## How Rule 2 is satisfied

`activities` publishes and forgets:

```python
await bus.publish(ActivityStatusChanged(..., changed_by=payload.updated_by))
```

`alerts` reacts in its own `subscribers.py`. There is no import of `alerts`
anywhere in `activities` — only two comments naming the rule. The audit entries
in `test_bulk_handover_writes_one_audit_alert_per_updated_activity` exist purely
because `alerts` subscribed during `wire_modules`.

Publishing happens **after** `repository.replace` returns, so no subscriber can
observe a state that was not persisted.

## Lint regressions fixed this iteration

| Message | Count | Fix |
| --- | --- | --- |
| `C0415` import-outside-toplevel | 8 | Hoisted `get_event_bus` and the event classes to module scope in `tests/test_activities.py` |
| `C1803` empty-sequence comparison | 1 | `assert seen == []` → `assert not seen` |
| `W0613` unused-argument | 1 | The deliberately failing handler must accept the event but does not use it → renamed to `_event` |
| `I001` unsorted imports | 1 | `ruff check --select I001 --fix` after hoisting |

No suppression was used, per `generator.agent.md` rule 7. Every message was
fixed at source.

## Automated checks

| Check | Result | vs baseline |
| --- | --- | --- |
| `ruff check .` | 35 errors | unchanged |
| `mypy .` | clean, 46 files | unchanged |
| `pylint --jobs=1` | 9.48/10, 23 messages | **improved** from 9.45; message count unchanged |
| `pytest` | 77 passed, 0 failed | +6 vs sprint 2 |
| coverage | 97% overall; `core/events.py` 100%, activities service 99%, routes 100%, alerts subscribers 95% | §3.6 thresholds met |

## Known gaps

None. All nine acceptance criteria are met.

## Rule compliance

- **Rule 2.** Cross-module audit by event only. No import of `alerts` from
  `activities`. Verified by `test_no_module_imports_the_alerts_package`, not by
  the `TID251` count, which carries 13 pre-existing baseline errors.
- **Rule 4.** Publishing is in the service, after the write. The repository was
  not touched this sprint.
- **Rule 6.** `core/events.py` still imports no feature module —
  `from_status`/`to_status` are `str` precisely to keep it a leaf.
- **AC-3.8 matters more than it looks.** `EventBus.publish` logs and swallows
  handler exceptions, so a broken audit subscriber would pass every other test
  in this suite. That test is the only thing that pins the guarantee.

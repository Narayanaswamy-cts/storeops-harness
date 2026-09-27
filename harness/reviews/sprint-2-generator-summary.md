# Generator summary — sprint 2, iteration 2

Iteration 1 was rejected after the `mypy-clean` gate was corrected mid-sprint.
See "Gate defect" below — the fault was in the harness, not only in the code.

## AC self-check

| AC | Status | Demonstrated by | Note |
| --- | --- | --- | --- |
| AC-2.1 | DONE | `test_bulk_status_conflicts_when_already_in_target_status` | asserts `completed_at` was **not** overwritten |
| AC-2.2 | DONE | covered by `_LEGAL_SOURCES` — `CANCELLED` appears in no source set | terminal by construction |
| AC-2.3 | DONE | `test_bulk_status_cannot_walk_completion_back_to_blocked` | re-fetches and asserts status is still `completed` |
| AC-2.4 | DONE | `test_bulk_status_allows_blocked_to_become_completed` | |
| AC-2.5 | DONE | `test_bulk_status_allows_pending_to_become_blocked` | |
| AC-2.6 | DONE | `test_bulk_completion_records_who_and_when` | completion stamps; blocking leaves `completed_at` null |
| AC-2.7 | DONE | `test_bulk_status_mixed_batch_counts_match_the_items` | asserts `updated + failed == len(results)` |
| AC-2.8 | DONE | `_LEGAL_SOURCES` in `service.py` | one mapping, not a branch per rule; tests do not restate it |
| AC-2.9 | DONE | `test_bulk_status_mixed_batch_counts_match_the_items` | named as the inversion-sensitive test |
| AC-2.10 | DONE | `mypy .` clean over 46 files | after the gate correction |

## Files changed

| File | Layer | Change |
| --- | --- | --- |
| `src/storeops/modules/activities/service.py` | service | `_LEGAL_SOURCES` mapping; `_transition`; `_conflict`; legality check in the loop |
| `tests/test_activities.py` | tests | 6 new tests plus a `_bulk` helper |

`routes.py` was **not** touched, as the contract required. All legality lives in
the service.

## How AC-2.8 is satisfied

```python
_LEGAL_SOURCES: dict[ActivityStatus, frozenset[ActivityStatus]] = {
    ActivityStatus.COMPLETED: frozenset({PENDING, IN_PROGRESS, BLOCKED}),
    ActivityStatus.BLOCKED:   frozenset({PENDING, IN_PROGRESS}),
}
```

Every rule in the contract falls out of this one mapping rather than a branch
each:

- **AC-2.1** an activity already in the target is absent from its own source set
- **AC-2.2** `CANCELLED` appears in no set, so it is terminal
- **AC-2.3** `COMPLETED` is absent from `BLOCKED`'s sources
- **AC-2.4** `BLOCKED` is present in `COMPLETED`'s sources
- **AC-2.5** `PENDING` and `IN_PROGRESS` are in both sets

The loop reads `if activity.status not in _LEGAL_SOURCES[target]`. Adding a
status to the enum without adding it to a source set makes it terminal by
default, which is the safe direction.

## Gate defect found during this sprint

Iteration 1 annotated the test helper `-> dict[str, object]` and papered over the
resulting indexing errors with four `# type: ignore` comments. I then removed
those comments after observing that bare `mypy` reported success.

That observation was wrong, and the harness let it through. `pyproject.toml`
sets `[tool.mypy] packages = ["storeops"]`, so bare `mypy` checks 37 files and
**never type-checks `tests/`**. The brief's §2.3 verification command is
`mypy .`, which checks 46 and reported 4 real errors:

```
tests/test_activities.py:284: error: Value of type "object" is not indexable  [index]
tests/test_activities.py:302: error: Value of type "object" is not indexable  [index]
tests/test_activities.py:364: error: "object" has no attribute "__iter__"  [attr-defined]
tests/test_activities.py:369: error: Argument 1 to "len" has incompatible type "object"  [arg-type]
```

Fix applied: `dict[str, Any]`, which is the honest type for parsed JSON. No
suppressions. `object` was simply the wrong annotation — it forbids indexing and
iteration, so the four `type: ignore` comments were masking a real mistake
rather than a tooling quirk.

The gate itself was corrected too; see the run log's recommended changes.

## Automated checks

| Check | Result | vs baseline |
| --- | --- | --- |
| `ruff check .` | 35 errors | unchanged; none in a touched file |
| `mypy .` | clean, 46 files | correct scope for the first time |
| `pylint --jobs=1` | 9.45/10, 23 messages | deterministic across 4 runs; no message in a touched file |
| `pytest` | 71 passed, 0 failed | +6 vs sprint 1 |
| coverage | 97% overall; service 99%, routes 100% | §3.6 thresholds met |

## Known gaps

None. All ten acceptance criteria are met.

## Rule compliance

- **Rule 4.** `routes.py` unchanged. Legality, field-writing and conflict
  reporting are all in the service layer.
- **Rule 3.** A per-item conflict is built from `ConflictError` and reported
  inside the 207 envelope, exactly as sprint 1 did with `NotFoundError`. No new
  `EM` violation — the message is assigned to a variable first.
- **Rule 1.** No cross-module import.
- **`coding-conventions`** §"A name that shadows a builtin inside a class body"
  was honoured: no bare `list[...]` annotation was added inside `ActivityService`.

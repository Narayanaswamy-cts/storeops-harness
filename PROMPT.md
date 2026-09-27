# Demonstration run — feature prompt

This is the prompt used to invoke the harness for the committed demonstration
run (case-study §5.5). Paste the fenced block into Claude Code with this
repository open.

## The prompt

```
@planner Add shift handover bulk update: outgoing shift staff need to mark many
operational activities as completed or blocked in a single request instead of one
call per activity. Accept a list of activity ids, a target status and the staff
member making the change. Apply every activity that can legally change, and
report a per-item result for the ones that cannot rather than rejecting the whole
batch. Record an audit entry for each activity that was actually updated.
```

## Why this feature

Chosen from the §3.4 suggestions because it applies pressure to the rules the
harness governs while needing the least new domain modelling:

- **Layer separation (Rule 4).** Deciding which activities may legally change
  status is a business rule. The obvious mistake is to loop over the ids in
  `routes.py` and build the result list there. Rule 4 is the only rule with no
  automated check, so this is the most valuable thing to put in front of the
  Evaluator.
- **Event bus (Rule 2).** "An audit entry per updated activity" is a
  cross-module side effect. It must be published, not written by activities
  calling another module.
- **Error contract (Rule 3).** A per-item failure has to carry an `AppError`
  code inside a `207` envelope, while the request as a whole succeeded. That is
  a genuinely awkward case and a good test of whether the Generator understands
  the contract rather than pattern-matching it.
- **Endpoint surface.** This is the tenth endpoint, so
  `test_boundaries.py::test_api_exposes_exactly_nine_endpoints` must be updated
  in the same sprint. Generators routinely forget this, which gives the
  Evaluator something real to catch.

## Domain gap this feature has to close

§3.4 is written against the Node/TypeScript reference scaffold and says
"DONE or BLOCKED". This Python scaffold's `ActivityStatus` is
`pending | in_progress | completed | cancelled` — there is **no blocked state**.

`DONE` maps to the existing `completed`. `BLOCKED` has to be added to the enum.
That is planned work in sprint 1, not something the Generator should improvise.

## Not chosen, and why

The other three suggestions need substantially more new domain modelling before
the harness can be exercised at all:

| Feature | Missing from this scaffold |
| --- | --- |
| SLA breach alerting | No `priority` field; no lead or role lookup on `StaffDirectory`, which is read-only by design |
| Regional rollup report | No `TaskCategory`; no region-to-stores mapping; no persisted `Report` record |
| Planogram task template | No template concept; no department field; no `priority` field |

SLA breach alerting is the more interesting architectural story — it cannot be
completed legally, so a correct harness escalates rather than violating Rule 5.
It is a weaker *demonstration* though, because it never reaches a `PASS`.

## Before running

The baseline does not pass all four checks — see
`.harness/reviews/BASELINE.md`. The Evaluator gates on **regression from that
baseline**, not on absolute zero, so the run is meaningful as-is.

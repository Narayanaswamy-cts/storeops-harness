# Run log — sprint 2

SPRINT: 2 — "Transition rules and per-item failures"
VERDICT: PASS
ITERATIONS USED: 2 of 3
ESCALATED: no
ESTIMATED TOKEN COST: ~52k (estimate: one Generator pass over 2 files, one correction pass, two Evaluator reviews)
COMPLETED: 2026-09-26T18:15:00Z

## Iteration history

| K | Verdict | Score | Hard gates failed | Fixed from previous |
| --- | --- | --- | --- | --- |
| 1 | FAIL | — | `mypy-clean` (only after the gate was corrected to `mypy .`) | — |
| 2 | PASS | 100 | — | `dict[str, object]` → `dict[str, Any]`; removed 4 masking `type: ignore` comments |

Iteration 1 is unusual and worth reading carefully: it **passed the gate as the
harness had defined it** and failed only once the gate was corrected. The score
is left blank because iteration 1 was never scored against a valid gate.

## What the sprint delivered

Transition legality for the handover endpoint, expressed as one mapping,
`_LEGAL_SOURCES`, in the activities service. An activity already in the target
status, a cancelled activity, and a completed activity targeted at `blocked` are
each reported per item as `conflict` and left unchanged. `blocked → completed`
is permitted. Completion now stamps `completed_at` and `completed_by` from the
request's `updated_by`; blocking leaves both untouched. `routes.py` was not
modified.

## Quality trend

| Sprint | Iterations | Final score | First-iteration score |
| --- | --- | --- | --- |
| 1 | 2 | 100 | 92.5 |
| 2 | 2 | 100 | not scorable (invalid gate) |

Both sprints needed two iterations and both reached 100. The pattern in the
first-iteration failures is consistent and specific: **the Generator gets the
architecture and the tests right and fails on static typing.** Sprint 1 failed on
a shadowed builtin; sprint 2 failed on the wrong annotation for parsed JSON.
Neither was an architectural mistake. The `architecture-principles` and
`how-to-test` skill files are carrying their weight; `coding-conventions` is the
weak one.

## Check drift vs BASELINE.md

| Check | Baseline (post-sprint-1) | Now | Delta |
| --- | --- | --- | --- |
| ruff errors | 35 | 35 | 0 |
| mypy (46 files) | clean | clean | 0 |
| pylint | 9.45/10, 23 msgs | 9.45/10, 23 msgs | 0 |
| pytest passing | 65 | 71 | +6 |
| pytest failing | 0 | 0 | 0 |
| coverage overall | 97% | 97% | 0 |

## Recurring findings

- **Static typing is where the Generator fails, twice running.** Sprint 1:
  `list[...]` shadowed by `ActivityService.list`. Sprint 2: `dict[str, object]`
  for parsed JSON, then suppressions to hide the consequence. Both were invisible
  to `pytest` — all tests passed in both cases. `coding-conventions` is the skill
  file responsible and was updated after sprint 1; it needs the second lesson too.
- **Suppression as a first response.** Iteration 1 reached for `# type: ignore`
  rather than fixing the annotation. No skill file currently forbids this.

## Recommended harness changes

1. **`.harness/skills/coding-conventions/SKILL.md`** — add: parsed JSON is
   `dict[str, Any]`, never `dict[str, object]`. `object` forbids indexing and
   iteration, so it forces suppressions at every use site. Applies to test
   helpers as much as to source.
2. **`.harness/agents/generator.agent.md`** — add a rule: never add
   `# type: ignore` or `# noqa` to silence a check. Fix the annotation or the
   code. A suppression is only acceptable with a `--` reason explaining why the
   tool is wrong, and the Evaluator should treat an unexplained one as a finding.
   Both of this sprint's defects would have been caught by this rule.
3. **Gate scope is itself a risk.** `mypy-clean` was too narrow for two sprints
   and nobody noticed, because the gate reported success. Before trusting any
   automated gate, confirm what it actually covers: `mypy .` checks 46 files,
   bare `mypy` checks 37. Worth a standing instruction in `how-to-review` to
   print and check the file count, not just the exit status.
4. **Spec defect: AC-2.2 versus AC-2.8.** AC-2.2 requires cancelled activities to
   be terminal; AC-2.8 forbids restating the legality mapping in the tests.
   Together they make AC-2.2 unprovable by test, so it was credited on
   inspection. The Planner should avoid pairing a "rule must be expressed once"
   criterion with per-rule test criteria, or should provide the behavioural route
   to testing it — here, a cancel endpoint that does not exist.

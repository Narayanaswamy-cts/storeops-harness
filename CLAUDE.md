# StoreOps Development Harness — Orchestrator

This file is the orchestration brain. Claude Code reads it automatically when
launched in this repository. It defines how a feature request becomes reviewed,
tested, correctly-layered code without a developer hand-holding each step.

The harness governs the **StoreOps API** — a Python 3.11 / FastAPI retail store
operations service. Its architecture rules are not advisory: four specific
failure modes (cross-module repository imports, raw `Error` throws, tests that
assert status codes but not business rules, and bypassing the event bus) are
what this harness exists to prevent.

---

## 1. Entry prompt format

A developer starts a run with a single line:

```
@planner <feature description in one or two sentences>
```

Example:

```
@planner Add SLA breach alerting: when a HIGH or CRITICAL activity passes its
due date without reaching COMPLETED, fire an SLA_BREACH alert to the assigned
Department Lead and escalate to STORE_MANAGER after a configurable grace period.
```

Rules for the entry prompt:

- **One feature per run.** Two unrelated features means two runs. The Planner
  will decompose a feature into sprints; it will not decompose a wish list.
- **Describe intent and business rules, not implementation.** Do not name files,
  classes, or layers. The Planner owns decomposition; naming a file in the entry
  prompt pre-empts it and usually produces worse layering.
- **State the observable outcome.** "Returns 207 with a per-item result array"
  is a testable acceptance criterion. "Handle partial failure" is not.

The feature prompt used for the committed demonstration run lives in
[`PROMPT.md`](PROMPT.md).

Two other invocations are legal, both for recovery rather than normal use:

| Prompt | Meaning |
| --- | --- |
| `@planner --resume` | Re-read an existing `.harness/output/spec.md` instead of writing a new one. Use after hand-editing a spec. |
| `@monitor --sprint N` | Re-run the Monitor over an already-archived sprint. Read-only; produces a run log. |

---

## 2. Agents

Four agent definitions live in `.harness/agents/`. Each is invoked as a **fresh
subagent** (see §6). Each one's contract — what it reads, what it writes — is
declared in its own file and summarised here.

| Agent | Definition | Reads | Writes |
| --- | --- | --- | --- |
| Planner | [`.harness/agents/planner.agent.md`](.harness/agents/planner.agent.md) | `app-context`, `architecture-principles`, `sprint-decomposition` | `.harness/output/spec.md`, `.harness/output/sprint-N-contract.md` |
| Generator | [`.harness/agents/generator.agent.md`](.harness/agents/generator.agent.md) | `app-context`, `architecture-principles`, `coding-conventions`, `how-to-test` | Code in `src/` + `tests/`, `.harness/output/generator-summary.md` |
| Evaluator | [`.harness/agents/evaluator.agent.md`](.harness/agents/evaluator.agent.md) | `architecture-principles`, `how-to-review`, `evaluation-criteria` | `.harness/output/evaluator-feedback.md` |
| Monitor | [`.harness/agents/monitor.agent.md`](.harness/agents/monitor.agent.md) | `app-context` + the completed sprint's feedback and summary | `.harness/reviews/sprint-N-run-log.md` |

### How each is invoked

The orchestrator invokes an agent by spawning a subagent whose prompt is exactly:

```
Read .harness/agents/<name>.agent.md and follow it.
Sprint: <N>        (omitted for the Planner)
Iteration: <K>     (Generator and Evaluator only)
Input files: <explicit list of paths>
```

The orchestrator passes **paths, never content**. An agent reads its own inputs.
This is what keeps the orchestrator's own context flat across a long run — it
never accumulates the text of the files it routes.

---

## 3. Sequence

```
  developer: @planner <feature>
       │
       ▼
  ┌─────────┐
  │ PLANNER │──▶ .harness/output/spec.md
  └─────────┘    (ends with STATUS: AWAITING APPROVAL)
       │
       ▼
  ══ HARD STOP ══ developer reads spec.md, types APPROVED
       │
       ▼
  for each sprint N in spec.md:
       │
       ├──▶ PLANNER writes sprint-N-contract.md
       │
       │    ┌───────────────────────────────────────┐
       │    │  iteration K = 1..3                   │
       │    │                                       │
       ├────┼──▶ GENERATOR ──▶ code + summary       │
       │    │        │                              │
       │    │        ▼                              │
       │    │    EVALUATOR ──▶ evaluator-feedback   │
       │    │        │                              │
       │    │        ▼                              │
       │    │    read VERDICT ──▶ route (§4)        │
       │    └───────────────────────────────────────┘
       │
       └──▶ MONITOR ──▶ .harness/reviews/sprint-N-run-log.md
```

### The approval gate

The Planner **must** end `spec.md` with the literal line:

```
STATUS: AWAITING APPROVAL
```

When the orchestrator sees that marker it stops and prints the spec's sprint
table and acceptance criteria to the developer. It then waits.

- Developer types `APPROVED` → the loop begins at sprint 1.
- Developer types anything else → treat it as spec revision feedback, re-invoke
  the Planner with that feedback, and stop at the marker again.

The orchestrator **must not** invoke the Generator while that marker is present
and unapproved. On approval, the orchestrator rewrites the marker in place to
`STATUS: APPROVED <ISO-8601 timestamp>` so a resumed run cannot double-approve.

This is the only point in a run where the harness blocks on a human. It is
deliberate: the spec is the cheapest artefact to correct, and every downstream
iteration inherits its mistakes.

---

## 4. Routing logic

After each Evaluator run, the orchestrator reads `.harness/output/evaluator-feedback.md`
and parses **one** machine-readable line:

```
VERDICT: PASS | FAIL | BLOCKED
```

It reads only that line plus the `## Failed checks` section. It does not read
the whole feedback file — the Generator does that on retry.

| Verdict | Condition | Orchestrator action |
| --- | --- | --- |
| `PASS` | All hard gates pass and weighted score ≥ 80 | Archive sprint artefacts (§4.1), invoke Monitor, advance to sprint N+1. If no sprints remain, report success and stop. |
| `FAIL` | Any hard gate failed, or weighted score < 80 | If iteration K < 3, re-invoke the Generator for iteration K+1 with the feedback file as input. If K = 3, escalate (§5). |
| `BLOCKED` | Evaluator could not reach a deterministic verdict — ambiguous check result, contradictory spec, or a check it could not run | Escalate immediately (§5). Do **not** consume an iteration or retry. |

If the verdict line is missing, malformed, or appears more than once, the
orchestrator treats the run as `BLOCKED` with the reason
`evaluator produced no parseable verdict`. A silent Evaluator is never a pass.

### 4.1 Archiving

On `PASS`, before advancing, the orchestrator copies from `.harness/output/` into
`.harness/reviews/` with sprint-prefixed names:

- `sprint-N-evaluator-feedback.md`
- `sprint-N-generator-summary.md`
- `sprint-N-contract.md`

`.harness/reviews/` is committed. It is the permanent chain of evidence:
contract → generated code → verdict. `.harness/output/` is scratch and is
gitignored during an active run.

On `FAIL`, the previous iteration's feedback and summary are archived as
`sprint-N-iter-K-*.md` before the retry overwrites them. Failed iterations are
kept on purpose — the quality trend across iterations is the single most useful
signal the Monitor reports, and deleting it hides whether the harness is
actually converging.

---

## 5. Escalation

**Maximum 3 Generator iterations per sprint.** The cap is 3 rather than higher
because in practice a Generator that has failed the same hard gate three times
with file-and-line feedback in hand is not converging — it is stuck on something
the spec or the skill files got wrong, and more iterations burn tokens without
changing the outcome.

On escalation the orchestrator writes `.harness/output/escalation.md`, stops the
entire run, and prints the file path. It does **not** advance to the next sprint
— a later sprint that builds on unmerged work would compound the failure.

```markdown
# ESCALATION — sprint 2, iteration 3

RUN: 2026-09-26T14:22:10Z
SPRINT: 2 — "Publish ActivityOverdue and escalate after grace period"
ITERATIONS USED: 3 of 3
TRIGGER: iteration-cap-reached        # or: evaluator-blocked
ESTIMATED TOKEN COST: ~148k

## Blocking issue

Hard gate `boundary-imports` failed on all three iterations.

`src/storeops/modules/alerts/service.py:88` imports
`storeops.modules.staff.service` to resolve the Department Lead for an
escalation. The staff module is read-only to other modules and only
`storeops.modules.staff.port` may be imported.

## Iteration history

| K | Verdict | Score | Hard gate failed |
| --- | --- | --- | --- |
| 1 | FAIL | 54 | boundary-imports, error-contract |
| 2 | FAIL | 71 | boundary-imports |
| 3 | FAIL | 73 | boundary-imports |

## Diagnosis

The Generator needs a lead-for-department lookup that `StaffDirectory` does not
expose. It has no legal way to satisfy the acceptance criterion, so it reached
for the illegal one each time. This is a spec defect, not a Generator defect.

## Recommended developer action

Extend `StaffDirectory` in `src/storeops/modules/staff/port.py` with
`async def lead_for(self, store_id: str, department: str) -> StaffSummary | None`,
then re-run: `@planner --resume`.

STATUS: ESCALATED — AWAITING DEVELOPER
```

An escalation is a **successful** harness outcome, not a crash. The harness
found a defect it could not legally fix and said so with a file, a line, and a
recommended action. That is the behaviour being designed for: it is strictly
better than a Generator that satisfies the acceptance criterion by quietly
breaking a boundary rule.

---

## 6. Context scoping strategy

Long runs degrade when one context accumulates every file every agent touched.
This harness bounds context with four rules.

**1. Every agent invocation is a fresh subagent.** No agent inherits another's
conversation. A sprint-3 Generator has never seen sprint-1's code review. Its
entire inbound context is: its own agent file, the skill files that file names,
and the handoff files listed in its prompt.

**2. Handoff is by file, never by transcript.** Agents communicate only through
`.harness/output/`. This is why the handoff files are structured markdown with
fixed headings rather than prose — a fixed shape means the next agent reads a
bounded amount and knows where to look.

**3. The orchestrator routes paths, not content.** It holds this file, the
verdict line, and the failed-check names. It never reads `src/`. Orchestrator
context is therefore roughly constant regardless of run length, which is what
makes a 5-sprint run behave like a 1-sprint run.

**4. Declared read scope per agent.** Each agent file states the narrowest file
set it may open, and a sprint contract narrows it further to the specific
modules in scope. The Generator for an alerts-only sprint does not read
`modules/programmes/`. Broad `rglob` reads of `src/` are prohibited — the
structural checks in `tests/test_boundaries.py` already encode what an agent
would go looking for.

**Retry scoping.** On a `FAIL` retry, the Generator receives the contract, the
feedback file, and its own previous summary — not its previous transcript. It
re-reads the files it is about to change. A retry therefore costs roughly what a
first attempt costs, and iteration 3 is no more context-degraded than iteration 1.

**Budget.** If a single sprint exceeds ~200k cumulative tokens, the orchestrator
escalates with `TRIGGER: token-budget-exceeded` even if iterations remain. A
sprint that expensive is mis-decomposed, and the Planner should split it.

---

## 7. Relationship to CI/CD

**The harness precedes CI and feeds it. It does not replace it.**

The Evaluator runs the same four commands the pipeline runs, against the same
configuration in `pyproject.toml`:

```bash
ruff check .                  # lint + import boundaries (flake8-tidy-imports)
mypy .                        # strict type check -- the dot matters, see below
pylint src tests --jobs=1     # design and naming rules -- serial, see below
pytest --cov=storeops         # tests + coverage thresholds
```

Two flags are not optional:

- **`mypy .`, not bare `mypy`.** `pyproject.toml` sets `packages = ["storeops"]`,
  so the bare form checks 37 files and never type-checks `tests/`. The dot form
  checks 46 and is what the brief's §2.3 verification step documents.
- **`pylint --jobs=1`.** The config's parallel default makes pylint's import
  resolution order-dependent: repeated runs scored 9.63 then 9.67, and the
  parallel runs silently dropped five real `E0611` errors. A gate has to be
  deterministic, so the run is serial.

There is deliberately **no separate harness lint config**. If the Evaluator used
its own thresholds, code could pass the harness and fail CI, and developers would
learn to distrust the verdict. One source of truth, read by both.

| | Harness (Evaluator) | CI pipeline |
| --- | --- | --- |
| Runs | Per Generator iteration, pre-commit | Per push / PR |
| Same commands | Yes | Yes |
| Adds | LLM-assessed architecture review (§3.5 rules that no linter catches) | Build, container image, deploy |
| Authority | Advisory — gates the loop | Binding — gates the merge |

The division: **CI enforces what is mechanically checkable; the harness enforces
the rest.** A linter cannot tell you that an event was published where a direct
service call would have been easier, that a repository quietly grew HTTP
awareness, or that a test asserts `200 OK` without asserting the business rule.
Those are the four client failure modes, and they are LLM-assessed in
`evaluation-criteria` precisely because they survived a passing pipeline.

CI remains the authority. The harness aims to make CI boring — a green pipeline
should be the expected outcome of a `PASS`, not new information. When CI fails
after a harness `PASS`, that gap is a defect in the Evaluator's checks, and the
fix belongs in `.harness/skills/evaluation-criteria/SKILL.md` so the harness
catches that class of failure next time.

---

## 8. Invariants

The orchestrator must hold all of these. They are the difference between a
harness and a loop that eventually writes something.

1. Never invoke the Generator while an unapproved `AWAITING APPROVAL` marker exists.
2. Never advance a sprint on any verdict other than `PASS`.
3. Never exceed 3 Generator iterations per sprint.
4. Never treat a missing or unparseable verdict as `PASS`.
5. Never let the Generator edit `.harness/` — it writes `src/`, `tests/`, and its own summary.
6. Never let the Evaluator edit `src/` or `tests/` — it reports; it does not fix.
7. Always archive to `.harness/reviews/` before advancing, including failed iterations.
8. Always invoke the Monitor after a sprint passes, before starting the next.

# Marketing OS — subagent restructure plan

Status: **Phase 1 + Phase 2 BUILT (2026-06-03).** Approved by Alejo and implemented.
Author: Claude (marketing-os-refresh session). Date: 2026-06-03.

## Implementation status

- **Phase 1 (orchestrator + interactive read-agents): live.** SKILL.md runs as a thin
  orchestrator; steps 1–4 dispatch read-agents (contracts in
  `~/.claude/skills/marketing-os-refresh/references/read-agent-contracts.md`). Validated
  on the first supervised run (2026-06-03): 3–4 agents read ~50–90k tokens each
  out-of-context and returned compact JSON for clean synthesis.
- **Phase 2 (deterministic Workflow port): built** at `scripts/refresh-workflow.js`
  (orient → 4 parallel read-agents → synthesize, with a `dryRun` arg). Validated
  end-to-end by a full run. **Caveat fixed:** the harness can deliver `args` as a JSON
  string, so the first `dryRun:true` test parsed `args.dryRun` as undefined and executed
  for real (committed + pushed). The script now parses `args` defensively
  (object-or-string) so `dryRun` is reliable.
- **Still gated:** wiring Phase 2 into the unattended launchd/cron daily job. Per the
  skill, that waits for ~a week of trusted supervised runs. Until then, run it manually:
  `Workflow({ scriptPath: 'scripts/refresh-workflow.js' })` (real) or
  `{ args: { dryRun: true } }` (read-only).

## Why

`marketing-os-refresh` currently runs as one monolithic session: steps 0–8 top to
bottom in a single context. Measured today:

- `data.js` (step 0 read) = 138 KB ≈ **34.5k tokens**.
- `state/lessons.jsonl` is small now (22 lines) but **append-only and unbounded**, and
  step 0 says "read every lesson."
- Live re-queries in steps 1–5 (PostHog experiment results, funnel, Klaviyo, Meta) add
  another ~15–40k of verbose JSON.
- Tom's ideas bank is ~80k tokens (must never load whole).

Two structural problems, independent of whether it fits today:

1. **Synthesis runs on the most-degraded context.** The Command Center rewrite (step 6)
   and next-experiment design (step 7) happen *last*, after the context is full of raw
   API dumps from steps 1–5. The highest-value reasoning gets the worst context.
2. **It scales badly and must eventually run unattended daily.** `data.js`, the ledger,
   and history all grow. "Probably fits" is not a foundation for an autonomous job.

## Target architecture: orchestrator + disposable read-agents

The skill session becomes a thin **orchestrator**. Each data-heavy step is dispatched to
a **subagent** that does the verbose reading in *its own* context and returns a compact
structured finding (~200–400 tokens). The subagent's context is discarded on return, so
the orchestrator never accumulates raw API exhaust.

```
orchestrator (holds: goal + ledger + commandCenter slice + 4 compact findings)
  ├─ step 1  → Experiments agent   → {experiments[], scored_predictions[], headline}
  ├─ step 2  → Funnel agent        → {stages[], biggest_leak, hypotheses[], fix_to_movement[], headline}
  ├─ step 3  → Campaigns agent     → {spend_7d, cpl, delivery, by_segment[], anomalies[], headline}
  ├─ step 4  → Lifecycle agent     → {flows[], top_gap, headline}
  │            (steps 1–4 run in PARALLEL — they share no state)
  ├─ step 5  measurement integrity → folded into the Funnel + Experiments agents
  ├─ step 0/6 resolve due predictions, write lessons, re-rank Command Center  ← clean context
  ├─ step 7  design next experiment FROM THE ROADMAP (state/experiment-roadmap.md)
  └─ step 8  build.py → git commit/push → refresh-log → summary
```

Synthesis (steps 0-resolve, 6, 7) now runs on a clean context of conclusions, not JSON.

### Return contracts (keep them small, enforce with schemas)

Each read-agent is forced to return JSON matching a schema. Sketches:

**Experiments**
```json
{
  "experiments": [
    {"id":"PH-1234","name":"...","surface":"signup-modal","status":"running",
     "exposures":{"control":210,"variant":198},"powered":true,
     "trend":"variant +6pp on signup_completed","action":"conclude-winner|keep-running|stop"}
  ],
  "scored_predictions": [
    {"id":"PRED-2026-05-20-...","actual":0.071,"verdict":"partial","lesson":"one line"}
  ],
  "headline": "PH-1234 ready to call; one due prediction scored partial"
}
```

**Funnel**
```json
{
  "stages":[{"step":"signup_modal_opened→signup_completed","rate":0.34,"delta_vs_history":-0.04,"n":540}],
  "biggest_leak":{"stage":"...","why":"...","leverage_to_paid":"high"},
  "hypotheses":["..."],
  "fix_to_movement":[{"shipped":"OS-SIGNUP-GOOGLE","predicted":0.40,"actual":0.37,"moved":true}],
  "measurement_ok": true,
  "headline":"biggest leak is modal→complete, down 4pp"
}
```

**Campaigns**: `{spend_7d, cpl, delivery, by_segment[], anomalies[], headline}`
**Lifecycle**: `{flows[], top_gap, headline}`

The orchestrator composes the four `headline`s + `biggest_leak` + `scored_predictions`
into the day's writes. That payload is ~2–4k tokens total.

## Two implementation options

### Option A — Claude Code subagents (Agent/Task tool), invoked from the skill run
- Phase-1 friendly: the skill stays a prose playbook; steps 1–4 become "dispatch a
  subagent with this brief, expect this schema back."
- Parallel dispatch of the four read-agents in one message.
- Lowest lift, runs in a normal interactive or cron session.
- Weaker on deterministic resumability (no built-in run journal).

### Option B — Workflow tool (deterministic JS orchestration)
- `parallel()` the four read-agents, `pipeline()` the synthesis, `schema` enforces the
  return contracts, `budget` caps tokens, `resumeFromRunId` gives true resume.
- Best fit for the **fully-unattended daily** end state.
- Bigger lift: the orchestration logic moves into a JS workflow script; the skill becomes
  the brief that launches it. Requires explicit opt-in to run.

**Recommendation: phased.**
- **Phase 1 (now): Option A.** Convert steps 1–4 to dispatched read-agents with schemas,
  keep synthesis in the orchestrator, add the run-state file below. This alone fixes
  "synthesis on degraded context" and cuts orchestrator peak context an estimated ~50%.
- **Phase 2 (when wired to the daily launchd job): Option B.** Port orchestration to a
  Workflow script for resumability, budget control, and enforced structured outputs.

## Resumability + idempotency (required before unattended)

Add `state/run-YYYY-MM-DD.json`: records which steps completed and their findings. On
re-invocation, skip completed steps and resume. Make writes idempotent:

- Ledger appends keyed by `id` — never double-append a prediction or its resolution.
- `git` commit + push happens **once**, at step 8 only.
- `build.py` is already idempotent (re-render is safe).

## Token budget: before vs after (estimate)

| | Monolith (today) | Phase-1 restructure |
|---|---|---|
| Orchestrator peak | ~80–130k, synthesis at the worst point | ~40–60k, synthesis on clean context |
| Heavy reads | all in the one context | isolated per subagent, discarded on return |
| Scaling headroom | degrades as data.js + ledger grow | each read-agent absorbs its own growth |

## Concrete changes

1. `SKILL.md` steps 1–4: rewrite each as "dispatch a read-agent with brief X, expect
   schema Y." Add a short "Read-agent contracts" reference section (or a sibling file
   `references/read-agent-contracts.md` if it gets long).
2. New `state/experiment-roadmap.md` (already referenced by the step-7 edit shipped today).
3. New `state/run-YYYY-MM-DD.json` run-state handling in step 0 and step 8.
4. Phase 2 only: `scripts/refresh-workflow.js` Workflow script; SKILL.md launches it.

## Risks + rollback

- **Subagents lack the orchestrator's full context.** Mitigation: each dispatch brief
  carries the goal, the relevant IDs, and the few lessons that bear on that step.
- **Structured-output drift.** Mitigation: enforce the schema (Agent `schema` option /
  Workflow `StructuredOutput`).
- **MCP availability in headless cron.** PostHog/Klaviyo MCP that are interactively
  authenticated may be absent in an unattended run. Must verify before Phase 2; the
  deterministic `build.py` already pulls most data, so read-agents lean on `data.js`
  first and live MCP second.
- **Rollback:** all changes are in `SKILL.md` + a few `state/` files; `git revert`.

## Decisions needed from Alejo

1. Approve **Phase 1 (Option A)** to implement now? (Reversible, ~one editing pass.)
2. Is **Phase 2 (Workflow port)** the intended end state once the daily launchd job runs
   this unattended, or do you want to stay on interactive subagents?
3. OK to add the two new state files (`experiment-roadmap.md`, `run-*.json`) to the repo?

# Read-agent contracts (Phase 1 orchestrator pattern)

Steps 1–4 of `marketing-os-refresh` are **delegated to subagents** so their verbose
reads (PostHog, Klaviyo, Meta, the full `data.js`) never accumulate in the orchestrator
context. Each agent does its own reading and returns **only** the compact JSON below.

## How the orchestrator dispatches

- Use the **Agent tool**, `subagent_type: general-purpose`, and dispatch all four in a
  **single message** so they run concurrently (steps 1–4 share no state).
- Each brief must carry: today's goal, the `dueForReview` prediction IDs + their metrics
  (so the agent can fetch the `actual`), and the path to `data.js`
  (`/Users/alejo/Documents/Claude/ablo-marketing-os/data.js`).
- **Data source order:** read the relevant slice of `data.js` first (build.py already
  pulled most data). Hit live MCP only for what is missing or needs a fresher read.
- **Read-only.** Agents gather and return. They never write the ledger, edit
  `commandCenter`, create PostHog drafts, or touch git. All writes stay in the orchestrator.
- **Return contract:** the agent's final message must be **only** the JSON object below,
  valid and parseable. The orchestrator validates on return; if malformed, re-dispatch once.

## 1. Experiments agent

Brief: for each running experiment pull results + exposures and judge power; read each
shipped before/after metric; for each `dueForReview` prediction whose metric it can see,
read the `actual` and score it.

```json
{
  "experiments": [
    {"id":"PH-1234","name":"...","surface":"signup-modal","status":"running",
     "exposures":{"control":210,"variant":198},"powered":true,
     "trend":"variant +6pp on signup_completed","action":"conclude-winner|keep-running|stop"}
  ],
  "before_after": [
    {"id":"OS-SIGNUP-GOOGLE","metric":"signup_completion_rate","before":0.31,"after":0.37,"held":true}
  ],
  "scored_predictions": [
    {"id":"PRED-2026-05-20-...","metric":"...","actual":0.071,"verdict":"hit|partial|miss","lesson":"one line"}
  ],
  "measurement_ok": true,
  "headline": "PH-1234 ready to call; one due prediction scored partial"
}
```

## 2. Funnel agent

Brief: read the live funnel (per-stage reach + same-user activation spine + leaks block)
**and `live.landingPages`** (per-entry-page engage% + signup%), compare to `history.jsonl`,
score any `dueForReview` funnel-fix predictions, and name the single biggest leak by
leverage toward paid conversion. **Treat top-of-funnel bounce (land→engage, land→signup)
as a first-class leak, not "normal" homepage behavior.** It is the largest loss of humans
by raw volume. If the homepage or a paid landing page is the biggest leak by volume, say so
and name the worst-converting high-volume page; a 2x signup-rate gap between two landing
pages is proof the page, not the ad, is the lever.

```json
{
  "stages": [
    {"step":"signup_modal_opened→signup_completed","rate":0.34,"delta_vs_history":-0.04,"n":540}
  ],
  "biggest_leak": {"stage":"...","why":"...","leverage_to_paid":"high"},
  "hypotheses": ["...", "..."],
  "landing_pages": {
    "home": {"path":"/","visitors":537,"engagePct":22.3,"signupPct":6.7},
    "worst": {"path":"/toddler","visitors":139,"engagePct":18.7,"signupPct":2.2},
    "page_is_the_leak": true,
    "cro_hypothesis": "one page-level bet, UTM-tagged so the lift is measurable"
  },
  "fix_to_movement": [
    {"shipped":"OS-...","metric":"...","predicted":0.40,"actual":0.37,"moved":true}
  ],
  "measurement_ok": true,
  "headline": "biggest leak is modal→complete, down 4pp vs history"
}
```

## 3. Campaigns agent

Brief: read the Meta autopilot state (spend, CPL, delivery health, per-segment). Extract
what is working, what is wasting money, whether budget sits on the converting segments
(Kids, Swim), and flag anomalies (zero-spend days, CPL spikes, tracking gaps).

```json
{
  "spend_7d": 1400, "cpl": 18.2, "delivery": "healthy|throttled|paused",
  "by_segment": [{"segment":"Kids","cpl":14.0,"converting":true}],
  "anomalies": ["..."],
  "headline": "spend healthy; Kids CPL best, Menswear wasting"
}
```

## 4. Lifecycle agent

Brief: read Klaviyo flow status and the prepared-but-unwired templates. Name the single
highest-leverage lifecycle gap (e.g. an Activate or AHA flow that exists but is wired to
nothing).

```json
{
  "flows": [{"name":"Welcome","status":"live|draft|unwired"}],
  "top_gap": {"flow":"...","leverage":"...","why":"..."},
  "headline": "AHA flow built but wired to nothing — highest-leverage gap"
}
```

## What the orchestrator does with the returns

- `scored_predictions` (from Experiments + Funnel) → resolve those `dueForReview` records
  in `state/lessons.jsonl` and write the one-line `lesson` (step 0-resolve).
- `measurement_ok: false` from either → flag a tracking regression loudly (step 5).
- `headline`s + `biggest_leak` + segment/anomaly/gap signals → re-rank the Command Center
  (step 6) and feed the experiment roadmap (step 7).
- `landing_pages` (page-level CRO read) → drive step 2b (question the frame): if the worst
  high-volume page is the biggest leak by volume and has no owner, add a Command Center item;
  its `cro_hypothesis` feeds the roadmap as a UTM-tagged page/landing test.

## 5. QA skeptic agents (step 7.5)

After synthesis proposes the re-rank, predictions, and conclusions, dispatch **2-3
skeptic agents in parallel**, each told to **REFUTE** the proposal, not bless it. Give
each a distinct lens so they do not share a blind spot. Each is read-only and returns
only the JSON below.

- **Lens A — numbers:** re-verify every figure in the proposal (re-rank rationale,
  prediction baselines/targets, any conclusion) against `data.js` and `history.jsonl`.
  Flag anything hallucinated, stale, or off.
- **Lens B — calls:** attack the judgment. Is any "winner" actually powered (~200
  exposures/variant)? Does every Command Center item still ladder to the goal? Does each
  new prediction respect `calibration` (humble when `n` is thin), or is it optimistic?
- **Lens C — boundary:** did the run auto-apply anything irreversible or user-visible
  (see the safety boundary in SKILL.md)? Those must be staged + escalated, not committed.

```json
{
  "lens": "numbers|calls|boundary",
  "refutations": [
    {"decision": "moved price-ask to #1", "verdict": "refuted|upheld", "reason": "...", "evidence": "data.js / history.jsonl ref"}
  ],
  "qa_lessons": [
    {"lesson": "forward-looking rule, e.g. confirm ~200 exposures/variant before calling a winner", "confidence": "high|med|low"}
  ],
  "verdict": "pass|revise|hold",
  "headline": "one line"
}
```

The orchestrator: revises or holds any **refuted** decision it cannot defend, writes each
`qa_lesson` as a `lesson` tagged `qa` in `state/lessons.jsonl` (read first next run), and
only then proceeds to publish (step 8).

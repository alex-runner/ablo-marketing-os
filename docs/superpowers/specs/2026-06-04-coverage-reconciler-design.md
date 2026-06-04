# Coverage Reconciler — design spec

Date: 2026-06-04
Status: approved design, pre-implementation
Repo: `alex-runner/ablo-marketing-os`

## Problem

The Marketing OS is a curated pull from known sources with known schemas. It
faithfully surfaces known-knowns and is blind to anything nobody explicitly
wired. Two real misses on 2026-06-04 motivated this:

1. A live A/B test (the `/try` vs homepage paid landing split) existed as a
   ClickUp task but never appeared in the OS Experiments tab, because that tab
   only pulls PostHog experiment objects. A Meta-level landing split has no
   PostHog experiment object, so the OS could not see it.
2. The `/try` flow fires its own event taxonomy (`tbs_*` = "try before signup"),
   which the funnel was never told about. The OS measured `/try` with the
   homepage's events (`cta_clicked`), so a whole sub-funnel was invisible and
   mismeasured.

Both are unknown-unknowns: the OS had no mechanism to notice surface area it was
not told to track. Fixing the instances (done) does not fix the class.

## Goal

Give the OS a discovery/reconciliation layer that, every build, enumerates the
live marketing surface area and diffs it against a registry of what the OS
models. Live-but-unmodeled = a blind spot. Auto-wire the unambiguous, reversible
cases; escalate the judgment cases to the daily agent. Surface a ranked
"Blind spots" list so nothing stays invisible.

Success = the two misses above would have been caught automatically: the `/try`
experiment task surfaced as an escalated experiments blind spot, and the `tbs_*`
event cluster surfaced as an escalated unmodeled high-volume flow — both in the
Coverage tab within one build, for the agent to resolve.

## Non-goals (v1)

- No auto-construction of funnels from discovered event clusters (the fragile
  part). A new event cluster is *escalated*, not auto-modeled.
- **No auto-creation of experiment cards from a name regex.** v1 escalates
  experiment-looking tasks; it does not auto-stub them (see Component 4).
- **The coverage layer never writes `content.json`.** build.py writes only
  `data.js` and `coverage-registry.json`. Any change to the brain-owned strategy
  file (experiment cards, Command Center items) is made by the *agent* in the
  reasoning lane, never by the data-refresh build. This preserves the clean
  09:00 data-refresh vs 09:20 reasoning separation.
- No new infrastructure, no new external services. Reuse the existing
  build.py → data.js → index.html pipeline and the `~/.local/bin/clickup` helper.
- Not a replacement for `reconcile_queue` (Command Center vs reality). This is
  the same pattern generalized to the whole surface; the two coexist.

## What this does NOT catch (honest scope)

This converts unknown-unknowns into **known-unknowns within the dimensions it
scans**. A genuinely novel surface *outside* those dimensions (a new channel
type, an offline touchpoint, a new tool the OS has no connector for) still stays
invisible until someone adds a scanner for it. The value is real — it closes the
gap inside the instrumented world, which is where today's two misses lived — but
it is not "total coverage," and the spec/UI must not imply that.

## Decisions (locked)

- Autonomy: **auto-wire the safe cases, escalate the rest.** Matches the OS's
  existing reversible-auto / escalate safety boundary. **In v1 there is no
  auto-wire — detect + escalate only.** The mechanical page/destination auto-wire
  and the explicit-tag experiment auto-wire both arrive in v2 (see Component 4).
- **Phased scope (changed after audit).** v1 scans the **proven need: events,
  experiments, and ClickUp tasks** — the exact two classes that caused today's
  misses. **v2 adds pages, channels, and flows** (Klaviyo + Meta) once the
  pattern has earned trust. Rationale: pages/channels/flows are both speculative
  *and* the highest-churn surfaces (new UTMs/ad sets/pages weekly), so they
  triple the new failure surface and the grooming burden in the critical daily
  build for unproven value. The registry and differ are dimension-generic, so v2
  is additive, not a rewrite. (Original ask was all six at once; phasing is the
  audit-driven risk reduction — overridable.)
- The Coverage view is **its own tab under Operate** (keeps the Command Center
  action queue clean).

## Architecture

The pattern: **registry (what we model) + scanners (what exists live) + differ
(the gap) + auto-wirer (close the safe gaps) + surface (show the rest).** Runs
inside `build.py` every build. Detection is fully deterministic; the LLM agent is
only needed to *resolve* escalated gaps, never to *notice* them.

```
build.py:
  pull live data (as today)
    -> scan_coverage(env)        # enumerate each dimension's live surface
    -> reconcile_coverage(reg)   # diff live vs registry -> blind spots + stale
    -> autowire_coverage(...)    # v1: no-op (detect+escalate). v2: safe wirings -> registry only (never content.json)
    -> live.coverage             # blind spots + stale + auto-wired log
  render Coverage tab + header health pill
```

### Component 1: The registry — `coverage-registry.json` (git-tracked)

The explicit manifest of what the OS models, plus per-dimension dismissals and
thresholds. Git-tracked so dismissals persist and coverage history is auditable.

```json
{
  "version": 1,
  "updated": "2026-06-04",
  "dimensions": {
    "events":      { "modeled": ["$pageview","cta_clicked","signup_modal_opened","signup_completed","model_generated","tryon_completed","..."],
                     "ignore":  ["$web_vitals","$autocapture","$feature_flag_called","..."],
                     "minUsers30d": 10 },
    "experiments": { "modeled": ["PH-374260","OS-SIGNUP-GOOGLE","OS-TRY-VS-HOME"],
                     "clickupMapped": {"OS-TRY-VS-HOME":"86ba9n6my"},
                     "ignore": [] },
    "pages":       { "modeled": ["/","/toddler","/plus-size","/try","/pricing"], "ignore": ["/auth/verify","/studio"], "minVisitors": 20 },
    "channels":    { "modeled": ["(direct)","meta","linkedin","..."], "ignore": [] },
    "flows":       { "klaviyoModeled": ["TG3ii9"], "metaCampaignsModeled": ["..."], "ignore": [] },
    "clickupTasks":{ "modeled": ["86ba9n6my","..."], "ignore": ["..."], "list": "901415977874" }
  }
}
```

Notes:
- `ignore` entries SHOULD carry a reason in a sibling `ignoreReasons` map (so a
  dismissal is auditable). Keep it a flat map `id -> reason`.
- Thresholds keep low-volume noise out of the blind-spot list.

**Write discipline (prevents a noisy daily commit — audit risk #5):**
- Serialize with **stable sorted keys** and sorted list members, so logically
  identical state is byte-identical across runs.
- **Write only on real change.** Build the new registry in memory, canonical-
  serialize it, compare to the on-disk canonical form, and write *only if they
  differ*. A no-op build must leave `coverage-registry.json` byte-identical so it
  never enters the daily commit.
- `updated` changes **only when the modeled/ignore content changes**, never as a
  bare per-run timestamp (a timestamp bump would itself cause a daily diff).

### Component 2: The scanners — `scan_coverage(env)` in build.py

One function per dimension, each returns the live surface for that dimension.
Reuse existing pulls where possible; add only what is missing. **v1 implements
`scan_events`, `scan_experiments`, `scan_clickup`. `scan_pages`,
`scan_channels`, `scan_flows` are v2** (tagged below).

- `scan_events` (v1): HogQL `SELECT event, count(DISTINCT person_id) AS users FROM
  events WHERE timestamp >= now() - INTERVAL 30 DAY GROUP BY event`. Returns
  `[{event, users}]`. Cluster by prefix before `_` for the "whole new flow"
  signal (e.g. `tbs_`, `onboarding_`).
- `scan_experiments` (v1): PostHog experiments (already pulled) + a ClickUp scan
  of the Ablo Studio list for open tasks that look like experiments. The name
  regex `experiment|test|a/b|split|variant` is a **weak signal used only to
  ESCALATE** (surface in the Coverage tab), never to auto-create a card — see
  Component 4. False matches are cheap here because they only add a line to a
  blind-spot list a human triages, not a card to the user-facing Experiments tab.
- `scan_pages` (v2): landingPages entry pathnames (already pulled) + Meta ad
  destination URLs (from the autopilot state / Meta read).
- `scan_channels` (v2): PostHog UTM sources (already in `channels`) + Meta ad-set
  destinations/UTMs.
- `scan_flows` (v2): Klaviyo flows (already pulled) + Meta campaigns/ad sets list.
- `scan_clickup` (v1): open tasks in the Ablo Studio list (already pulled for the
  Command Center feed) whose id is NOT referenced by any Command Center item or
  by `experiments.clickupMapped` — i.e. marketing work the OS does not surface
  anywhere. (Concrete rule, not a fuzzy "looks marketing" judgment.)

Each scanner degrades to "no data" on a failed pull (never crash the build), and
a dimension with no live data is skipped (not reported as "everything stale").

### Component 3: The differ — `reconcile_coverage(registry, scans)`

Pure function, no I/O, unit-testable. For each dimension:
- `blind = live - modeled - ignore`, filtered by the dimension threshold,
  ranked by volume (users/visitors) then recency.
- `stale = modeled - live` (a modeled item that stopped appearing — candidate
  tracking regression; flagged, never auto-removed).

Returns `{dimension: {blind: [...], stale: [...]}}` with each blind item shaped
`{key, dimension, where, volume, cluster?, action}` (same field names as the
`live.coverage.blindSpots` items below). The `status` field
(`escalated` | `auto-wired`) is set later by the auto-wirer, not the differ.

### Component 4: The auto-wirer — `autowire_coverage(registry, diff, env)`

The bar is deliberately high: auto-wire ONLY when the wiring is mechanical,
unambiguous, reversible, and touches NO brain-owned file. The signature takes
`registry` (not `content`) on purpose — **the auto-wirer never edits
`content.json`.**

**v1: no auto-wire. Detection + escalate only.** Every v1 blind spot is surfaced
in the Coverage tab for the agent/human to resolve. This is the lowest-risk start
and it still catches both real misses — the `/try` task and the `tbs_*` cluster
both ESCALATE, which is exactly what was needed to stop missing them. Auto-wiring
adds risk for value we have not yet proven we need.

Escalated (v1):
- New high-volume **event cluster** (e.g. `tbs_*`) → blind spot, action
  "investigate + map a funnel or dismiss". A correct funnel needs human judgment.
- **Experiment-looking ClickUp task** (weak name match) → blind spot, action
  "confirm it is a real experiment, then wire or dismiss". **NOT auto-stubbed:** a
  name regex is judgment, and a false match (e.g. "test new pricing copy", "split
  the budget") would inject a junk card into the *user-facing* Experiments tab.
  Surfacing it in the Coverage triage list is enough and keeps junk out.

**v2: introduce auto-wire, only for mechanical / hard-signal cases:**
- **New entry page / Meta destination with traffic** → add to `pages.modeled`
  (landingPages already measures it; this only marks it covered) and flag poor
  conversion. Mechanical, reversible, registry-only.
- **Experiment task carrying an explicit opt-in ClickUp tag** (a deliberate label
  like `os-track`, NOT a name regex) → the tag is a hard signal of intent, so
  promotion is safe. Even then, the experiment card itself is materialized by the
  **agent in the reasoning lane** (it owns `content.json`); the auto-wirer only
  records the mapping in `coverage-registry.json` and flags it for the agent.

All auto-wire side effects are confined to `coverage-registry.json`
(stable-ordered, write-on-change-only) and logged in `live.coverage.autowired`,
so every change is visible and reversible via git.

### Component 5: The surface — `live.coverage` + Coverage tab

`live.coverage` shape (v1 example — both real misses ESCALATE; `autowired` empty
until v2):
```json
{
  "updated": "2026-06-04",
  "blindSpots": [
    {"key":"tbs_*","dimension":"events","where":"PostHog, 61 users/30d","volume":61,"cluster":true,"action":"Investigate the /try value-first flow; map a funnel or dismiss","status":"escalated"},
    {"key":"86ba9n6my","dimension":"experiments","where":"ClickUp Ablo Studio, name matches 'A/B test'","volume":null,"action":"Confirm it is a real experiment, then wire (OS-* card) or dismiss","status":"escalated"}
  ],
  "stale":     [ {"key":"some_event","dimension":"events","note":"modeled but 0 users in 30d — possible tracking regression"} ],
  "autowired": [],
  "summary":   {"blind": 2, "autowired": 0, "stale": 1}
}
```

UI: a new **Coverage** tab under Operate. Renders Blind spots (ranked, with
dimension chip, volume, suggested action, escalated/auto-wired badge), Stale/
broken, and (from v2) an Auto-wired log. Plus a one-line health pill in the
footer/header: "Coverage: 2 blind spots need you, 1 stale."

### Component 6: Agent integration — SKILL.md step "Coverage scan"

A new step in `marketing-os-refresh` (after the funnel/experiments reads): read
`live.coverage`. For each escalated blind spot, investigate (the `tbs_*`
playbook done today: query the events, map the real funnel), then either wire it
into the OS (funnel stage / experiment card / Command Center item) or dismiss it
to `registry.ignore` with a reason. (In v1 every coverage item is escalated, so
this resolution step is the whole loop; v2 adds a sanity-check of any auto-wired
registry mappings.) The agent owns `content.json`, so any experiment card or
Command Center item is written here, in the reasoning lane. This is where
unknown → known completes; turning on flows / launching tests still escalates to
Alejo.

## Data flow

1. `build.py` pulls live data exactly as today.
2. `scan_coverage(env)` enumerates each dimension's live surface (reusing
   existing pulls + the new events/clickup/meta-destination queries).
3. `reconcile_coverage(registry, scans)` diffs vs the registry → blind + stale.
4. `autowire_coverage(...)` applies safe wirings (none in v1 — detect + escalate
   only) and, when it does, updates only `coverage-registry.json` on real change
   and logs what it did. Never writes `content.json`.
5. `live.coverage` is embedded in data.js; the Coverage tab + health pill render.
6. The daily agent reads `live.coverage` and resolves escalated gaps.

## Error handling

- Any scanner pull failure → that dimension reports "no data", build continues.
  Never crash the build; the site must always render (existing invariant).
- A failed pull must NOT produce false "stale" (modeled-but-missing) entries —
  `stale` is only computed for dimensions whose live scan succeeded.
- Registry write is atomic (write temp, replace) so a crashed build cannot
  corrupt it, and write-on-change-only (see registry write discipline).
- Auto-wire (v2) is idempotent: re-running the build does not create duplicate
  mappings (guard on the ClickUp task id already in `clickupMapped`).

**The realistic failure mode is soft, not an outage: erosion of trust.** The
fail-open design protects the build, so the risk is a noisy blind-spot list or a
junky commit log that makes you stop reading the tab. Mitigations are first-class
requirements, not nice-to-haves: per-dimension volume thresholds, dismiss-with-
reason `ignore`, v1 = escalate-only (no auto-created cards), registry
write-on-change-only, and a registry seeded from today's known-good state so day
1 is quiet. If the Coverage tab is noisy, it has failed regardless of correctness.

## Testing

- Unit-test `reconcile_coverage` (pure): given a fixed registry + synthetic
  scans, a known blind spot appears, a known-ignored item does not, a stale item
  is detected, thresholds filter low-volume noise.
- Unit-test that in v1 nothing auto-wires: an experiment-looking task and an
  event cluster both land in `blindSpots` with `status:"escalated"`,
  `autowired` stays empty, and `content.json` is never touched.
- Unit-test the registry write discipline: a no-op build produces a
  byte-identical `coverage-registry.json` (no write, no diff); a real change
  writes once with stable key order.
- Regression fixtures: the two real misses. The `tbs_*` cluster must surface as
  an escalated events blind spot; a synthetic "Experiment: X — A/B test" ClickUp
  task must surface as an escalated experiments blind spot (NOT auto-stubbed).
- Build smoke test: `python3 build.py` runs clean, `live.coverage` populates,
  data.js stays valid, the site renders the Coverage tab.
- (v2) Unit-test `autowire_coverage`: a page-destination auto-wire is idempotent;
  an explicit `os-track`-tagged task records a registry mapping but writes no
  `content.json`.

## Rollout / seeding

- Seed `coverage-registry.json` from today's known-good state (all currently
  modeled events/experiments/pages/channels/flows/tasks), so day 1 is not a wall
  of false positives. The first real blind spots are then genuinely new.
- Ship v1 = detection + escalation + the Coverage tab (no auto-wire). The
  SKILL.md step lands in the same change so the agent starts resolving gaps the
  next run. v2 (pages/channels/flows + the two auto-wire rules) ships only after
  v1 has earned trust over a week of low-noise runs.

## Success criteria (v1)

- A new live experiment that lives outside PostHog (e.g. a Meta split tracked in
  ClickUp) appears as an **escalated experiments blind spot** within one build,
  with a suggested action. (Auto-stub is a v2 behavior, gated behind an explicit
  `os-track` tag.)
- A new high-volume event cluster appears as an escalated blind spot within one
  build, with a suggested action.
- A modeled event that stops firing appears as a stale/regression flag.
- **Zero false positives** from the seeded registry on day 1, and a no-op build
  produces no `coverage-registry.json` diff (no commit-log noise).
- The site never fails to render due to a coverage scan error.

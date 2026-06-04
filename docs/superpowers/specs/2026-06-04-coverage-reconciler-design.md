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
experiment task auto-wired into an OS experiment stub, and the `tbs_*` event
cluster escalated as an unmodeled high-volume flow.

## Non-goals (v1)

- No auto-construction of funnels from discovered event clusters (the fragile
  part). A new event cluster is *escalated*, not auto-modeled.
- No new infrastructure, no new external services. Reuse the existing
  build.py → data.js → index.html pipeline and the `~/.local/bin/clickup` helper.
- Not a replacement for `reconcile_queue` (Command Center vs reality). This is
  the same pattern generalized to the whole surface; the two coexist.

## Decisions (locked)

- Autonomy: **auto-wire the safe cases, escalate the rest.** Matches the OS's
  existing reversible-auto / escalate safety boundary.
- v1 scans **all six dimensions**: events, experiments, pages, channels, flows
  (Klaviyo + Meta), ClickUp marketing tasks.
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
    -> autowire_coverage(...)    # apply safe wirings, update registry, emit OS-* stubs
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

### Component 2: The scanners — `scan_coverage(env)` in build.py

One function per dimension, each returns the live surface for that dimension.
Reuse existing pulls where possible; add only what is missing.

- `scan_events`: HogQL `SELECT event, count(DISTINCT person_id) AS users FROM
  events WHERE timestamp >= now() - INTERVAL 30 DAY GROUP BY event`. Returns
  `[{event, users}]`. Cluster by prefix before `_` for the "whole new flow"
  signal (e.g. `tbs_`, `onboarding_`).
- `scan_experiments`: PostHog experiments (already pulled) + a ClickUp scan of
  the Ablo Studio list for open tasks whose name matches
  `experiment|test|a/b|split|variant` (case-insensitive).
- `scan_pages`: landingPages entry pathnames (already pulled) + Meta ad
  destination URLs (from the autopilot state / Meta read).
- `scan_channels`: PostHog UTM sources (already in `channels`) + Meta ad-set
  destinations/UTMs.
- `scan_flows`: Klaviyo flows (already pulled) + Meta campaigns/ad sets list.
- `scan_clickup`: open tasks in the Ablo Studio list (already pulled for the
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

### Component 4: The auto-wirer — `autowire_coverage(content, registry, diff, env)`

Deterministic rules. Auto-wire ONLY when wiring is unambiguous and reversible;
everything else is left as an escalated blind spot.

Auto-wire rules (v1):
- **New experiment-tagged ClickUp task** → create an `OS-<slug>` experiment stub
  in `experimentsCurated` (status "discovered — needs metric mapping"), add the
  task id to `experiments.clickupMapped`, add the id to `experiments.modeled`.
  This is the `/try` wire-up, automated. The agent later fills the metric.
- **New entry page / Meta destination with traffic** → add to `pages.modeled`
  (landingPages already measures it; this just marks it covered) and flag if it
  converts poorly.

Escalate (never auto-wire in v1):
- New high-volume **event cluster** (e.g. `tbs_*`) → blind spot with action
  "investigate + map a funnel or dismiss". Building a correct funnel needs human
  judgment.
- New **Klaviyo flow / Meta campaign** the OS does not represent → blind spot.
- Anything ambiguous.

Every auto-wire updates `coverage-registry.json` in place and is logged in
`live.coverage.autowired` so the change is visible and reversible via git.

### Component 5: The surface — `live.coverage` + Coverage tab

`live.coverage` shape:
```json
{
  "updated": "2026-06-04",
  "blindSpots": [ {"key":"tbs_*","dimension":"events","where":"PostHog, 61 users/30d","volume":61,"cluster":true,"action":"Investigate the /try value-first flow; map a funnel or dismiss","status":"escalated"} ],
  "stale":     [ {"key":"some_event","dimension":"events","note":"modeled but 0 users in 30d — possible tracking regression"} ],
  "autowired": [ {"key":"OS-NEW-TEST","dimension":"experiments","note":"auto-created stub from ClickUp task 86xxxx"} ],
  "summary":   {"blind": 2, "autowired": 1, "stale": 0}
}
```

UI: a new **Coverage** tab under Operate. Renders Blind spots (ranked, with
dimension chip, volume, suggested action, escalated/auto-wired badge), Stale/
broken, and an Auto-wired log. Plus a one-line health pill in the footer/header:
"Coverage: 2 blind spots — 1 auto-wired, 1 needs you."

### Component 6: Agent integration — SKILL.md step "Coverage scan"

A new step in `marketing-os-refresh` (after the funnel/experiments reads): read
`live.coverage`. For each escalated blind spot, investigate (the `tbs_*`
playbook done today: query the events, map the real funnel), then either wire it
into the OS (funnel stage / experiment card / Command Center item) or dismiss it
to `registry.ignore` with a reason. Sanity-check each auto-wired stub. This is
where unknown → known completes. Auto-wiring stays within the existing reversible
safety boundary; turning on flows / launching tests still escalates to Alejo.

## Data flow

1. `build.py` pulls live data exactly as today.
2. `scan_coverage(env)` enumerates each dimension's live surface (reusing
   existing pulls + the new events/clickup/meta-destination queries).
3. `reconcile_coverage(registry, scans)` diffs vs the registry → blind + stale.
4. `autowire_coverage(...)` applies safe wirings, updates the registry + emits
   OS-* stubs, logs what it did.
5. `live.coverage` is embedded in data.js; the Coverage tab + health pill render.
6. The daily agent reads `live.coverage` and resolves escalated gaps.

## Error handling

- Any scanner pull failure → that dimension reports "no data", build continues.
  Never crash the build; the site must always render (existing invariant).
- A failed pull must NOT produce false "stale" (modeled-but-missing) entries —
  `stale` is only computed for dimensions whose live scan succeeded.
- Registry write is atomic (write temp, replace) so a crashed build cannot
  corrupt it.
- Auto-wire is idempotent: re-running the build does not create duplicate stubs
  (guard on the ClickUp task id already in `clickupMapped`).

## Testing

- Unit-test `reconcile_coverage` (pure): given a fixed registry + synthetic
  scans, a known blind spot appears, a known-ignored item does not, a stale item
  is detected, thresholds filter low-volume noise.
- Unit-test `autowire_coverage`: a new experiment-tagged task creates exactly one
  stub and is idempotent on re-run; an event cluster is left escalated (not
  auto-modeled).
- Regression fixtures: the two real misses. The `tbs_*` cluster must surface as
  an escalated events blind spot; a synthetic "Experiment: X — A/B test" ClickUp
  task must auto-wire to an OS stub.
- Build smoke test: `python3 build.py` runs clean, `live.coverage` populates,
  data.js stays valid, the site renders the Coverage tab.

## Rollout / seeding

- Seed `coverage-registry.json` from today's known-good state (all currently
  modeled events/experiments/pages/channels/flows/tasks), so day 1 is not a wall
  of false positives. The first real blind spots are then genuinely new.
- Ship detection + the two auto-wire rules + the Coverage tab together. The
  SKILL.md step lands in the same change so the agent starts resolving gaps the
  next run.

## Success criteria

- A new live experiment that lives outside PostHog (ClickUp-tagged) auto-appears
  as an OS experiment stub within one build.
- A new high-volume event cluster appears as an escalated blind spot within one
  build, with a suggested action.
- A modeled event that stops firing appears as a stale/regression flag.
- Zero false positives from the seeded registry on day 1.
- The site never fails to render due to a coverage scan error.

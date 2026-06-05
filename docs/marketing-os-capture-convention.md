# Marketing OS capture convention

How a new asset or initiative gets represented in the Marketing OS automatically, so nothing ships invisibly again. This is the written rule behind the Coverage Reconciler built into `build.py` (design: `docs/superpowers/specs/2026-06-04-coverage-reconciler-design.md`). It closes ClickUp task `86ba9n6w5` (the `/try` landing page shipped without ever appearing in the OS).

## The principle

Every build, `build.py` enumerates the live marketing surface and diffs it against `coverage-registry.json` (the manifest of what the OS already models). Anything live-but-unmodeled is a blind spot. The safe cases auto-wire, the rest escalate to the daily agent. Detection is deterministic, so a new initiative cannot stay invisible just because nobody wired it.

The flow (`build_coverage` in `build.py`): `scan_coverage` (enumerate live) then `reconcile_coverage` (diff vs registry) then `autowire_coverage` (close safe gaps) then emit `live.coverage` (the Coverage tab). It is fail-open: any scanner failure yields "no data" for that dimension and the build/site still render.

Scope is phased. v1 scans 3 dimensions (events, experiments, ClickUp tasks), the exact two classes that caused the misses. v2 adds pages, channels, and flows. The differ is dimension-generic, so v2 is additive.

## What counts as a trackable asset (per dimension)

- **Events** (`scan_events`): a live PostHog event over 30d that is not in `events.modeled` or `events.ignore`. Unmodeled events are clustered by prefix-before-`_`, so a whole new flow (e.g. `tbs_*`) reads as one blind spot. Filtered by `minUsers30d` (10) so low-volume noise is dropped.
- **Experiments** (`scan_experiments`): a PostHog experiment object, OR an open Ablo Studio ClickUp task whose name matches the regex `experiment|test|a/b|split|variant` (case-insensitive). This catches a Meta-level landing split that has no PostHog object but lives as a ClickUp task. The name match is a weak signal used only to escalate, never to auto-create a card.
- **ClickUp tasks** (`scan_clickup`): an open task in the Ablo Studio list (`901415977874`) whose id is NOT in `clickupTasks.modeled` and NOT in `experiments.clickupMapped`. That is concrete "marketing work the OS surfaces nowhere," not a fuzzy judgment.
- **Pages / channels / flows** (v2): a new entry page or Meta destination with traffic, a new UTM channel, a new Klaviyo flow or Meta campaign. Registered as v2 in the spec, not yet scanned.

A modeled item that stops appearing is flagged `stale` (possible tracking regression), never auto-removed.

## The ClickUp convention (the bridge)

`build.py` already pulls the Ablo Studio list (`901415977874`) live every build, so ClickUp is the capture surface. To make a new initiative auto-captured:

- **Create a ClickUp task in the Ablo Studio list.** Any open task there that the OS references nowhere surfaces as a `clickup` blind spot within one build, with the action "wire a Command Center item or dismiss." That alone makes it visible.
- **Name experiments with an experiment word.** Prefix with `Experiment:` or include `A/B`, `split`, `variant`, or `test` so `scan_experiments` catches it as an experiments blind spot. Match is on the task name, so put the word in the title.
- **Dismiss a non-marketing task with a reason.** Add its id to `clickupTasks.ignore` (or `experiments.ignore`) in `coverage-registry.json` AND add a one-line entry to the sibling `ignoreReasons` map. The reason is required by convention so every dismissal is auditable in git. No reason, no dismissal.

Note the visibility window: `fetch_clickup` exposes the top 12 open tasks (`active[:12]`), so the experiment/clickup scanners see that working set, not the entire backlog. Keep marketing initiatives near the top of the list (status, due date) so they fall inside the window.

## How resolution works

- **Auto-wire** (reversible, mechanical, touches only `coverage-registry.json`): v1 is intentionally no-op (`autowire_coverage` returns `[]`), so v1 is detect-and-escalate only. v2 adds two wirings: a new entry page with traffic into `pages.modeled`, and an explicit `os-track`-tagged experiment task into `experiments.clickupMapped`. Even then the experiment card itself is materialized by the agent in `content.json`, never by the build.
- **Escalate** (needs judgment): a new event cluster ("investigate, map a funnel stage or dismiss"), an experiment-looking task ("confirm it is a real experiment, then wire or dismiss"), or unmodeled marketing work. Blind spots rank by volume (distinct users) descending.
- **The daily agent resolves escalations.** The `marketing-os-refresh` step reads `live.coverage` and, per blind spot, either wires it in (funnel stage, experiment card, Command Center item in `content.json`, which the agent owns) or dismisses it to the registry with a reason. The build never writes `content.json`; that stays in the reasoning lane.

## Verdict: can 86ba9n6w5 close?

Yes. The reconciler implements the auto-capture the task asked for: ClickUp is the live bridge, and any new initiative surfaces within one build instead of shipping invisibly. The two original misses are both now caught. The `/try` experiment (ClickUp task `86ba9n6my`) is detected by `scan_experiments` via its `A/B` name and is now mapped in `experiments.clickupMapped`. The `tbs_*` event cluster is detected by `scan_events`. The HubSpot and Day Mode cases also resolved into the registry (`OS-DAYMODE` mapped, the HubSpot ops task `86baa3y5b` dismissed with a reason).

Residual gaps to keep honest:
- Only the 3 v1 dimensions are scanned. Pages, channels, and flows (v2) are not yet live, and any surface outside all six dimensions (an offline touchpoint, a tool with no connector) stays invisible until a scanner is added.
- The ClickUp scanners see only the top 12 open tasks (`fetch_clickup` cap), so an initiative buried deep in the backlog can be missed until it surfaces.

Neither blocks closing `86ba9n6w5`. Both are tracked scope in the design spec, not the original bug.

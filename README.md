# Ablo Studio · Marketing OS

The single internal home for Ablo Studio's marketing strategy and live execution.
One page, on the real Ablo Studio design system. Built so the team (and the team's
agents) always work from the same canon, and so a marketing agent can read the whole
operating picture — funnel, lifecycle, channels, experiments, campaigns — and act on it.

**Internal and confidential.** `noindex` + `robots.txt` disallow. Do not share the
link publicly.

## What's inside

| Group | Sections |
|---|---|
| Operate | **Command Center** — ranked action queue, anchored to KPIs, with the live ClickUp task feed · **Trends** — daily history, is it moving up or down |
| Strategy | Overview · Goals & OKRs · ICP & Segments · Positioning · Competition · Battle Card |
| Brand | Messaging & Perceptions · Brand Voice (with a copy-paste voice card for agents) |
| Growth | **Funnel** (PostHog) · **Lifecycle** (Klaviyo) · **Channels** (live UTM attribution) · **Content Calendar** · Experiments · Campaigns · Content |

## Hosting (static, GitHub Pages)

Static only, no backend. GitHub Pages serves `index.html` + `data.js`. The daily `build.py` runs on the Mac (launchd, see below), regenerates `data.js` + `history.jsonl`, and pushes. Tokens live in `~/.claude/.env` and are never published. The site is a `noindex` dashboard fed by the local daily job. (A `server.py` / Railway path with an in-app token editor was prototyped and then dropped on 2026-06-03 to keep the system lean; the static path is the single source of truth.)

## Connected sources

| Source | What it feeds | Auth |
|---|---|---|
| PostHog | Funnel, channel attribution (UTM), daily history, experiments | `POSTHOG_PERSONAL_API_KEY` |
| Klaviyo | Lifecycle flows + prepared emails | `KLAVIYO_API_KEY_ABLO` |
| Meta Ads | Campaign spend/CPL/signups (via the autopilot) | `META_ADS_TOKEN` |
| ClickUp | Live task feed in the Command Center (task source of truth) | `CLICKUP_TOKEN_ABLO` |
| Instagram | Organic follower/post stats (Content Calendar) | `META_ADS_TOKEN` (account-read) |

Instagram **publishing** by the agent and post-level engagement need an IG token with `instagram_content_publish` — the `META_IG_TOKEN` is currently expired. GA4 is intentionally **not** connected: PostHog already captures channel/UTM attribution tied to product events, which GA4 can't do. The **Command Center** items each carry a `ladder` field naming the KPI they move, so priority always means goal-impact. The **Content Calendar** is seeded; wiring it to a ClickUp calendar is queued (a ClickUp task was created).

### The three working surfaces

- **Funnel** renders the real product happy path (`$pageview → … → tryon_completed (aha) → checkout_started`)
  with a time-window selector (7d / 30d / 90d / since launch), the same-user activation spine, and a
  per-step leak diagnosis. Goal: see exactly where users drop on the way to the aha (try-on) and payment.
- **Lifecycle** renders the Klaviyo flows signups actually receive — the live onboarding flow's messages
  and performance, plus the lifecycle emails that are *built but wired to no flow*, and the behavioral-flow
  opportunities they map to.
- **Command Center** ties every live funnel leak to the one fix that moves it, ranked by leverage. This is
  the surface a daily routine rewrites: read funnel + campaigns + experiments + lifecycle, re-rank, write back.
- **Trends** answers "is the work moving the numbers?" — daily volume, conversion rates and cost with
  week-over-week deltas and sparklines. See "History" below.

## History (the daily time-series)

`build.py` keeps an append-only **`history.jsonl`**, one row per UTC day, committed on every refresh — so
trends survive and the agent can judge whether each change worked. Why JSONL and not a database: at ~1
snapshot/day of a few dozen scalars, JSONL is git-native (diffable, append-only), zero-dependency, and
readable by both the browser (sparklines) and the agent (Python). A database can't be queried client-side
from a static site and makes poor diffs; a single MD file isn't machine-trendable.

The clever bit: **the PostHog event log is the backfill.** Each run recomputes the full daily funnel-reach
series from event timestamps (self-healing, no drift), so volume/conversion history is real from launch.
Only the non-reconstructable fields (Meta cost, email rates, cumulative spine rates) are *persisted forward*
from the day they first appear. The site embeds the last 120 days into `data.js`; the agent reads
`history.jsonl` directly.

## How it works (hybrid data)

- **Curated strategy** lives in [`content.json`](content.json). Human-edited. Positioning,
  ICP, messaging, voice, goals, competition, Battle Card. Rarely changes; never auto-rewritten.
  The `funnelCurated` / `lifecycleCurated` / `channels` / `commandCenter` blocks are real
  snapshots that act as fallbacks (seeded by [`gen_sections.py`](gen_sections.py)).
- **Live data** is merged in by [`build.py`](build.py) on every run:
  - **Funnel** — live HogQL against PostHog (per-stage reach across 4 windows + the same-user
    activation spine).
  - **Lifecycle** — live Klaviyo API (flow statuses, the live flow's messages + performance,
    prepared templates).
  - **Campaigns** + the KPI strip read the `ablo-ads-autopilot` local state (spend / signups /
    CPL, delivery health, auto-generated funnel intelligence).
  - **Experiments** read PostHog. (See "Live PostHog" below.)
- `build.py` writes [`data.js`](data.js) (`window.ABLO_OS = {...}`), which `index.html` renders.
  Every live source degrades gracefully: if a pull fails, the curated fallback stays and the site
  never breaks. Credentials come from `~/.claude/.env` (`POSTHOG_PERSONAL_API_KEY`,
  `POSTHOG_PROJECT_ID`, `KLAVIYO_API_KEY_ABLO`).

```
content.json  ─┐
                ├─► build.py ─► data.js ─► index.html (renders)
live sources  ─┘
```

## Editing the strategy

Edit `content.json`, then run `python3 build.py` and refresh the page. No build tools,
no dependencies (stdlib Python only). The daily job will also pick up your edits.

## The daily run (what actually produces the commits)

Two launchd agents fire every morning. **This is the single source of truth for
"when does it run / when did it last run."** Check the logs under `~/.local/log/`,
*not* the repo's stale `.refresh.log` (see note below).

| # | LaunchAgent | Entrypoint | Schedule | What it does | Commit it makes | Real log |
|---|-------------|-----------|----------|--------------|-----------------|----------|
| 1 | `com.alejo.ablo-marketing-os.weekly` | `~/.local/bin/ablo-marketing-os-refresh.sh` | **daily 09:00** | deterministic data pull: `build.py` regenerates `data.js` + `history.jsonl`, stages tracked files only, commits, pushes `origin main` | `chore: daily data refresh <date>` | `~/.local/log/ablo-marketing-os.log` |
| 2 | `com.alejo.ablo-marketing-os-agent` | `~/.local/bin/ablo-marketing-os-agent.sh` | **Mon–Fri 09:20** | the LLM "brain": headless `claude -p` (sonnet) in an isolated worktree, re-ranks `content.json` + appends `state/lessons.jsonl`. `PUSH_MODE=live` deploys to `main` **only if** the QA self-check + secret-scan + build all pass; otherwise it pushes the proposal to branch `agent/daily` | `chore: autonomous marketing routine <date>` (only on a live deploy) | `~/.local/log/ablo-marketing-os-agent.log` |

> The launchd entrypoints live in `~/.local/bin/` (not the repo) on purpose: macOS
> TCC blocks a launchd job from executing a script inside `~/Documents` and from
> letting `git` discover the repo via CWD. The scripts work around this by staying
> outside `~/Documents` and pointing `git` at the repo with `--git-dir/--work-tree`.
> The repo keeps `refresh.sh` for **manual** runs from a Terminal (which has
> Documents access), and it must be kept in sync with the `~/.local/bin` copy.

A third commit shape, `chore: daily marketing routine <date>`, is **not** a cron —
it is the interactive `skill/marketing-os-refresh` skill run by hand in a Claude
Code session. If you see that message, a human (Alejo) ran the playbook, not launchd.

```bash
# run the data refresh now (manual, from a Terminal)
./refresh.sh
# run the brain now (manual): live deploy, skip the freshness gate
PUSH_MODE=live AGENT_SKIP_FRESHNESS=1 ~/.local/bin/ablo-marketing-os-agent.sh
# check / load / unload either schedule (swap the label)
launchctl list | grep ablo-marketing-os
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.alejo.ablo-marketing-os.weekly.plist
launchctl bootout  gui/$(id -u) ~/Library/LaunchAgents/com.alejo.ablo-marketing-os.weekly.plist
```

> **Note on `.refresh.log`:** the repo-local `.refresh.log` (and `.launchd.*.log`)
> are **retired**. They stopped updating on 2026-06-02 when the launchd entrypoint
> moved to `~/.local/bin/` during the migration off the `alejoras` GitHub account —
> which is why their last lines still show pushes to `alejoras`. The live logs are
> the two `~/.local/log/` files in the table above. (Agent `#1`'s plist label still
> says `weekly` for historical reasons; its `StartCalendarInterval` has no `Weekday`
> key, so it fires daily.)

## Live PostHog experiments

`build.py` pulls experiments **live** via the PostHog REST API using
`POSTHOG_PERSONAL_API_KEY` from `~/.claude/.env` (the key has the `experiment:read` /
`feature_flag:read` scopes). If a pull fails or the scopes are ever revoked, the
Experiments tab degrades to an accurate **cached snapshot**, labeled as such in the UI —
the same graceful-degradation pattern every live source uses.

## Publishing (GitHub Pages)

Static site, no build step. Files that ship: `index.html`, `data.js`, `assets/`,
`robots.txt`, `.nojekyll`. Repo is private; Pages serves the built site.

```bash
git add -A && git commit -m "update" && git push origin main
```

GitHub Pages caveat: on a private repo the Pages **site URL** is still public unless you
are on GitHub Enterprise with access control. The repo source stays private, the page is
`noindex`, and no personal/HR data is included. For stricter gating, put the page behind
Cloudflare Access or a similar auth proxy.

## Files

| File | Role |
|---|---|
| `index.html` | The app: CSS + render logic (self-contained) |
| `content.json` | Curated strategy (human-edited) |
| `data.js` | Generated. `window.ABLO_OS`. Do not hand-edit. |
| `history.jsonl` | Generated. Append-only daily time-series (one row per UTC day). Committed each refresh. |
| `build.py` | Generator: content.json + live PostHog/Klaviyo/autopilot → data.js + history.jsonl |
| `gen_sections.py` | Seeds the curated funnel/lifecycle/channels/command-center fallbacks |
| `gen_battlecard.py` | Imports the competitive battlecard workbook into content.json |
| `gen_connect.py` | Seeds Command Center ladders, objectives, and the Content Calendar |
| `refresh.sh` | Refresh wrapper (build + commit + push) |
| `assets/` | Logo |

The `gen_*.py` scripts are **standalone** one-shot seeders — none are imported by `build.py`. Run them by hand when you need to (re)seed a section; the daily pipeline is just `build.py`.

## The self-improving routine (two layers)

The Command Center keeps itself honest in two layers, so a hand-written status can never
quietly drift from reality (the failure that used to make the queue untrustworthy):

1. **Deterministic reconciler (always on, every build).** `reconcile_queue()` in `build.py`
   cross-checks each curated item against the live signals the same build already pulled, the
   before/after experiment results, the autopilot's delivery status, and matching ClickUp
   tasks (open or closed). Items opt in with a `verify` block in `content.json`
   (`{signal, clickup, doneWhen}`). It attaches a non-destructive `live` overlay
   (`verdict`, `evidence`, `disagree`) that the dashboard renders as a "live check" badge,
   flagging any card whose written status disagrees with the live truth. No LLM, no network
   beyond the pulls already done, runs daily.
2. **LLM reasoning pass (`marketing-os-refresh` skill).** Reads the whole picture and re-ranks
   the queue by KPI impact, rewrites item bodies, and proposes the next action toward the goal
   (first paying customer, CAC < $300). Ranking stays human-owned; this pass proposes, you ship.

The reconciler is the cheap guardrail between the heavier reasoning passes. To add a new
self-verifying item, give it a `verify` block; to add a new signal, extend the `signals` dict
in `reconcile_queue()`.

## Source of truth

Curated content is distilled from the marketing strategy spine and the MVC in
`Brain/projects/ablo/Ablo Studio/`. When the strategy there changes materially, update
`content.json` to match. Personal, HR, and non-marketing content is intentionally excluded.

# Ablo Studio Marketing OS

**An AI-run marketing control center for Ablo Studio.** One page, fed by a local pipeline, that holds the whole operating picture (funnel, lifecycle, channels, experiments, campaigns) and acts on it. The team and the team's agents always work from the same canon.

Live at `alex-runner.github.io/ablo-marketing-os` (internal, `noindex`).

## The one number it ranks against

Everything in the OS is scored against the same goal: **first paying customers**. The hard targets are CAC under $300, signup-to-paid at 8% or better, and the first paying customer by end of June. Every action card names the KPI it moves, so "priority" always means "goal impact," never opinion.

## How it is built

A static GitHub Pages dashboard fed by a local pipeline. No backend, nothing to break.

```
content.json (curated)  ─┐
                          ├─► build.py (merges live data) ─► data.js ─► index.html
live sources             ─┘
```

`content.json` is the human-edited strategy (positioning, ICP, voice, goals). `build.py` pulls live data and writes `data.js`, which the page renders. Every live source has a curated fallback, so if a pull fails the site still shows the last good snapshot instead of breaking.

**Live sources:** PostHog (funnel, UTM channels, experiments), Meta Ads (spend, CPL, signups via the autopilot), Klaviyo (lifecycle emails), ClickUp (the task feed), plus LinkedIn and Instagram.

## What runs it: three schedulers and one manual writer

All four feed one git repo that auto-deploys through GitHub Pages.

| Runner | Cadence | What it does |
|---|---|---|
| Ads Autopilot | every 12h | Manages Meta ad budgets deterministically, then a Claude analyst pass reads the funnel. Feeds ad data into the OS. |
| Data refresh | daily, 09:00 | `build.py` pulls every live source and regenerates `data.js`. |
| The Brain | Mon-Fri, 09:20 | A headless Claude pass re-ranks the action queue and records lessons. Gated by QA and a secret-scan before it can deploy. |
| Manual playbook | by hand | The `marketing-os-refresh` skill, run when a human wants to drive the queue directly. |

## The Command Center

The surface the agent owns. A ranked action queue that ties each funnel leak to its one fix, anchored to the KPIs. Read the funnel, campaigns, experiments, and lifecycle; re-rank by leverage; write back. This is what a teammate (or Josh) opens to see "what should we do next, and why."

## The self-improving loop

The OS does not just report, it learns. Every fix or experiment is logged as a falsifiable prediction in `state/lessons.jsonl`: **predict, observe, score, distill into a lesson, read first next run.** Resolved bets become durable lessons; a running hit-rate keeps the agent honest about how often it is right. Over time the queue gets smarter instead of just busier.

## The Coverage Reconciler

A deterministic layer that catches its own blind spots. Each build enumerates the live marketing surface (events, channels, ClickUp-tagged experiments) and diffs it against a registry of what the OS already models. Anything unmodeled (a new event cluster, a fresh experiment) gets flagged automatically instead of staying invisible. Detection is deterministic by design; the LLM only resolves what to do about a flagged gap, so the catch never depends on a model noticing.

## How it extends

The OS is built to generalize. Every future product or project gets its **own** Marketing OS instance, plus an AI CMO to run it, and optionally a Paperclip agent team as the hands. One pattern, many businesses.

## Where it fits with Josh's pipeline

Josh's automation runs **idea generation, then filtering, then business creation.** The Marketing OS is the distribution and go-to-market brain that takes over the moment a business exists: it runs the marketing and measures it. The full chain becomes:

**idea → filter → build → (Marketing OS) distribute and grow.**

Josh's pipeline decides *what* to build. The Marketing OS makes it *find customers*.

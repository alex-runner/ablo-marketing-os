# Marketing OS — refresh log

Narrative journal of each daily run: what moved, what concluded, what was added,
what's proposed next. The *structured* memory (scoreable predictions + durable
lessons) lives in `lessons.jsonl`; this file is the human-readable companion.

Newest entries on top.

---

## 2026-06-04 — top-of-funnel CRO wired in, first run that proposes a page bet
- Shipped earlier today: `build.py` `fetch_landing_pages` (live `live.landingPages`), reclassified land→engage med→high, Command Center #5 "Win the homepage + paid landing pages (CRO)", SKILL.md step 2b "Question the frame" + `mkt1-homepage-positioning`, Funnel read-agent contract reads landingPages. Then surfaced landingPages in the Funnel tab UI ("Where they land · per-page conversion"). Also persisted `home_engage_pct`/`home_signup_pct` to history so the leak is trendable + the bet scoreable.
- Run result (the QA of the whole change): the Funnel read-agent independently named land→engage the biggest leak (78% of 855 bounce) and returned a concrete page-level CRO hypothesis (rebuild /toddler to match /plus-size, UTM-tagged) — step 2b works end to end. Campaigns agent independently confirmed it: paid Swim converts 4% on its landing despite the best CPL ($2.22), and /toddler 2.2% vs /plus-size 6.8% proves the page, not the ad, is the lever.
- Moved: enriched CC #5 with the live proof; added the hero-rebuild test as roadmap #1 (escalate: needs Product to build the variant, not auto-launchable). Opened PRED-2026-06-04-homepage-cro (home_signup_pct 6.7→8.0, due 2026-07-19, conditional on ship).
- Concluded nothing new (coachmarks PH-374260 still underpowered, hold). Measurement flags: purchase_completed still unproven (0 paying); a before/after display inconsistency on the signup ship (+4.3pp live-window vs +11pp peak) noted, not a regression.
- QA pressure-test (3 skeptics: numbers/calls/boundary). Boundary: PASS (every change staged + reversible, no live experiment/flow/budget/product fired). Numbers: caught hand-carried figures (537/854) drifted from live data.js (540/855) and a denominator mix; fixed across CC #5, the prediction, and this log. Calls: caught (a) the prediction's 60d-trailing metric would score a mid-window ship as a dilution-miss — re-plumbed to score on the hero_v2 UTM cohort; (b) ranking a Product-blocked test roadmap #1 overstates near-term win-prob — moved the launchable-today Activate flow to #1, CRO hero to #2 (win-prob low/blocked). CRO at CC #5 and the no-thrash discipline were upheld. 3 qa-tagged lessons written forward.
- Proposes next: Alejo/Product builds the /toddler + homepage hero variant so the CRO bet can launch and score; meanwhile price-ask test (#1) and purchase_completed verification (#2) remain the direct path to the first paying customer.

## 2026-06-03 — first supervised reasoning run (orchestrator + read-agents)
- Ran the restructured routine: 3 read-agents (Experiments, Campaigns, Lifecycle) dispatched in parallel, Funnel reused; synthesis on their compact JSON returns (each read ~50-90k tokens out-of-context).
- Moved: signup-modal fix held at 42% (44% peak). Confirmed the activation gap (signup→model 69%) as the #1 leak, rage-click cluster on /studio.
- Concluded nothing (coachmarks PH-374260 underpowered at 6/7 exposures, left running). Caught: purchase_completed still not firing, so signup→paid unreadable; un-marked rank 5 "done".
- Re-ranked Command Center: price-ask test to #1 (most direct path to first paying customer), lifecycle wiring #2, activation gap #3, purchase_completed verify #4. Opened PRED-2026-06-03-activate-flow (activation_rate 69→75, due 2026-06-24).
- Proposes next: Alejo starts the price-ask test, wire the Activate flow, run a test purchase to verify purchase_completed fires.

## 2026-06-03 — self-improvement loop wired
- Added `state/lessons.jsonl`: append-only predict→score→learn ledger, read first / written last each run.
- `build.py` now surfaces it as `window.ABLO_OS.live.learning` (lessons, openPredictions, dueForReview, calibration).
- Seeded with the resolved Google-signup bet (33%→44%, hit) + 2 durable lessons. Calibration: 1/1 hits so far (thin, n=1).
- Next: every run logs a falsifiable prediction per fix/experiment and resolves matured bets against `history.jsonl`.

## 2026-06-04 (focused re-run)
- Coverage blind spots 4 -> 1. Dismissed HubSpot-verify task 86baa3y5b (ops/measurement check, not a marketing surface). Wired Day Mode (light-theme) A/B from ClickUp 86baa3ykz as OS-DAYMODE stub (discovered, NOT launched -- launching escalates).
- /try decision surfaced: homepage / = 7.4% signup (42/568) vs /try = 1.5% (1/68, thin). Recommend routing paid to the homepage and pausing /try until fixed/powered (escalated to Alejo, folded into Command Center #5). tbs_* (91 users, 13 events) left escalated pending kill/fix call -- not bulk-dismissed.
- Logged LES-2026-06-04-try-landing (confidence med; /try arm under-powered). No experiment launched, no Meta change executed.

## 2026-06-04 (correction: /try measurement)
- Investigated whether /try's 1.5% was a tracking error (Alejo's question). CONFIRMED a measurement bug: landingPages keys signup_completed to first-pageview pathname=/try, which captures only 2 of 24 real signup-wall reaches and mis-credits 3 of 4 /try signups to other entry pages.
- True /try funnel (tbs_* taxonomy): 91 viewed -> 54 category -> 25 generate -> 24 wall -> 4 signed = 4.4% view->signup (16.7% wall->signup), not 1.5%. Signup events fire correctly; attribution is the bug.
- Corrected CC#5 and superseded LES-2026-06-04-try-landing with LES-2026-06-04-try-mismeasure. Held the 'route paid off /try' recommendation. Code fix (measure /try via tbs_) proposed, not yet applied.

## 2026-06-04 (fix shipped: /try measurement)
- Implemented the /try measurement fix in build.py: new _correct_try_row() re-measures /try by its tbs_* cohort reach (per-event distinct, not intersected on the entry person-set, which fragmentation was collapsing to generate=5). landingPages /try now reads 91 viewed -> 25 generate -> 24 wall -> 4 signed = 4.4% (was a fake 1.5%); homepage unchanged at 7.4%.
- Hardened: monotonic clamp on the funnel, graceful degrade if the tbs_ pull fails, dropped the noisy 'customize' union step. Lesson LES-2026-06-04-anon-funnel-reach recorded. ClickUp 86ba2wp4t resolved by this change.

- [2026-06-08] Ad ops: repointed Kids paid ad (120248623833700414) /toddler -> /try-kids via twin creative 1313242573665691 (same adset/budget). Kids = top-spend segment on the worse page (2.9% vs 10%). PENDING_REVIEW at change time. Caveat: lp_test UTMs now on this traffic. Revert: creative 2450333338727221.

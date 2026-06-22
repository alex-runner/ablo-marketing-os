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

## 2026-06-10 — pre-call reasoning run (orchestrator + 4 read-agents + 2 QA skeptics)
- Moved: both A/Bs closed. OS-TRY-VS-HOME retired with /try as the defensible paid default (NOT a powered win, attribution methods differ across arms); PH-374260 coachmarks ended in PostHog Jun 9 inconclusive (32/41 exposures), flag at 100%, end state observed not set by this run. Modal fix holding at 43.6% last-7d, magic-link at 0/day.
- Lifecycle milestone: all 3 Klaviyo flows live (Activate May 19, AHA Jun 5, Convert Jun 6); rank "wire lifecycle emails" resolved, residual gap (Convert paid-exit Subscription Started, Jason) folded into rank 2 with purchase_completed verification.
- Re-ranked CC: 1 price-ask test (20 days left), 2 paid-conversion visibility (two blind events), 3 aha→paid leak (54 aha → 10 checkouts → 0 paid, post-tryon prompt proposal for Jason), 4 activation gap (40.7% daily-sum last-7d, mix hypothesis, UTM split is the next action), 5 Meta health (CPL $8.61 fine, 24h ~$23.6 spike, Kids pixel under-firing), 6 CRO (/try default, hero blocked), 7 modal watch.
- Held by QA: PRED-2026-06-10-try-paid-default (flight-cumulative cpl violates LES-2026-06-04-qa-rolling-metric, rollout premise overstated, autopilot confound). Re-log once a clean per-cohort metric exists in history.jsonl.
- QA (2 skeptics, both "revise", revisions applied): stale Jun-8 figures replaced with live (try-kids 8.6 vs toddler 3.9), denominator splices fixed (pricing 11 lifetime not 9/54), unverifiable ad-set claims removed, try-value-first lesson downgraded to low. 4 qa lessons written. REPEAT CATCH of LES-2026-06-04-qa-figures (hand-carried numbers): queue SKILL.md hardening in the monthly audit.
- Proposes next: Alejo starts the price-ask test (20 days); run the sandbox purchase + Stripe cross-check (CC 2); write the post-tryon prompt proposal for Jason (CC 3); UTM activation split (CC 4).

## 2026-06-11 — daily run

- **Moved:** Modal completion d7 at 52.8% (56/106) -- EXCEEDS the 50% PRED-2026-06-04-remove-magic-link target. Likely HIT when scored Jun 18. AHA flow early signal: 7 recipients, 28.6% open rate.
- **Flagged:** PRED-2026-06-03-activate-flow is a directional miss -- activation 54% rolling spine is BELOW the 69% baseline (not just below 75% target). UTM split needed to diagnose: mix-shift vs product regression. Added to roadmap as a diagnostic.
- **Flagged:** Kids pixel likely not firing on /try-kids post-Jun-8 creative swap (unaudited live-read, not persisted). $16/day Kids spend potentially running blind. Needs 24h verification via Meta Pixel Helper.
- **CC updates:** Rank 4 body rewritten with directional-miss flag and UTM split urgency. Rank 5 status updated with pixel caveat. Rank 8 status updated with 52.8% d7 figure and likely-hit note for PRED.
- **QA (2 skeptics): revise.** 3 figure corrections applied (Kids spend $16 not $12; 7d CPL $7.71 not $11.06; Swim CPL $0.51 removed as unverifiable). PRED magic-link correction: d7 rate exceeds target (was cited as below). Rank order upheld after review (activation stays rank 4, /try category stays rank 6). 5 qa lessons written.
- **Proposes next:** (1) Alejo: start the price-ask test (19 days to end-June); (2) run UTM split in PostHog to diagnose activation decline (2-day action); (3) verify Kids pixel on /try-kids via Meta Pixel Helper within 24h; (4) Jason: Subscription Started exit event for Convert flow + purchase_completed verification.

## 2026-06-11 — autonomous fix session (post-routine)
- Investigated the 3 "needs attention" items directly in code + PostHog. Two were NOT bugs:
  - **Kids pixel:** /try-kids tracks fine — PostHog recorded 122 paid pageviews/101 people in 14d. Meta "0 PageViews" is ad-block asymmetry, not a code bug. CANCELLED the "revert creative" action. Real fix = server-side CAPI (Jason, de-prioritised).
  - **Activation decline:** CONFIRMED mix-shift via PostHog activation-by-channel (paid 44% vs direct 66%, 30d; paid share rose 50→73%). Not a product regression. Fix = traffic quality + the live Activate flow.
  - **purchase_completed:** wiring verified correct end-to-end (success_url → AccountPage track, keyed to user.id). 0 fires ≈ 0 real purchases; confirm in Stripe. Robustness fix = server-side webhook capture (Jason).
- Wrote state/diagnostics-2026-06-11.md (full evidence). Updated CC ranks 2/4/5. 3 diagnosis lessons appended.
- ClickUp: commented diagnosis on 86ba9kmjg (pixel) and 86ba9kmj6 (purchase verify).
- Net: 3 fire-drills de-escalated to their true scope. Remaining real work all needs a person: price-ask test (Alejo), CAPI + server-side purchase event + Convert paid-exit (Jason), paid targeting tightening (Alejo).

## 2026-06-15 — Monday run (daily + weekly coherence audit)
- **NEW headline: Meta ads are DARK.** $0 spend + 0 impressions on all 4 segments for 3+ days (Jun 13-15); the $8.33 CPL is a frozen lifetime average, not live. Added high-sev CC rank 3 "Relight Meta delivery", ESCALATED to Alejo (money action, not auto-fired). LES-2026-06-15-meta-dark.
- Re-ranked: 1 price-ask, 2 purchase-visibility, 3 relight-Meta (NEW), 4 aha→paid (+ NEW AHA-CTA rework: opens 33-36% but 0 clicks), 5 activation gap, 6 /try category, 7 CRO, 8 modal-hold.
- Activation slide 57→52 reframed per QA: confounded by channel mix-shift; the Jun-12 create-a-model overhaul has no clean before/after and is too thin to read — impact UNMEASURABLE, not failed. Queued an OS-CREATE-MODEL binding on the roadmap.
- Predictions: 0 due, 0 resolved. PRED-2026-06-04-remove-magic-link (due Jun 18) flagged likely-miss (completion stuck ~44%, not climbing to 50) — resolve Jun 18, not early. No new prediction logged (thin calibration n=1; no clean before-window). Price-ask is the clean bet to log WHEN it ships.
- QA (2 skeptics): numbers=revise (caught 41/43 metric mislabel + payment_rate 10→6/checkout-window errors, both corrected); calls=valid logic but read the wrong workspace (MCP graph, not data.js) — boundary upheld (escalate Meta relight). 5 qa lessons written, incl. a process fix to pin QA sources to the files.
- Weekly coherence: the 3 most direct paths to the end-June goal are all stalled — price-ask not started, purchase_completed uninstrumented, Meta dark. Top of queue is correct; the issue is execution/escalation, not ranking.
- Proposes next: Alejo relights Meta + starts price-ask; verify purchase_completed; I rework the AHA CTA + spec the create-model before/after binding.

## 2026-06-22 — daily run (orchestrator + 4 read-agents + 3 QA skeptics)
- **Top movement:** Campaigns agent VERIFIED via Meta API that ads are healthy ($1,334/30d, $287/7d, $42 yesterday, Swim best at $7.80 CPL / 4.34% CTR). The OS feed is FROZEN at $241.52/29/$8.33 since ~Jun 12 — the autopilot writes fresh files but its 'Lifetime:' line never refreshes. Retracted the false 'ads paused' framing for the 3rd time; root cause is the autopilot's Meta pull (not build.py). CC rank 8 rewritten with the true numbers + escalated as an engineering fix.
- **Re-ranked** by leverage toward first-paying-customer in 8 days: 1 make-paid-visible/check-Stripe, 2 Convert C2-C5 CTA rework, 3 checkout outreach, 4 activation/model-pick, 5 AHA CTA rework, 6 value-capture, 7 /try garment→generate (~47%), 8 stale Meta feed, 9 /try category (37%), 10 modal-hold, 11 CRO. Bottom-funnel/lifecycle levers ranked above slower product-owned activation for the 8-day sprint.
- **Concluded/diagnosed:** activation 49% (spine 85/173) — clean signal is the onboarding model-pick collapse (79% finish Q3, 33% pick a model, but 97% of pickers generate); the 69→35 before/after stays discounted as mix-shift-confounded (paid 44% vs direct 66%). PH-374260 coachmarks confirmed ENDED Jun 9 inconclusive — no live A/B occupies any surface now.
- **Predictions:** 0 due for review (none matured), 0 resolved. 1 opened — PRED-2026-06-22-cta-rework (email_click 0→5, due Jul 6, moot if unshipped) for the Convert+AHA CTA reworks, logged at decision time per QA. Calibration unchanged 0.33 (n=3).
- **QA (3 skeptics): revise → fixed.** Numbers caught that the /try 46%/39% leaks ARE in today's data.js (live.meta.funnelSuggestions), not stale — corrected ranks 7 & 9 to current Jun-22 numbers (622→230→198→105). Calls flagged the Convert lever was unbet — logged the PRED. Calls also disputed the '10 checkout-starters' as '7'; ground-truth check upheld 10 (spine); the 7 was a stale d30 figure. Boundary: PASS, no irreversible/user-visible action auto-applied (CTA reworks staged 'Claude draft / Alejo ship', live flows unchanged). 3 qa lessons written.
- **Content calendar:** stale scaffold (last touched Jun 3, nothing scheduled past Jun 10). Noted as a gap; not drafted this run — conversion, not content volume, is the binding constraint on the goal.
- **Proposes next:** (1) Alejo: confirm the 10 checkout-starters in Stripe — do we already have customer #1 hidden behind the ad-blockable client-side event? (2) Alejo/Claude: ship the Convert C2-C5 + AHA B1/B2 CTA reworks (drafts ready, escalate-gated). (3) Engineering: fix the autopilot's frozen Meta 'Lifetime:' pull or add a build.py direct-API fallback. (4) Jason: Subscription Started paid-exit + server-side purchase capture.

## 2026-06-22 (follow-up) — fixed the stale Meta feed at the root
- Diagnosed: the feed was NOT frozen/broken. The autopilot's lifetime pull (lib/meta.py, run_cycle.py) was hardcoded to one CAMPAIGN_ID ($241.52/29) while Ablo spend had moved to 2 other Ablo campaigns (paused May-20 original $512/25; Jun-3 LP-test $460/52 ACTIVE). True lifetime: $1,332.89 / 111 signups / $12.01 CPL.
- Fix (read-only reporting, no change to what the autopilot ACTS on): added meta.ablo_campaign_ids() (paginates the campaign list, name-matches 'Ablo', excludes the 200+ unrelated 'AI .' junk campaigns sharing the ad account) + meta.lifetime_insights_ablo() (date_preset=maximum). run_cycle.py now uses it. Verified via dry-run: LATEST.md regenerated to $1,332.89/111/$12.01, no ad mutations.
- OS rebuilt: feed now reads the true totals. CC rank for the Meta feed marked RESOLVED and moved to done. LES-2026-06-22-meta-feed-rootcause logged (true root cause behind the retracted LES-2026-06-15-meta-dark).

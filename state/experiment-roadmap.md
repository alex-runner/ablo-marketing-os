# Experiment roadmap

Prioritized backlog of candidate experiments. The daily routine (`marketing-os-refresh`,
step 7) picks the **top candidate that does not overlap a live test** (non-overlap rule:
at most one live test per surface, see SKILL.md step 1), launches it, logs a `prediction`,
then re-ranks this list.

Ranking = **leverage** (impact on signup→paid toward the goal) **× win-probability**
(tempered by `calibration`: when the hit rate is low or thin, discount optimistic bets).

Goal everything ranks against: first paying customer by end-of-June, CAC < $300,
signup→paid ≥ 8%.

Updated: 2026-06-03.

## Live now

| id | test | surface | status |
|----|------|---------|--------|
| PH-374260 | Studio onboarding coachmarks | /studio create-model | ENDED in PostHog Jun 9, inconclusive (32/41 exposures, never powered). Flag serving variant at 100%, end state observed not set by the OS. Lesson: LES-2026-06-10-ab-power-floor. |

Surfaces occupied: **/studio**. Free surfaces: homepage/landing pages, email/lifecycle, try-on result screen, pricing.

## Queue (ranked)

| rank | candidate test | surface | funnel leak it targets | Big Bet it ladders to | primary metric | leverage | win-prob | notes |
|------|----------------|---------|------------------------|----------------------|----------------|----------|----------|-------|
| 1 | Activate A1-A3 behavioral flow (24h no-model nudge) | email/lifecycle | activation gap (signup→model 69%) | Lever 2 · Conversion | `activation_rate` | high | med | Launchable now: ship-and-measure as OS before/after, not an A/B (traffic too thin for power). Templates exist, buildable today, no Product eng cycle. = CC rank 3. Bet logged: PRED-2026-06-03-activate-flow (69→75, due 2026-06-24). Escalate: emails real users, so human-gate the turn-on. |
| 2 | Hero rebuild on homepage + /toddler (match /plus-size structure, mkt1-homepage-positioning lens), UTM-tagged hero_v2 vs hero_v1 | homepage / paid landing pages | top-of-funnel bounce (land→engage 22%, land→signup 6.7%) | Lever 1/2 · Convert the visit, lower CAC | `home_signup_pct` | high | low (blocked on Product build) | HIGHEST leverage (biggest leak by volume, 78% of 855 bounce; live proof page is the lever: /toddler 2.2% vs /plus-size 6.8%, paid Swim 4% on landing despite best CPL). Ranked #2 not #1 because near-term win-prob is gated: **needs Product to build the hero variant (user-visible, not auto-launchable)**, so it cannot ship as fast as the launchable-today items. Priority lives in CC rank 5; this row is launch-order. Bet: PRED-2026-06-04-homepage-cro (scored on the hero_v2 UTM cohort, moot if unshipped by 2026-07-19). |
| 3 | Download/share prompt on try-on render | try-on result screen | value-capture (try-on→download 17%) | Lever 2/3 · Activation-to-paid + ARPU | `downloads` | med | med | Non-overlapping with /studio. Ship-and-measure (thin traffic). = CC rank 7. |
| 4 | Coachmarks follow-up (before/after, not A/B) | /studio create-model | activation gap | Lever 2 · Conversion | `activation_rate` | high | tbd | PH-374260 ended inconclusive Jun 9. Per LES-2026-06-10-ab-power-floor, any retest is ship-and-measure (OS-...), not a split. |

## Concluded
_Moved here with the winner + one-line conclusion + linked `PRED-...` once resolved._

- OS-SIGNUP-GOOGLE (signup-modal, Google-primary): **winner**, completion 33%→42% (44% peak), held. PRED-2026-05-20-google-signup resolved hit (+11pp). Lesson LES-2026-05-31-friction.

## Added 2026-06-11

### Activation UTM diagnostic (new — pre-ranked above download/share prompt)
**Action:** Split last-7d signups by utm_source (Direct vs Paid) and compare activation rate per cohort in PostHog. This is a **diagnostic**, not an A/B — no experiment needed. Run via HogQL in PostHog within 2 days.
**Purpose:** Confirm whether the 15pp activation decline (69%→54%) is channel mix-shift (TBS/Paid cohort lower intent) or a product regression. The fix is different in each case: traffic-quality if mix, product if regression.
**No PRED yet:** No persisted metric for channel-split activation rate in history.jsonl. Add a split key once the query runs and confirm the result. Then log the prediction.
**Escalate:** Not a build task — Alejo runs the HogQL query. Results inform whether rank 4 (activation gap) needs a product fix or a traffic-quality fix.

## Added 2026-06-15
### Bind a before/after on the Jun-12 create-a-model overhaul (coverage gap)
The Jun-12 Studio overhaul (2-step coachmarks, swipeable models, pose tuning, mobile fixes) shipped with NO measurement binding. Add an OS-CREATE-MODEL before/after on signup→model (activation), split by channel to control for mix-shift, so we can read whether it lifted activation. Until bound, its effect is unidentifiable (see LES-2026-06-15-qa-confound-vs-fail). Ship-and-measure (not an A/B). Owner: Claude to spec the binding; needs a build.py/tracking change.

## Updated 2026-06-22

**Surfaces now FREE.** PH-374260 (coachmarks) ENDED in PostHog Jun 9, inconclusive — no live A/B occupies /studio or any surface today. All 3 lifecycle flows (Activate, AHA, Convert) are live, so the old rank-1 "Activate flow" queue item is shipped (= CC done). Roadmap re-based on what the data now says.

**No new live experiment launched today.** Reasons: (1) calibration thin (0.33, n=3) — bar is raised, prefer the reversible move; (2) the highest-leverage levers are escalate-gated (live-flow email edits, product changes), not OS-launchable A/Bs; (3) traffic too thin for a powered split. Discipline over a forced launch. Log the PRED when each ships.

**Queue (re-ranked by leverage × win-prob, tempered by calibration):**

| rank | candidate | surface | leak it targets | metric | leverage | win-prob | notes |
|------|-----------|---------|-----------------|--------|----------|---------|-------|
| 1 | Convert C2-C5 paid-ask CTA rework (one action line + direct link) | email/lifecycle | tryon→paid (105 read, 0 click) | email_click / payment_rate | high | med | CC rank 2. Closest-to-money lever. Ship-and-measure before/after (thin traffic). Escalate: edits a live flow. PRED LOGGED Jun 22: PRED-2026-06-22-cta-rework (email_click 0->5, due Jul 6, moot if unshipped) -- covers both #1 and #2 CTA reworks. |
| 2 | AHA B1/B2 CTA rework | email/lifecycle | model→tryon nudge (24 read, 0 click) | email_click | med | med | CC rank 5. Same fix class as #1; batch both copy reworks together. Escalate the live edit. |
| 3 | Post-render download/share prompt on try-on result | try-on result screen | value-capture (26% download) | downloads | med | med | CC rank 6. Product-owned (Jason). Ship-and-measure OS before/after. |
| 4 | Onboarding model-gallery pre-filter (5-8 matches) | /studio onboarding | activation model-pick collapse (33% pick) | activation_rate | high | med | CC rank 4. Already a live bet: PRED-2026-06-19-onboarding-model-filter (49→57, due Jul 3). Product-owned. |
| 5 | Homepage/landing hero rebuild (mkt1-positioning lens, UTM-tagged) | homepage / paid landing | land→engage bounce | home_signup_pct | high | low | CC rank 11. Blocked on Product. PRED-2026-06-04-homepage-cro due Jul 19. |

**Data-integrity blocker (not an experiment, but gates campaign decisions):** the autopilot's Meta 'Lifetime:' line is frozen since ~Jun 12 (CC rank 8). Ads are confirmed healthy via Meta API; the OS just can't see it. Fix = autopilot Meta refresh or a build.py direct-API fallback. Escalate / own as an engineering task.

## Updated 2026-06-24
- **3 predictions resolved, all MISS** (activate-flow 69->50, tbs-category-fix 10.4 unshipped, checkout-outreach 6->5 not executed). Calibration now ~0.17 (n=6). 2 of 3 missed because the action never shipped, not because the hypothesis was wrong (LES-2026-06-24-escalate-gated-calibration).
- **No new experiment launched, no new prediction opened.** Calibration is low/thin -> raise the bar, prefer reversible moves. The top lever (Convert C2-C5 CTA rework, roadmap rank 1) is still UNSHIPPED and is now confirmed a real dead-CTA (121 recipients, windows elapsed, 0 clicks), not a timing artifact. Queue unchanged; the blocker is execution, not the queue.
- Experiments: PH-374260 (coachmarks) data.js binding still says 'Running' but PostHog ended it Jun 9 inconclusive -- stale flag, low-priority hygiene fix.

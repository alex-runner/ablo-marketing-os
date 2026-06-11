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

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
| PH-374260 | Studio onboarding coachmarks | /studio create-model | running, badly underpowered (~6/7 exposures, ~3% of sample). Hold, do not conclude. |

Surfaces occupied: **/studio**. Free surfaces: email/lifecycle, try-on result screen, pricing.

## Queue (ranked)

| rank | candidate test | surface | funnel leak it targets | Big Bet it ladders to | primary metric | leverage | win-prob | notes |
|------|----------------|---------|------------------------|----------------------|----------------|----------|----------|-------|
| 1 | Activate A1-A3 behavioral flow (24h no-model nudge) | email/lifecycle | activation gap (signup→model 69%) | Lever 2 · Conversion | `activation_rate` | high | med | Ship-and-measure as OS before/after, not an A/B (traffic too thin for power). Templates exist, buildable today. = CC rank 2. Bet logged: PRED-2026-06-03-activate-flow (69→75, due 2026-06-24). |
| 2 | Download/share prompt on try-on render | try-on result screen | value-capture (try-on→download 17%) | Lever 2/3 · Activation-to-paid + ARPU | `downloads` | med | med | Non-overlapping with /studio. Ship-and-measure (thin traffic). = CC rank 5. |
| 3 | Conclude coachmarks, ship if it wins | /studio create-model | activation gap | Lever 2 · Conversion | `activation_rate` | high | tbd | Blocked until PH-374260 reaches ~200/variant. Then conclude and, if it wins, roll out + re-measure. |

## Concluded
_Moved here with the winner + one-line conclusion + linked `PRED-...` once resolved._

- OS-SIGNUP-GOOGLE (signup-modal, Google-primary): **winner**, completion 33%→42% (44% peak), held. PRED-2026-05-20-google-signup resolved hit (+11pp). Lesson LES-2026-05-31-friction.

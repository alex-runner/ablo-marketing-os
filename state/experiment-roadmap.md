## 2026-06-29 -- TOP: Paid value-first landing wedge (paid cohort aha->pricing)
- **Leak:** paid converts 11x worse than organic to checkout (1% vs 11%); paid = 57% of signups (CC#2).
- **Big Bet tie:** wedge-first paid acquisition (bodies brands cannot shoot).
- **Hypothesis:** paid users treat try-on as a free novelty because the wedge never reaches them; a value-first paid landing that leads with the wedge lifts paid aha->pricing.
- **Variant:** Kids/Swim paid -> dedicated /try-wedge landing (UTM-cohorted) vs current homepage//try.
- **Primary metric:** paid-cohort aha->pricing_plan_clicked (payment_rate as blended indicator). **Surface:** paid landing (non-overlapping with the coachmarks studio test).
- **PRECONDITIONS (queued, not launched):** (1) paid delivery resumed (idle $0/24h), (2) value-first paid landing built, (3) purchase_completed firing server-side. Do NOT launch on idle traffic.
- **Linked prediction:** PRED-2026-06-29-paid-wedge-gap.


## Updated 2026-07-01
- End-of-June deadline PASSED, 0 paying customers. PRED-2026-06-16-aha-cta-rework resolved MOOT (3rd consecutive moot for an unshipped CTA rework). Calibration 0.17 (n=6, moot excluded).
- No new experiment launched, no new prediction. Calibration low + top levers escalate-gated/product-owned + traffic thin. The queue is not the problem; execution is.
- Campaigns: delivery resumed. Swim is the live paid winner ($4.61 CPL, 15/18 last-7d regs); Kids ran hot ($35 CPL) this window (thin, 1wk). Only 1 Ablo Studio campaign live.
- Standing queue top (all execution-blocked, not launchable by the OS): (1) server-side purchase capture + Stripe check, (2) at-aha in-product price-ask, (3) Convert CTA rework live edit.

## Updated 2026-07-08 (MILESTONE: first paying customer)
- **First paying customer landed 2026-07-02** (organic/direct, Growth ANNUAL, in-app via the aha pricing-prompt, a day after aha; NOT email/paid). Goal hit ~1 week past deadline.
- 3 due predictions all resolved MOOT (try-generate, onboarding-filter, cta-rework -- none shipped). 6 moot / 5 miss / 1 hit total; calibration 0.17 (n=6, moot excluded).
- No new experiment launched, no new prediction. Rationale: the levers are product/escalate-gated and calibration is low; the milestone tells us the PROVEN path is organic + in-app aha conversion, so the queue re-ranked to (1) convert the 11 warm checkout-starters, (2) fix revenue tracking, (3) sharpen the at-aha price-ask (now staged), (4) reverse the activation slide.
- Two artifacts staged this session for shipping: cta-rework-2026-07-01.md (email, downgraded) and at-aha-price-ask-2026-07-08.md (the validated in-app path).
- Data integrity: Meta feed frozen again since 07-03 (autopilot last ran ~Jul 2) -- verify the autopilot cron.

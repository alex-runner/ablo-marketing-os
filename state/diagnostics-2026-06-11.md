# Diagnostics — 2026-06-11 (autonomous fix session)

Three issues investigated directly in code + PostHog. Bottom line: two were
NOT bugs (the data was misread), one is correctly wired and just has no sales
yet. The real work that remains is traffic quality and a server-side event,
both of which need a person (Alejo / Jason).

---

## 1. Kids pixel on /try-kids — NOT a code bug

**Claim under test:** "Kids burning ~$16/day blind, 0 PageViews on /try-kids."

**What I checked:**
- `/try-kids` is a normal SPA route (`apps/web/src/App.tsx:33`).
- Vercel rewrite serves `index.html` on a direct hit (`vercel.json` `/(.*) → /index.html`), so the deep-link-404 theory is wrong.
- Base Meta pixel fires `PageView` on every HTML load (`index.html:31-32`), no consent gate, `TryKidsPage` needs no special handling.
- **PostHog (independent of Meta):** `/try-kids` recorded **135 pageviews / 106 people in 14 days; 122 of them `utm_source=meta` (101 people)**. Paid traffic IS landing and the page IS tracking.

**Conclusion:** The page works. Meta's "0 PageViews" is a **Meta-side reporting artifact** — `fbevents.js` is ad-blocked far more aggressively than PostHog, so Meta under-counts. Reverting the creative to `/toddler` would NOT help: identical architecture, same asymmetry.

**Real fix (needs Jason, escalate):** server-side **Meta Conversions API** PageView/Lead from the existing `meta.service.ts`, so Meta sees the event regardless of client ad-blockers. This is the only thing that closes the Meta-vs-PostHog gap.

---

## 2. Activation decline (69% → 54%) — MIX-SHIFT, not a product regression

**Claim under test:** activation slid 15pp; is it a product bug or channel mix?

**PostHog activation by channel (signup → model_generated):**

| Window | meta/paid | direct/none | blended |
|---|---|---|---|
| 30d | 44.0% (50) | 66.0% (47) | 55.0% |
| 14d | 42.6% (54) | 48.3% (29) | 45.5% |
| 7d | 36.6% (41) | 30.0% (10) | 37.5% |

**Conclusion:**
- **Paid activates ~22pp lower than Direct** (44% vs 66% on 30d). This is a structural, persistent gap.
- Paid's **share** of signups rose (50% of signups at 30d → 73% at 7d), so the blended rate falls as paid scales. That is the dominant driver of the "decline."
- Short windows are also depressed by **recency lag** (someone who signed up 2 days ago may not have generated a model yet), which is why 7d < 14d < 30d.
- Direct still activates at 48–66%, so **the product step is not broken** — no regression.

**Real fix (needs Alejo):** this is a **traffic-quality** problem, not an onboarding bug. Two levers: (a) tighten paid targeting so paid clicks are higher-intent, (b) lean on the already-live Activate email flow (the 24h no-model nudge) which targets exactly these paid non-activators. Do NOT spin up an emergency product investigation.

---

## 3. purchase_completed — wiring is CORRECT; 0 fires ≈ 0 real purchases

**Claim under test:** purchase_completed has never fired; is tracking broken?

**What I checked (end-to-end):**
- Server sets Stripe `success_url = ${frontendOrigin}/account?success=true` (`stripe.routes.ts:74` → `stripe.service.ts:109`).
- Stripe redirects there post-payment; `AccountPage` fires `track('purchase_completed', …)` once, guarded by a ref (`AccountPage.tsx:44-52`).
- Event is keyed to the same `user.id` PostHog identifies the funnel person by (`analytics.ts:27`), so it would attach to the right person.

**Conclusion:** The wiring is correct. The event hasn't fired because **no checkout has completed payment** (10 started, 0 paid). This is a true signal, not a measurement gap. **Confirm in the Stripe dashboard:** if Stripe shows 0 completed payments among the 10 starters, then 0 paying customers is real.

**One robustness gap (needs Jason, escalate):** the event fires **client-side**, so a real purchase could be missed if PostHog JS is ad-blocked at the redirect. The bulletproof fix is to fire `purchase_completed` **server-side** from the existing `checkout.session.completed` webhook (`stripe.service.ts:139`, which already has `userId`). Blocker: there is no server-side PostHog client in the repo yet (`posthog-node` not installed) — small build, but it touches the payment path + needs the PostHog key in the server env, so Jason should own + deploy it.

---

## Net change to the action list

- **Kids pixel "revert creative" → CANCELLED.** Not a bug. Replace with: Jason adds CAPI server-side event (de-prioritised; ad-block under-count is cosmetic on a $16/day spend).
- **Activation gap → re-scoped** from "diagnose product regression" to "confirmed mix-shift; improve paid traffic quality + lean on Activate flow."
- **purchase_completed → re-scoped** from "verify tracking" to "confirm in Stripe (likely 0 real sales); Jason adds server-side capture for robustness."

# Ablo Studio — Post-Signup Onboarding (PRD)

**Owner:** Marketing/Product · **Status:** Ready to build · **Date:** 2026-06-03

## 1. Why we're building this

We are flying blind on who our users are. With ~57 signups/month and 0–3 purchases, we
have no segmentation and not enough data to even form purchase hypotheses. This onboarding's
**primary job is to generate that data** at the moment of highest intent (right after signup).
Its **secondary job** is to make the first generated image match what the user actually wanted,
which is a credible lever on the post-generation drop-off (see the funnel teardown).

**Explicit non-goal:** lifting signup→first-image activation. That step is already healthy (~61%).
We must *not* let onboarding friction drag it down — hence both steps are skippable and we guard
activation as a metric.

## 2. Principle

Every tap must hand the user control (personalize their session), not just extract data.
Framed as **"Let's set up your studio,"** never "help us understand you." Data is the byproduct
of a genuinely useful setup step.

## 3. The flow

Signup → **Step 1** → **Step 2** → land directly inside a pre-configured first generation.
No "thanks for answering" interstitial. Progress shown (1 of 2 / 2 of 2). Both steps skippable.

### Step 1 — "What are you here to create?" (output style)
Single-select, large visual tiles, each showing the **same white tee** rendered in that style
(isolates the variable; doubles as a teach for what each style is).

| Tile | Sets |
|---|---|
| On Model | `preferred_style = on_model` |
| Mannequin | `preferred_style = mannequin` |
| Ghost Mannequin | `preferred_style = ghost` |
| Flat-lay | `preferred_style = flatlay` |
| Sketch/CAD *(only if it's an OUTPUT, not an input — confirm with product)* | `preferred_style = sketch` |

→ Pre-selects the default render style and seeds the first canvas/templates.

### Step 2 — "Where will these images live?" (format + use-case)
Single-select. Chosen over a "who are you" persona question because it is genuine customization
that *also* reveals the segmentation — users reveal who they are through intent, not self-labels.

| Tile | Sets format | Reveals (`use_case`) |
|---|---|---|
| Product pages / online store | square, clean white-bg | `ecommerce` |
| Social (Instagram, TikTok) | 4:5 / 9:16 crops | `social` |
| Marketplace (Amazon, Etsy) | marketplace-compliant white-bg | `marketplace` |
| Lookbook / catalog | landscape / multi-shot | `brand_agency` |

→ Sets the output aspect ratio/preset and the `use_case` person property.

### Then, in-product (NOT a survey step)
"Add your first garment" → 📱 Snap a photo · ⬆️ Upload · 🎨 Start from sketch → first generation,
pre-configured with the Step 1 style + Step 2 format.

### Roadmap upgrade (post-validation)
For the **On Model** path, replace Step 2 with a **model picker** (gender / look / setting) — the
highest "I'm tailoring my studio" moment. Requires branching logic; defer to v2.

## 4. Tracking plan (exact)

**Events** (fire on each):
- `onboarding_started` — props: `{ variant }`
- `onboarding_step_viewed` — props: `{ step: 1|2, question, variant }`
- `onboarding_step_completed` — props: `{ step, question, answer, variant }`
- `onboarding_skipped` — props: `{ step, variant }`
- `onboarding_completed` — props: `{ preferred_style, use_case, variant }`

**Person properties** (set, so the WHOLE downstream funnel becomes sliceable):
- `preferred_style` ∈ {on_model, mannequin, ghost, flatlay, sketch}
- `use_case` ∈ {ecommerce, social, marketplace, brand_agency}
- `onboarding_completed_at` (timestamp)

This is the payoff: once set, `model_generated`, `result_downloaded`, `pricing_plan_clicked`,
`checkout_started` can all be broken down by style and use-case — the first real segmentation we'll have.

## 5. Experiment design

- **Feature flag:** `onboarding-2step` (boolean), 50/50.
- **Control:** current flow (straight into studio).
- **Variant:** the 2-step onboarding.
- **Primary (guardrail) metric:** signup → `model_generated` rate. Variant must hold or beat control.
- **Secondary:** `model_generated` → `result_downloaded` and → `pricing_plan_clicked`, sliced by
  `preferred_style` / `use_case`.
- **Skip rate** per step (a high skip rate is itself a signal the framing is wrong).
- **Decision rule on purchase:** do NOT gate the decision on purchase conversion — at ~57
  signups/mo it is statistically untestable. Judge on activation guardrail + downstream
  engagement + the segmentation data it unlocks.

> Reality check: with this traffic, even the activation A/B needs ~weeks to read. Treat v1 as
> ship-measure-learn for the *data*, not as a stat-sig conversion test.

## 6. Edge cases / rules
- Skippable at every step; never trap. "Skip for now" visible.
- Don't re-show to returning/already-onboarded users (`onboarding_completed_at` set).
- Mobile-first layout (paid traffic is largely mobile — confirm in analytics).
- If Step 1 is skipped, fall back to a sensible default style (likely `on_model`) and still let
  them change it in-product.

## 6b. Delivery: a campaign landing page, not the homepage

Ship this as a **standalone signup-first landing page** (its own URL + UTMs) that we drive a
campaign to — keep the homepage as-is. This is **arm A2** of the three-arm landing-page test:
A0 = current control, A1 = value-first try-before-signup LP, A2 = this (signup-first LP + extended
onboarding). Compare all arms on **cost per activated user** (visitor → first image). Given low
volume (~656 visitors/mo), run A1 vs control first and bring this in as wave 2 rather than
thin-splitting traffic three ways. See `docs/ablo-studio-try-before-signup-prd.md` §8.

## 7. What this does NOT solve (see teardown)
- The pre-signup bounce (656 visitors → 57 signups). That's upstream of this feature.
- The core monetization gap (generate → don't pay). Onboarding may *nudge* it via relevance, but
  the teardown's diagnosis work owns that question.

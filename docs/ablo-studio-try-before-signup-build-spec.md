# Try-Before-Signup — Engineering Build Spec (grounded in ablo-tech)

**For:** the A1 value-first landing page. Read alongside `ablo-studio-try-before-signup-prd.md`.
**Repo:** `denizozzgur/ablo-tech` (local: `~/Documents/Claude/ablo-tech`).
**Headline:** ~70% of this already exists. The only net-new capability is an **anonymous trial
generation with a gated result**. Everything else is reuse + assembly.

## 1. What already exists (reuse, don't rebuild)

| Capability | Where | Use for |
|---|---|---|
| Niche landing pages | `apps/web/src/pages/PlusSizeLandingPage.tsx`, `ToddlerLandingPage.tsx` | Template for the A1 LP; clone the pattern per niche. |
| 3-step studio flow (Model → Product → TryOn) | `apps/web/src/pages/StudioPage.tsx` | The flow our LP mirrors. Studio is already reachable anonymously (`studio_entered` fires pre-auth). |
| "Pick a seed model" (pre-generated models) | `ModelBuilder.tsx` (`seedModelRef`, event `seed_model_selected`) | This **is** our category-model picker. Feed it the new men/women/toddler/plus-size pre-gens (prompts in `ablo-tech/photos/category-model-prompts.md`). |
| Model attribute enums | `packages/shared/src/constants/enums.ts` (`MODEL_RACE/GENDER/HAIR/SIZE`) | Category → attribute mapping for the seed models. |
| Prompt builder | `apps/server/src/utils/promptBuilder.ts` + `constants/defaults.ts` | Generates the seed models; no change needed. |
| Product import (URL) + sample products | `components/product/ProductImport.tsx`, `data/defaultProducts.ts` | Step 2 "paste store URL OR try a sample." Sample = `defaultProducts` = the failure-proof default (URL scrape fails ~84%). |
| Credits system | `en.json` credits/* — 50 free credits on signup; model gen = 5 credits, try-on = 5, import = credits | The existing gate. See §2. |
| A/B experiment infra | `lib/useFeatureFlag.ts` (`useFeatureVariant`), live flag `studio-onboarding-coachmarks` | Our `onboarding-2step` flag (PostHog id 701824) plugs into the SAME hook. They already run experiments this way. |
| First-run coachmarks (test arm only) | `ModelBuilder.tsx` `FeatureTips`, gated `coachmarksVariant === 'test'` | Pattern to copy for any test-arm-only UI. |

**They already diagnosed our Leak #2:** code comment in `ModelBuilder.tsx:59` — the blank describe
box "is the main reason ~37% of signups never generate a model," and they shipped animated
placeholder examples + seed models to fix it. Our funnel's 39% signup→generate drop = their 37%.
Confirms the read; means seed-models-first is already their direction.

## 2. The one net-new thing: anonymous trial generation + gated result

**Today's gate is credits, and credits require an account** ("Your account is created on the spot —
50 free credits"). That's why no one can generate before signup.

**The change (the whole experiment):**
1. On the A1 LP, let an anonymous visitor pick a category seed model → add garment (sample or URL) →
   **Generate once**, funded by a single server-granted **anonymous trial credit** (rate-limited per
   IP/device to prevent abuse).
2. Run the real generation. Show the result as a **watermarked / lower-res preview**.
3. **Gate the clean asset:** download / HD / save / "generate another" → signup wall
   ("Sign up to download — 50 free credits"). Existing signup → existing 50-credit grant.
4. On signup, **claim** the already-generated result (re-issue clean (un-watermarked) version) so the
   first thing they see post-signup is *their* image, unlocked.

**Why teaser-first (not gate-on-click):** people sign up to unlock a result they can see far more
than to find out if one exists. A/B the gate placement later; ship teaser-first.

## 3. Instrumentation

- Reuse existing events (`studio_entered`, `seed_model_selected`, `model_generated`,
  `product_imported`, `product_scrape_failed`, `signup_modal_opened`, `signup_completed`).
- Add: `tbs_category_selected`, `tbs_garment_added {source}`, `tbs_generate_clicked`,
  `tbs_preview_shown`, `tbs_signup_wall_shown`.
- Person props on the ANON profile (before signup): `model_category`, `store_url`, `store_domain`,
  `garment_source`, `pre_signup_generated`.
- **⚠️ Anonymous→identified stitching:** on signup, `$identify` MUST merge the anon distinct_id or all
  pre-signup data (and the experiment bucketing) orphans. Verify in PostHog after launch.

## 4. Experiment wiring

- Use `useFeatureVariant('onboarding-2step')` (flag 701824 already exists, inactive). But note: for the
  **landing-page test**, the cleaner split is at the **traffic/URL level** (separate LP routes +
  campaigns), not an in-app flag — see §5. Use the flag only if we serve variants on the same URL.
- Primary guardrail metric: signup→`model_generated` (don't regress). Headline: visitor→signup, and
  visitor→`model_generated` (activated) per arm.

## 5. Campaign routing & attribution

- **Distinct routes** per arm/niche, e.g. `/try` (A1 value-first), niche variants `/try/plus-size`,
  `/try/kids`, `/try/womens`, `/try/mens`; A2 keeps the current signup-first LPs.
- **One Meta campaign/ad-set per LP**, UTMs carried through (the codebase already preserves
  `utm_*`/`fbclid` on landing URLs — seen in session data). Match ad niche → LP niche (curve ad →
  `/try/plus-size` with plus-size seed model pre-selected) to fix the ad↔landing message mismatch.
- **Attribution in PostHog:** break the funnel `$pageview → signup_completed → model_generated` down
  by `$entry_pathname` (or a `landing_variant` person prop set on first touch). The ads autopilot
  (`act_3682177848625068`) splits budget across the routes.
- Volume discipline: ~656 visitors/mo. Run **A1 vs control first**; A2 as wave 2. Don't thin-split.

## 6. Suggested build order
1. Clone a niche LP → new `/try` route, wire the category seed-model picker (reuse `ModelBuilder` seed
   models) + `ProductImport` with sample default.
2. Backend: anonymous trial credit (rate-limited) + watermarked preview render + claim-on-signup.
3. Instrumentation (events, anon person props, identify-stitch).
4. Campaign routes + UTM wiring; PostHog funnel broken down by landing variant.
5. Generate + load the 4 category seed models (prompts already written).

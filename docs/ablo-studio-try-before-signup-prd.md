# Ablo Studio — Try-Before-Signup (PRD)

**Owner:** Marketing/Product · **Status:** Ready to spec into build · **Date:** 2026-06-03
**Priority:** #1 growth experiment (attacks the largest funnel leak).

## 1. Why

The biggest leak in the funnel is pre-signup: **656 studio visitors → 57 signups/mo (91% bounce)**,
and the root cause is **confirmed** — you cannot generate an image before signing up. We charge an
email toll before delivering any value. This flips that: deliver the magic first, ask for the email
at peak intent, and **capture rich segmentation *before* signup** (category + website URL) — earlier
and richer than the post-signup onboarding.

**Three wins in one flow:** value-first (fixes the leak) · data-earlier (category + store URL) ·
signup at peak intent (post-effort, pre-reward).

## 2. The flow (recommended spec)

1. **Land — matched to the ad.** Paid niche → matching pre-selected category (curve ad → plus-size).
2. **Step 1 — "Who are you creating for?"** Big visual tiles of pre-generated models:
   **Men · Women · Toddlers/Kids · Plus-size.** One click. *(captures segment intent — e.g.
   toddler → baby/kids apparel.)* No friction, instant.
3. **Step 2 — "Add a garment."** Two paths, side by side:
   - **"Paste your store URL"** → import products, pick one. *(high-signal identity capture — their
     own domain tells us who they are.)*
   - **"Try a sample garment"** → instant, failure-proof default.
   *(Both offered. URL is the bonus; sample is the guaranteed path — see Risk #2.)*
4. **Generate** → run it and show a **watermarked / lower-res preview** of the result. Deliver the wow.
5. **Signup wall — "Sign up to download / get HD / save."** Gate the *clean asset*, not the preview.
   Peak buying intent → high signup rate.
6. **Post-signup** → drop straight into the studio with their category + garment already set. The
   post-signup onboarding becomes a light style confirmation (we already know category + use-case).

## 3. Key design decisions (and the A/B we'll run on them)

- **Gate placement (the make-or-break).** SPEC = teaser-first: show a watermarked preview, then gate
  download/HD/save. RATIONALE: people sign up to *unlock a result they can see* far more than to
  *find out if one exists*; gating before any output risks a bait-and-switch bounce. ALTERNATIVE
  (worth A/B'ing later): gate on the Generate click, before any render (cheaper compute, signup at
  committed intent). Start with teaser-first; A/B the placement once volume allows.
- **Watermark vs. low-res.** Either works; pick whatever is cheapest to ship that still looks
  desirable. The preview must be good enough to create want, gated enough to need the unlock.

## 4. Data capture (the point)

Set these as person properties on the ANONYMOUS user, before signup:
- `model_category` ∈ {men, women, toddler, plus_size}
- `store_url` (raw) + `store_domain` (parsed) — enrich later (domain → company, industry, size)
- `garment_source` ∈ {store_url, sample}
- `pre_signup_generated` = true once they hit Generate

**Events:** `tbs_category_selected`, `tbs_garment_added` (props: source), `tbs_generate_clicked`,
`tbs_preview_shown`, `tbs_signup_wall_shown`, `signup_completed` (existing).

**⚠️ Instrumentation MUST: anonymous→identified stitching.** Data is captured pre-signup. On signup,
`$identify` must merge the anonymous distinct_id so the category/URL/events attach to the real
person. Without this, all pre-signup data orphans. Verify in PostHog after launch.

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Bait-and-switch bounce** if we gate before showing value | Teaser-first: show watermarked preview, gate the download (§3). |
| **URL scraping fails ~84%** (measured) | Never the only path. "Try a sample garment" is the default; URL is the bonus. Also: fail gracefully (URL fail → auto-offer sample/upload). |
| **Free generation cannibalizes signup** (they get the image and leave) | Gate download/HD/save — the preview alone isn't usable output. |
| **Pre-generated models don't exist yet** | DEPENDENCY: product must produce a small set of high-quality pre-gen models per category. Flag in build ticket. |
| **Signups drop in quality** (more, but worse) | Guardrail metric: do new signups still activate (reach a *post-signup* generation) at the old rate? |

## 6. Measurement

- **Primary:** visitor → signup rate (the leak we're attacking; today ≈ 8.7%).
- **Secondary:** visitor → preview-shown (did they experience value), preview → signup (does the wall
  convert), signup → post-signup activation (quality guardrail).
- **Watch:** pre-signup generations per visitor; % choosing URL vs sample; URL-scrape success rate.
- **Experiment:** A/B the whole flow (control = current signup-first) via a feature flag. At ~656
  visitors/mo this is the highest-volume part of the funnel, so a visitor→signup A/B is the *most*
  readable test we have — far more than anything post-signup.

## 7. Relationship to the post-signup onboarding

This **partially subsumes** the post-signup onboarding's data job (category + store URL captured
earlier and richer). Recommendation: ship this as the primary data + growth vehicle and **slim the
post-signup onboarding** to a style confirmation, to avoid double-asking. Do not build two
overlapping data-capture flows. See `docs/ablo-studio-onboarding-prd.md` and
`docs/ablo-studio-funnel-teardown.md`.

## 8. Delivery & experiment design (landing-page approach)

**Ship as a standalone campaign landing page, NOT the homepage.** Keep the homepage/current funnel
untouched (zero risk to the live flow); build this as a net-new URL we drive paid campaigns to.
Note: despite "landing page," this is a **product surface** — it needs the generation engine,
preview, and signup wall — so it likely lives in the app codebase, not the marketing-site stack.

**Three-arm campaign test** (split at the ad level via separate campaigns/ad sets → distinct LP
URLs + UTMs, so PostHog funnels split cleanly):
- **A0 — Control:** current homepage / signup-first flow.
- **A1 — Value-first LP:** this PRD (try-before-signup).
- **A2 — Onboarding LP:** standard signup-first LP → post-signup extended onboarding
  (`docs/ablo-studio-onboarding-prd.md`).

**Normalized metric across all arms: cost per activated user** (visitor → first image), since the
arms solve different stages and can't be compared on a single mid-funnel number. Underneath, per
arm: visitor→signup, signup→activation, plus data-richness (does A1 capture category + store URL
pre-signup) and downstream desire (download / pricing) as volume allows.

**Sequencing given volume (~656 visitors/mo):** do NOT thin-split three ways at once. Run **A1 vs
A0 first** (biggest leak, most readable metric), then bring **A2** in as wave 2. Expect directional
reads over 4–8 weeks, not fast p<0.05.

**Stack the winners:** value-first entry + post-signup onboarding is likely the eventual combined
flow. Test clean first, combine after.

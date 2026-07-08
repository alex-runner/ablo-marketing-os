# At-aha in-product price-ask + return path — copy/placement spec (2026-07-08)

Staged by the marketing OS (the reversible half). Product build is Jason's; this removes the copywriting + placement decisions so it's a build, not a design exercise.

**Why now:** customer #1 (Jul 2) converted via exactly this path: the pricing prompt shown at the try-on aha, then a return visit 19h later to buy in-app. That is the proven conversion path (not email, click=0; not paid, checkouts concentrate Direct). Sharpen it and add the return hook.

**Where:** the moment the try-on result renders (the aha), and again on the download/export action. Not on a separate pricing page.

## Prompt 1 — at the aha (the instant the try-on renders)
- **Trigger:** first `tryon_completed` in a session.
- **Headline:** This is one look. Your plan is the whole shoot.
- **Sub:** Unlimited models, every size and body, high-res and commercial-ready. No studio.
- **Primary CTA:** See plans → (opens inline plan sheet, not a new page)
- **Secondary (low friction, capture intent):** Keep exploring (dismiss, but set a flag for the return nudge)
- **Do NOT** hard-gate the first try-on. Let them feel the value first; the ask rides the aha, it doesn't block it.

## Prompt 2 — at download/export (value leaving the app)
- **Trigger:** `result_downloaded` or export tap.
- **Headline:** Download the full-res set with a plan.
- **Sub:** This preview is watermarked/low-res. Growth unlocks the originals + commercial rights.
- **Primary CTA:** Unlock downloads ($50/mo)
- Ties the paywall to the exact moment they want the artifact.

## Return path (the payer bought on a RETURN visit, not first session)
- **Persistent project:** their try-on/photoshoot stays saved and is the first thing they see on return. Deep-link it.
- **In-app return banner** (on 2nd+ session if not yet paid): "Your {{ garment }} shoot is ready to finish." → reopen project.
- **Push/web-push** (if permissioned) at ~18-24h: same message. This replaces the dead email nudge (email_click 0).

## Instrumentation to add (blocks measuring any of this)
- Fix `purchase_completed` to log real `amount_usd` (currently 0.0 — CC #2).
- Add `Subscription Started` server-side (real paid-exit; today Convert has no paid exit and can't measure activation→paid).
- Emit `price_prompt_shown` / `price_prompt_clicked` with the surface (aha vs download) so the two prompts can be compared.

## Test binding (when it ships)
Ship-and-measure OS before/after on `payment_rate` (baseline 5) and the aha→pricing-click rate (baseline ~12%). Log the prediction at ship time. Do not A/B (traffic too thin to power).

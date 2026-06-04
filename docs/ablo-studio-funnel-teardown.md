# Ablo Studio — Full Funnel Teardown

**Lens:** marketer + product manager who owns this product.
**Window:** last 30 days (2026-05-04 → 2026-06-03), studio.ablo.ai, test accounts excluded.
**Source:** PostHog project "Ablo Studio" (419152).

---

## TL;DR

We do not have a single conversion problem. We have **a volume problem feeding a desire problem.**
The middle of the funnel (signup → first image) is the *healthiest* part and the only part most
"onboarding" work would touch. The money is lost at the two ends:

1. **91% of studio visitors never sign up** (656 → 57). Biggest leak by raw volume.
2. **Of those who make an image, ~92% never even look at pricing** (35 generate → 3 reach pricing).
   The product creates curiosity, not desire-to-pay.

Everyone who *does* reach pricing starts checkout (3/3, in ~2ms). **The paywall is not the problem.
Getting people to *want* the paywall is.**

---

## The funnel

| Stage | People (30d) | Step conv. | Drop |
|---|---|---|---|
| Visited studio.ablo.ai | 656 | — | — |
| **Signed up** | 57 | **8.7%** | 599 lost |
| **Generated first image** | 35 | **61%** | 22 lost |
| Downloaded a result | ~4 | ~11% | ~31 lost |
| Reached pricing | 3 | ~9% | — |
| Started checkout | 2–3 | ~100% of pricing | — |

Behavioral texture from session recordings: the most *active* sessions in 30 days run **3–33
seconds**, overwhelmingly anonymous visitors arriving on paid Meta links
(`?utm_source=meta…` — niches: womens-swim, curve/plus-size, kids, toddler) and bouncing fast.

---

## Leak #1 — Visitor → Signup (lose ~599 / 91%)  ⟵ biggest by volume

**What I see:** Paid Meta traffic lands on the studio and bounces in seconds. Signups that *do*
happen occur almost instantly (median pageview→signup = 1s), i.e. the people who convert were
pre-sold; everyone else leaves before any value.

**PM/marketer diagnosis:**
1. **We ask for the email before showing the magic. ⟵ CONFIRMED (2026-06-03).** Users *cannot*
   generate an image before signing up. We charge an email toll before delivering any value — the
   classic activation killer. This is almost certainly the primary driver of the 91% pre-signup
   bounce, and matches the 3–33s session lengths on paid traffic.
2. **Ad → landing message mismatch.** Ads are cut by tight apparel niches (swim, curve, kids,
   toddler) but the landing appears generic. Promise/landing congruence is probably weak per-niche.
3. **No instant "wow" on the page.** Nothing demonstrates the output quality before the ask.

**⭐ #1 RECOMMENDED EXPERIMENT (highest business leverage): try-before-signup.** Let a visitor
generate one image *before* the email ask; gate the *download/save/HD* behind signup, not the
*try*. This attacks the single biggest leak (≈599 people/mo) and is a larger lever than anything
inside the post-signup funnel, including the onboarding. Pair with per-niche landing congruence so
the swim ad lands on a swim-led experience.

## Leak #2 — Signup → First image (lose ~22 / 39%)  ⟵ healthiest, leave mostly alone

**What I see:** 61% generate — fine. The 39% who sign up and don't generate likely hit **input
friction**: they need a garment photo or a product URL they don't have to hand.

**Measured (30d):** the product-URL import path fails for ~16 users — roughly **84% of the 19 who
tried URL import hit a scrape failure**. Damage is partly cushioned because users can also upload
(32 imported total), but the URL path is unreliable and is real friction in this zone. *→ Own a
product ticket to harden scraping / fail gracefully into upload.* The onboarding's "Add your first
garment → snap/upload/sketch" step also lowers dependence on a clean product URL.

## Leak #3 — First image → Download → Pay (lose ~32 of 35)  ⟵ the "lovable product" gap

**What I see:** People generate, then mostly don't even download, let alone view pricing. This is
the core of your original question — *why don't they buy* — and the honest answer is **they never
get to the buying question because the first result doesn't create "I need more of this."**

**PM/marketer diagnosis (hypotheses we must disambiguate):**
- **Quality/relevance bar:** the output isn't good enough or isn't the style/use-case they wanted.
  (This is exactly what the onboarding's style + use-case picks attack.)
- **Curiosity satisfied, need not triggered:** one free image scratches the itch; there's no
  "now make the other 12 SKUs" loop, no urgency, no reason to return.
- **Paywall placed before value is proven:** if download is gated, we're asking for money at the
  moment of least-proven value.
- **Measured (30d): 2.69 images per generating user.** Not one-and-done — they *iterate a couple
  times and give up*. That's the signature of "output was close but not what I wanted," which
  favors the **relevance/quality** hypothesis over "curiosity satisfied." Strengthens the case that
  matching first-image-to-intent (onboarding) plus a quality/feedback signal is the right attack.

---

## What we still don't know (and how we'll learn it)

| Gap | Why it matters | How to close |
|---|---|---|
| Who the users even are | No segmentation at all | **The onboarding** (style + use_case person props) |
| Images per user | 1-and-done vs iterating tells us if output was close | PostHog trends: `model_generated` total ÷ unique |
| `product_scrape_failed` rate | Possible silent killer of Leak #2 | PostHog query on that event |
| Is download paywalled? Where's the paywall? | Determines if Leak #3 is value or placement | Product walkthrough + recordings |
| Why visitors bounce pre-signup | Owns Leak #1 | Watch anonymous paid-traffic recordings; can-you-try-before-signup audit |
| Output quality perception | The "lovable" question | A 1-question in-product micro-survey after generation |

---

## Recommended sequence (my call as owner)

1. **Ship the onboarding** (PRD complete). Rationale = unblock segmentation; we cannot make smart
   bets on Leak #3 until we know who's who. It also directly tests the relevance hypothesis.
2. **Diagnose Leak #3** in parallel: watch the generate-but-didn't-pay recordings, pull
   images-per-user, confirm paywall placement, add a 1-question post-generation micro-survey
   ("Was this what you needed? — yes / close / not what I wanted").
3. **Attack Leak #1 (biggest volume):** audit whether value can be experienced before signup; if
   not, prototype "generate one before signup." Tighten per-niche ad→landing congruence with the
   ads work.
4. **Revisit paywall placement** once we know whether Leak #3 is a value or a packaging problem.

**Sequencing logic:** #1 unlocks the data, #2 finds the real cause of the desire gap, #3 fixes the
single biggest volume leak, #4 follows from #2. We deliberately do *not* invest in the
signup→generation zone beyond reducing scrape friction — it isn't broken.

> Caveat held honestly: every number here sits on ~57 signups and 0–3 purchases. Directionally
> strong, statistically thin. The first job of the next month is to grow the denominator and
> instrument the unknowns — not to over-fit to 3 conversions.

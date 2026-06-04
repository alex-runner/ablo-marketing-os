# Price-Ask Test Kit — Ablo Studio

**Owner:** Alejo Escriva, Head of Marketing · **Status:** Ready to run · **Date:** 2026-06-03
**Command Center rank:** 1. The most direct path to the first paying customer.

The brief in one line. Free signups tell us almost nothing about revenue. So we hand-onboard real founders, walk each one to the try-on (the aha), then ask for a card. Whichever segment puts a card down first, at a price that clears CAC and sits clearly above the ~$5 free-tool floor, becomes ICP #1.

**Targets this test moves toward:** first paying customer by end of June, CAC under $300, signup-to-paid at or above 8%, ARPU at or above $50/mo.

**The test design (from `icp.decisiveTest`):** onboard 5 kids founders (start with Agenzia Kids) and 4 to 5 swim / size-inclusive founders (start with Water Vixen Swim). Watch them hit try-on. Ask the four discovery questions and "would you pay, how much." Decision rule below.

---

## 1. Target list

The real signups, grouped by the segment the test cares about. This is who actually showed up (from `icp.realSignups`). It is thin on the two lead segments, which is the gap Alejo has to close.

### Kids & babywear (lead segment, ~40% of focus) — target 5

| Brand | Status | Source |
|---|---|---|
| **Agenzia Kids** | Activated real brand. The named kids account in the OS. **Start here.** | Existing signup |
| _(need 4 more)_ | — | Alejo to supply / source |

**Shortfall: 4 of 5.** We have one named kids brand. The test needs five.

### Swim & size-inclusive (co-lead segment, ~30% of focus) — target 5

| Brand | Status | Source |
|---|---|---|
| **Water Vixen Swim** | Activated real brand, activated twice. The named swim account. **Start here.** | Existing signup |
| _(need 4 more)_ | — | Alejo to supply / source |

**Shortfall: 4 of 5.** We have one named swim brand. The test needs four to five.

### Other real signups (not the two lead segments — use as fallback / cross-read only)

These came in but sit outside the kids and swim wedges. Do not count them toward the 5+5. They are useful as a backstop if a lead-segment slot stays empty, and as a sanity read on whether a non-target founder reacts differently to the price ask.

| Brand | Why it is not a lead-segment target |
|---|---|
| ALYYO | Micro independent brand. General fashion signal, not kids/swim. |
| Naked Slang | Micro independent brand. |
| Zero Core | Micro independent brand. |
| NeevaD London | Micro independent brand. |
| BENI | Couture bridal. Hero-shoot buyer, weak recurrence fit. |
| ElilouCrea | Craft brand. |
| _(freelance fashion photographer)_ | Agency/studio motion (B2B2B), a different sale. Park for later. |

> Geography of the real list: US-heavy, then Italy, Spain, UK, France. Keep the price ask US-first; the unit economics and CAC math are built on the US (LinkedIn US CTR 12.2% vs 3.9 to 5.5% in the EU).

### How to source the rest (do NOT invent contacts)

The named list covers 2 of the 10 slots. The remaining 8 come from two places, in this order:

1. **Alejo's relationships first. ⟵ Alejo must supply these.** Warm intros convert to a 20-minute call far better than cold. Anyone in his network running a small US **kids/babywear** or **swim / size-inclusive women's** brand is a first-call target. _This is the single biggest gap in the kit and only Alejo can fill it._ Mark each warm contact against an empty slot above.

2. **The existing signup base, re-segmented.** The post-signup onboarding (`use_case` / `preferred_style` person properties, see `docs/ablo-studio-onboarding-prd.md`) is being built precisely to reveal who signups are. Until that data lands, pull the signup list from PostHog and eyeball brand names/URLs for kids and swim. Some of the "other" brands above may re-classify on a closer look at their catalog.

**Firmographic to find more of (for paid sourcing or manual prospecting, contact details supplied by Alejo, never fabricated):**
- Buyer: **founder / owner / CEO**, not a marketer.
- Company: small US brand, **2 to 10 employees** (up to 50), Retail Apparel & Fashion or Apparel Manufacturing.
- Kids slot: DTC **babywear / toddler / kids** brand. The tell is a catalog of babies and toddlers (the shoot they cannot cheaply or repeatedly do, the model is the hard part, the product ages out in weeks).
- Swim slot: **swimwear** or **size-inclusive / plus women's** brand. The tell is many SKUs across many body types, the most expensive and logistically painful shoot in fashion.
- De-prioritize: menswear (weakest paid pull), couture/bridal (hero-shoot, low recurrence), pure flat-lay brands (PhotoRoom already serves them at ~$5).

**Where Alejo must act:** every "_(need N more)_" row, and item 1 above. The kit cannot manufacture people. Land at least 3 per segment to make the read meaningful; 5+5 is the goal.

---

## 2. The interview guide

A 20-minute onboarding plus feedback call. The shape: open, walk them to the aha, ask the four discovery questions, then ask for money. Keep it conversational, let them talk, do not pitch over them.

**Before the call:** have their product URL ready so you can import their real catalog live. The test only works if they see **their own product** on a model, not a demo.

### Opener (30 seconds)
> "Thanks for making time. This is not a demo and I'm not going to pitch you. I want to set up Studio on your actual products, watch you use it, and hear what's missing. Twenty minutes. Sound good?"

Frame: their session, their products, their feedback. You are the one taking notes.

### Walk them to try-on (the aha) — the heart of the call
Get them to the **on-model try-on of their own garment** as fast as possible. That is the moment that earns the right to ask for money. The activation spine is: enter studio → generate a model → import a product → **try on**. The try-on is the aha (`ahaKey: tryon`).

- Create a model that fits their segment (a baby/toddler for kids; the body type they struggle to shoot for swim/size-inclusive).
- Paste their product URL, import the garment.
- Generate the try-on at 2K. Let them watch it render.
- Lead with the result: _"There's your product, on a model you'd never have to cast or book."_

Watch for the reaction. The price ask lands very differently before vs after they see their own product on the right body. If something breaks or stalls before the first generate, note it (this is also the live activation-gap investigation).

### The four discovery questions (from `icp.decisiveTest`)
Ask these after they have seen the try-on. They map directly to the ICP rubric (unsolvable problem, recurrence, willingness to pay, product fit).

1. **The shoot today.** "How do you shoot this today, and what does it cost you in money and time?" _(Sizes the old way. For kids/swim this is the expensive, painful, recurring shoot.)_
2. **The hardest shot.** "What's the hardest or most expensive thing for you to photograph?" _(Surfaces the wedge: the body they cannot easily shoot. Listen for babies, plus/diverse bodies, swim fit.)_
3. **Frequency.** "How often do you need new imagery, every drop, every month?" _(Recurrence is the difference between one-time revenue and a subscription.)_
4. **What they use now.** "What tools do you use for product imagery right now, and what do they cost?" _(The PhotoRoom check. If they say PhotoRoom/Pimeli at ~$5 and that's all they need, the wedge is not there. If they describe gluing tools together and still can't get the on-model shot, it is.)_

### The price ask (do not skip, do not soften)
This is the whole point. Three escalating questions:

1. **"Would you pay for this?"** Yes/no, and watch the hesitation.
2. **"What would you pay per month?"** Let them name a number first. Silence is your friend. Then anchor: _"The plan we're building is $50 a month."_ (Do **not** quote the current $1,250/mo Pro wall; that is the enterprise anchor, not this test. Reference: planned SMB tier is $50/mo, free tier is 50 credits no card.)
3. **"Would you put a card down today?"** The real signal. A stated "I'd pay $50" is worth far less than a card on file. If they say yes, take it (or send the link on the call and watch them complete it). If they hesitate, ask what would have to be true.

> Why the card matters: free signups and even verbal yeses have told us nothing. A card clearing checkout is the first true revenue signal. Treat "would put a card down" as the conversion event, not "said they'd pay."

### The decision rule
After the calls, apply this exactly (from `icp.decisiveTest`):

> **Whichever segment converts a card first, at a price that clears CAC and sits clearly above the ~$5 free-tool floor, is ICP #1.**

Unpacked:
- **A card, not a verbal yes.** Stated willingness does not count.
- **Clears CAC.** The price has to support a CAC under $300 (ceiling) at roughly 8% signup-to-paid. A $50/mo card that retains gets there; a one-time $10 does not.
- **Above the ~$5 floor.** If the willingness sits at PhotoRoom money (~$5), there is no wedge, that is the commoditized flat-lay job free tools already own.
- **First to convert wins.** Kids and swim are running head to head. The one that produces a real card first gets promoted from hypothesis to Core, and budget concentrates there.

**Log per founder:** segment, did they reach try-on, the four answers, named price, card down (Y/N), and the single biggest reason for a no. That table is the deliverable that promotes a segment.

---

## 3. Outreach drafts

Cold, short, founder to founder. Lead with the wedge: the bodies they cannot easily or cheaply shoot. The ask is a 20-minute onboarding plus feedback call, not a sale. No em dashes, no hype, editorial and concrete.

> **Use note:** these are for warm and lightly-cold founders Alejo sources himself. Do not mass-send. Personalize the bracketed bits with the brand's actual product (the baby line, the swim fit, the size range). DRAFT ONLY, nothing here has been or should be sent.

### Cold email

**Kids version**
> **Subject:** your kids' line, on-model, no shoot
>
> Hi [First name],
>
> You can't cheaply shoot babies and toddlers. They're expensive to cast, hard to direct, and they age out of the product in weeks. That's the exact shot Ablo Studio is built to make: campaign-ready, on-model images of your [brand] pieces, in minutes, no photographer or casting.
>
> I'm hand-onboarding a few kids founders this week. I'll set it up on your real products, you tell me what's missing. 20 minutes, no pitch.
>
> Worth a look? I can send times.
>
> [Alejo]

**Swim / size-inclusive version**
> **Subject:** every body, every size, no casting
>
> Hi [First name],
>
> Swim and size-inclusive is the most expensive shoot in fashion: many bodies, real fit on diverse and plus models, a heavy SKU count. Ablo Studio makes the part you can't cheaply do, the believable on-model shot across every body type, in minutes from your product URL.
>
> I'm hand-onboarding a few founders this week. I'll set it up on your real [brand] pieces and you tell me where it falls short. 20 minutes, no pitch.
>
> Worth a look? I can send times.
>
> [Alejo]

### LinkedIn DM (shorter)

> Hi [First name], founder to founder. The hardest shot for a [kids / swim] brand is the one you can't cheaply do: [babies who age out in weeks / real fit across every body type]. That's exactly what we built Ablo Studio to make, on-model, from your product URL, in minutes. I'm onboarding a few founders by hand this week and would love to set it up on your actual products and get your read. 20 min, no pitch. Open to it?

**Why these work:** they lead from the result and the one wedge (the body the brand cannot shoot), name the founder's real pain in their own category, and ask for time, not money. The call is where the price ask happens, in person, after the aha.

---

## Appendix — grounding

All of the above is pulled from the OS (`window.ABLO_OS` in `data.js`):
- **Segments & named brands:** `icp.tiers`, `icp.realSignups` (Agenzia Kids, Water Vixen Swim, the "other" list).
- **The four questions + decision rule:** `icp.decisiveTest`, `icp.rubric`.
- **The ~$5 floor / PhotoRoom lesson:** `icp.lesson`.
- **Price anchors:** planned SMB $50/mo, current $1,250/mo Pro wall, free tier 50 credits no card (`competition.pricing`, `goals.unitEconomics`). Do not quote the $1,250 wall in the ask.
- **The aha (try-on):** `funnelCurated.ahaKey = tryon`; activation spine signup → model → import → try-on.
- **Voice:** `voice` (editorial, sparse, result-first, no em dashes, no hype, acronyms stay).
- **Targets:** `goals` (first paying customer by Jun 30, CAC < $300, signup→paid ≥ 8%, ARPU ≥ $50).

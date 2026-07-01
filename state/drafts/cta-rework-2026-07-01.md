# Convert + AHA CTA rework — ready-to-ship draft (2026-07-01)

Staged by the marketing OS so shipping is a paste, not a writing task. This is the reversible half the OS owns. The live Klaviyo edit is the escalate step (Alejo/whoever owns Klaviyo).

**Why these emails fail today:** opens are healthy (25 to 45%) but clicks are ~0 on every email except C1. C1 works because it rides the just-completed try-on (+2h, concrete, references what they just made). C2 to C5 drift into generic "explore plans" asks that read and get abandoned. The fix is the same each time: one concrete action tied to the try-on they already made, one direct link, no menu.

**Rules applied:** lead with their result, one action per email, link straight to /studio or their project (never a generic pricing page), no em dashes, no "learn more". Keep each under 60 words.

Segment tokens: `{{ first_name }}`, `{{ garment }}` (their tried-on product), `{{ project_url }}` (deep link to their studio project), `{{ studio_url }}`.

---

## Convert flow (try-on completers to paid)

### C2 — Day 2 — the wedge (currently 0% clicks / 53 recipients)
- **Subject:** Your {{ garment }}, on every body you can't cast
- **Preview:** Same product. New models. No shoot.
- **Body:** {{ first_name }}, the try-on you made is one model. The point of Ablo is the ones you can't book: different sizes, ages, skin tones, all wearing your {{ garment }}, all in minutes. Put it on three more right now.
- **CTA button:** Try it on 3 more models
- **Link:** {{ project_url }}

### C3 — Day 4 — proof / speed (currently 0% clicks / 35 recipients)
- **Subject:** A size-inclusive shoot, before lunch
- **Preview:** What used to cost a photographer and a week.
- **Body:** {{ first_name }}, your {{ garment }} is already rendering on real bodies. The version brands pay a studio for takes them a day and a casting call. You did it in a browser. Finish the set: 5 looks, one product page's worth, in the next 10 minutes.
- **CTA button:** Build the full set
- **Link:** {{ project_url }}

### C4 — Day 7 — the paid ask (currently 2.4% clicks / 41 recipients)
- **Subject:** Unlock the full shoot for {{ garment }}
- **Preview:** You've made the case. Here's the plan.
- **Body:** {{ first_name }}, you've tried it on. To download the high-res set, run unlimited models, and use them commercially, you need a plan. It's $50/mo, less than one hour of a photographer. Start with your {{ garment }} shoot.
- **CTA button:** Unlock my shoot ($50/mo)
- **Link:** {{ studio_url }}/pricing?ref=convert_c4

### C5 — last touch — single objection + exit (currently 0% clicks / 36 recipients)
- **Subject:** One question before you go
- **Preview:** What stopped you?
- **Body:** {{ first_name }}, you tried on your {{ garment }} and didn't upgrade. If it was quality, price, or fit on your product, reply and tell me one word. If it was time, your project is still saved. Pick it back up.
- **CTA button:** Reopen my project
- **Link:** {{ project_url }}

---

## AHA flow (model generated to try-on, currently 0% clicks)

### B1 — the missing half
- **Subject:** You made a model. Now dress it.
- **Preview:** Your {{ garment }} is one click from on-body.
- **Body:** {{ first_name }}, you generated a model but haven't put your product on it. That's the whole moment: your {{ garment }}, worn, in seconds. Finish it.
- **CTA button:** See it on-body
- **Link:** {{ project_url }}

### B2 — show the outcome
- **Subject:** This is what "shot in minutes" looks like
- **Preview:** No studio, no sample shipping, no casting.
- **Body:** {{ first_name }}, the try-on you started ends in a photo you'd put on a product page. One tap gets you there.
- **CTA button:** Finish my try-on
- **Link:** {{ project_url }}

---

## Test binding (when it ships)
Ship-and-measure, not an A/B (traffic too thin to power a split). Primary metric: `email_click` (baseline 0.0). Already covered by PRED-2026-06-22-cta-rework (email_click 0 to 5, due 2026-07-06) — resolve it against this artifact once live. Watch payment_rate as the downstream signal.

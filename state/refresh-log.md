# Marketing OS — refresh log

Narrative journal of each daily run: what moved, what concluded, what was added,
what's proposed next. The *structured* memory (scoreable predictions + durable
lessons) lives in `lessons.jsonl`; this file is the human-readable companion.

Newest entries on top.

---

## 2026-06-03 — first supervised reasoning run (orchestrator + read-agents)
- Ran the restructured routine: 3 read-agents (Experiments, Campaigns, Lifecycle) dispatched in parallel, Funnel reused; synthesis on their compact JSON returns (each read ~50-90k tokens out-of-context).
- Moved: signup-modal fix held at 42% (44% peak). Confirmed the activation gap (signup→model 69%) as the #1 leak, rage-click cluster on /studio.
- Concluded nothing (coachmarks PH-374260 underpowered at 6/7 exposures, left running). Caught: purchase_completed still not firing, so signup→paid unreadable; un-marked rank 5 "done".
- Re-ranked Command Center: price-ask test to #1 (most direct path to first paying customer), lifecycle wiring #2, activation gap #3, purchase_completed verify #4. Opened PRED-2026-06-03-activate-flow (activation_rate 69→75, due 2026-06-24).
- Proposes next: Alejo starts the price-ask test, wire the Activate flow, run a test purchase to verify purchase_completed fires.

## 2026-06-03 — self-improvement loop wired
- Added `state/lessons.jsonl`: append-only predict→score→learn ledger, read first / written last each run.
- `build.py` now surfaces it as `window.ABLO_OS.live.learning` (lessons, openPredictions, dueForReview, calibration).
- Seeded with the resolved Google-signup bet (33%→44%, hit) + 2 durable lessons. Calibration: 1/1 hits so far (thin, n=1).
- Next: every run logs a falsifiable prediction per fix/experiment and resolves matured bets against `history.jsonl`.

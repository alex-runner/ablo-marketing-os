export const meta = {
  name: 'marketing-os-refresh',
  description: 'Daily Ablo Studio marketing routine as a deterministic workflow: orient, 4 parallel read-agents, synthesize + re-rank + publish. Phase 2 of the orchestrator restructure.',
  phases: [
    { title: 'Orient' },
    { title: 'Read' },
    { title: 'Synthesize' },
  ],
}

// Phase 2 of docs/marketing-os-subagent-restructure.md. The workflow is the
// deterministic control flow; the agents are the hands (only agents can run
// bash / read files / write / commit, workflow scripts cannot).
//
// Run real:  Workflow({ scriptPath: 'scripts/refresh-workflow.js' })
// Run dry:   Workflow({ scriptPath: 'scripts/refresh-workflow.js', args: { dryRun: true } })
//   dryRun = read-only validation: orient skips build.py, synthesis reports the
//   proposed re-rank WITHOUT writing content.json/lessons.jsonl or committing.

const REPO = '/Users/alejo/Documents/Claude/ablo-marketing-os'
const SKILL = '/Users/alejo/.claude/skills/marketing-os-refresh/SKILL.md'
const CONTRACTS = '/Users/alejo/.claude/skills/marketing-os-refresh/references/read-agent-contracts.md'
// Robust args parse: the harness may deliver `args` as an object OR a JSON string.
// (A prior run received it as a string, so args.dryRun was undefined and a "dry"
// test executed for real, committing + pushing. Parse defensively.)
let _args = (typeof args !== 'undefined' && args) ? args : {}
if (typeof _args === 'string') { try { _args = JSON.parse(_args) } catch (e) { _args = {} } }
const dryRun = _args.dryRun === true || _args.dryRun === 'true'

// ---- schemas (validated at the tool layer, agents must return matching JSON) ----
const ORIENT = {
  type: 'object',
  required: ['goal', 'calibration', 'dueForReview', 'commandCenter', 'headline'],
  properties: {
    goal: { type: 'string' },
    calibration: { type: 'object', properties: { hitRate: { type: ['number', 'null'] }, n: { type: 'number' } } },
    dueForReview: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, metric: { type: 'string' }, due: { type: 'string' } } } },
    commandCenter: { type: 'array', items: { type: 'object', properties: { rank: { type: 'string' }, title: { type: 'string' }, sev: { type: 'string' } } } },
    headline: { type: 'string' },
  },
}
const EXPERIMENTS = {
  type: 'object', required: ['experiments', 'before_after', 'scored_predictions', 'measurement_ok', 'headline'],
  properties: {
    experiments: { type: 'array' }, before_after: { type: 'array' }, scored_predictions: { type: 'array' },
    measurement_ok: { type: 'boolean' }, headline: { type: 'string' },
  },
}
const FUNNEL = {
  type: 'object', required: ['stages', 'biggest_leak', 'hypotheses', 'fix_to_movement', 'measurement_ok', 'headline'],
  properties: {
    stages: { type: 'array' }, biggest_leak: { type: 'object' }, hypotheses: { type: 'array' },
    fix_to_movement: { type: 'array' }, measurement_ok: { type: 'boolean' }, headline: { type: 'string' },
  },
}
const CAMPAIGNS = {
  type: 'object', required: ['spend_7d', 'cpl', 'delivery', 'by_segment', 'anomalies', 'headline'],
  properties: {
    spend_7d: { type: ['number', 'null'] }, cpl: { type: ['number', 'null'] }, delivery: { type: 'string' },
    by_segment: { type: 'array' }, anomalies: { type: 'array' }, headline: { type: 'string' },
  },
}
const LIFECYCLE = {
  type: 'object', required: ['flows', 'top_gap', 'headline'],
  properties: { flows: { type: 'array' }, top_gap: { type: 'object' }, headline: { type: 'string' } },
}
const SYNTH = {
  type: 'object', required: ['reranked', 'predictions_resolved', 'predictions_opened', 'wrote', 'committed', 'summary', 'scoreboard'],
  properties: {
    reranked: { type: 'array', items: { type: 'object', properties: { rank: { type: 'string' }, title: { type: 'string' }, sev: { type: 'string' } } } },
    predictions_resolved: { type: 'array' }, predictions_opened: { type: 'array' },
    wrote: { type: 'boolean' }, committed: { type: ['boolean', 'null'] },
    summary: { type: 'array', items: { type: 'string' } }, scoreboard: { type: 'string' },
  },
}

const READONLY = 'READ-ONLY: gather and return only the JSON below, no writes, no git. data.js first, live MCP only for what is missing.'
const GOAL = 'Goal: first paying customer by end-of-June, CAC < $300, signup→paid ≥ 8%.'

// ---- step 0: orient ----
log(`marketing-os-refresh starting · dryRun=${dryRun} (false = real run: writes + commit + push)`)
phase('Orient')
const orient = await agent(
  `You are the ORIENT step of the Ablo marketing OS daily routine. Playbook: ${SKILL} (step 0).
${GOAL}
${dryRun
    ? 'DRY RUN: do NOT run build.py. Read the existing ' + REPO + '/data.js.'
    : 'Run `cd ' + REPO + ' && python3 build.py` to refresh live data into data.js, then read it.'}
Read only the compact slices: goals, commandCenter, and live.learning (lessons, openPredictions, dueForReview, calibration). Also read state/lessons.jsonl.
Return ONLY the orient JSON: goal, calibration {hitRate,n}, dueForReview (each {id, metric, due}), commandCenter (each {rank, title, sev}), and a one-line headline.`,
  { schema: ORIENT, label: 'orient', phase: 'Orient' },
)

// ---- steps 1-4: parallel read-agents ----
phase('Read')
const due = JSON.stringify((orient && orient.dueForReview) || [])
const [experiments, funnel, campaigns, lifecycle] = await parallel([
  () => agent(`You are the Experiments read-agent. Contract: ${CONTRACTS} (section 1). ${READONLY}
${GOAL}
Read the experiments block in ${REPO}/data.js and before/after tracked experiments; you may query PostHog MCP (project "Ablo Studio"). Score any of these dueForReview predictions you can see: ${due}. Return ONLY the Experiments JSON.`,
    { schema: EXPERIMENTS, label: 'experiments', phase: 'Read' }),
  () => agent(`You are the Funnel read-agent. Contract: ${CONTRACTS} (section 2). ${READONLY}
${GOAL}
Read the live funnel from ${REPO}/data.js (per-stage reach + activation spine + leaks), compare to ${REPO}/history.jsonl, score any dueForReview funnel-fix predictions in ${due}, name the biggest leak by leverage with 1-2 hypotheses. Return ONLY the Funnel JSON.`,
    { schema: FUNNEL, label: 'funnel', phase: 'Read' }),
  () => agent(`You are the Campaigns read-agent. Contract: ${CONTRACTS} (section 3). ${READONLY}
${GOAL}
Read the Meta autopilot / paid blocks in ${REPO}/data.js and LinkedIn spend; query Meta Ads MCP only if the block is thin. Report spend, CPL, delivery health, per-segment (Kids, Swim), waste, anomalies. Return ONLY the Campaigns JSON.`,
    { schema: CAMPAIGNS, label: 'campaigns', phase: 'Read' }),
  () => agent(`You are the Lifecycle read-agent. Contract: ${CONTRACTS} (section 4). ${READONLY}
${GOAL}
Read the lifecycle blocks in ${REPO}/data.js (Klaviyo flow status + prepared templates); query Klaviyo MCP only if thin. Name the single highest-leverage gap. Return ONLY the Lifecycle JSON.`,
    { schema: LIFECYCLE, label: 'lifecycle', phase: 'Read' }),
])

// ---- steps 0-resolve, 5, 6, 7, 8: synthesis + writes (orchestrator role) ----
phase('Synthesize')
const findings = JSON.stringify({ orient, experiments, funnel, campaigns, lifecycle })
const synth = await agent(
  `You are the SYNTHESIS + PUBLISH step of the Ablo marketing OS. Playbook: ${SKILL} (steps 0-resolve, 5, 6, 7, 8). Work in ${REPO}.
${GOAL}
Here are the orient + 4 read-agent findings (already gathered, do NOT re-read the raw sources): ${findings}

Do the orchestrator writes, exactly per the playbook:
- Resolve every dueForReview prediction using the agents' scored_predictions: edit state/lessons.jsonl in place (status, actual, verdict, resolved_date) and append a one-line lesson.
- Measurement integrity: if any measurement_ok is false, treat it as a flag (do not over-claim signup→paid).
- Re-rank commandCenter.items in content.json by leverage toward the goal (the renderer uses ARRAY ORDER; reorder the array AND renumber rank, move done items to the bottom). Only edit the commandCenter block. Validate content.json parses.
- Build the next experiment from state/experiment-roadmap.md respecting the non-overlap rule (≤1 live test per surface); log the leading bet as a prediction in state/lessons.jsonl (metric must be a real history.jsonl key); re-rank the roadmap.
- Append 2-3 lines to state/refresh-log.md.
${dryRun
    ? '- DRY RUN: do NOT write any file, do NOT run build.py, do NOT commit. Instead REPORT the proposed re-rank, the predictions you WOULD resolve/open, and what you WOULD commit. Set wrote=false, committed=null.'
    : '- Then run `python3 build.py` to re-render, and COMMIT EXACTLY ONCE: `git add -A && git commit -m "chore: daily marketing routine $(date +%F)" && git push origin main`. Mark state/run-$(date +%F).json complete. Set wrote=true, committed=true (or false if the push failed).'}

Return ONLY the Synthesis JSON: reranked (each {rank,title,sev}), predictions_resolved, predictions_opened, wrote, committed, summary (3 short lines: top movement, top action, anything needing Alejo), scoreboard (one line: resolved with verdicts, opened, calibration hitRate/n).`,
  { schema: SYNTH, label: 'synthesize', phase: 'Synthesize' },
)

return { dryRun, orient, experiments, funnel, campaigns, lifecycle, synth }

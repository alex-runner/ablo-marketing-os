export const meta = {
  name: 'marketing-os-refresh',
  description: 'Daily Ablo Studio marketing routine as a deterministic workflow: orient, 4 parallel read-agents, synthesize + re-rank + publish. Phase 2 of the orchestrator restructure.',
  phases: [
    { title: 'Orient' },
    { title: 'Read' },
    { title: 'Synthesize' },
    { title: 'QA' },
    { title: 'Publish' },
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

// ---- step 6/7 (PROPOSE): synthesis computes the plan, NO writes, NO commit ----
phase('Synthesize')
const findings = JSON.stringify({ orient, experiments, funnel, campaigns, lifecycle })
const PROPOSAL = {
  type: 'object', required: ['reranked', 'predictions_to_resolve', 'predictions_to_open', 'roadmap_changes', 'escalations', 'summary'],
  properties: {
    reranked: { type: 'array', items: { type: 'object', properties: { rank: { type: 'string' }, title: { type: 'string' }, sev: { type: 'string' }, why: { type: 'string' } } } },
    predictions_to_resolve: { type: 'array' }, predictions_to_open: { type: 'array' },
    roadmap_changes: { type: 'array' }, escalations: { type: 'array' }, measurement_flags: { type: 'array' },
    summary: { type: 'array', items: { type: 'string' } },
  },
}
const proposal = await agent(
  `You are the SYNTHESIS (PROPOSE) step of the Ablo marketing OS. Playbook: ${SKILL} (steps 0-resolve, 5, 6, 7). Work from the findings only, do NOT re-read raw sources, and **do NOT write any file or commit** — only PROPOSE.
${GOAL}
Findings: ${findings}
Propose, per the playbook:
- predictions_to_resolve: each dueForReview prediction + its actual/verdict from the agents' scored_predictions.
- predictions_to_open: the leading funnel/experiment bet (metric must be a real history.jsonl key, baseline from data, predicted lift tempered by calibration).
- reranked: the full commandCenter order (each {rank,title,sev,why}), by leverage toward the goal.
- roadmap_changes: experiment-roadmap edits respecting the non-overlap rule (≤1 live test per surface).
- escalations: anything irreversible or user-visible (per the SKILL.md safety boundary) that must be staged for a human, NOT auto-applied.
- measurement_flags: any measurement_ok=false issue.
Return ONLY the Proposal JSON.`,
  { schema: PROPOSAL, label: 'propose', phase: 'Synthesize' },
)

// ---- step 7.5 (QA): 2-3 skeptics REFUTE the proposal in parallel, distinct lenses ----
phase('QA')
const QA = {
  type: 'object', required: ['lens', 'refutations', 'qa_lessons', 'verdict', 'headline'],
  properties: {
    lens: { type: 'string' }, refutations: { type: 'array' }, qa_lessons: { type: 'array' },
    verdict: { type: 'string' }, headline: { type: 'string' },
  },
}
const proposalStr = JSON.stringify(proposal)
const LENSES = [
  { key: 'numbers', brief: 're-verify EVERY figure in the proposal against data.js and history.jsonl; flag anything hallucinated, stale, or off.' },
  { key: 'calls', brief: 'attack the judgment: is any "winner" actually powered (~200 exposures/variant)? does every Command Center item ladder to the goal? does each new prediction respect calibration (humble when n is thin)?' },
  { key: 'boundary', brief: 'did the proposal auto-apply anything irreversible or user-visible (see the SKILL.md safety boundary)? those belong in escalations, not committed.' },
]
const qa = await parallel(LENSES.map((L) => () =>
  agent(`You are a QA SKEPTIC for the Ablo marketing OS, lens "${L.key}". Contract: ${CONTRACTS} (section 5). READ-ONLY. Your job is to REFUTE this run, not bless it. Default to refuted when uncertain.
${GOAL}
Proposal to attack: ${proposalStr}
Findings it came from: ${findings}
Your lens: ${L.brief}
Return ONLY the QA JSON (lens="${L.key}").`,
    { schema: QA, label: `qa:${L.key}`, phase: 'QA' })))

// ---- step 7.5 act + feed-back, step 8 publish: APPLY only QA-approved work ----
phase('Publish')
const qaStr = JSON.stringify(qa.filter(Boolean))
const apply = await agent(
  `You are the APPLY + PUBLISH step of the Ablo marketing OS. Playbook: ${SKILL} (step 7.5 act/feed-back + step 8). Work in ${REPO}.
${GOAL}
The proposal: ${proposalStr}
The QA skeptics' verdicts: ${qaStr}

Act on QA first:
- Any decision a skeptic REFUTED that the proposal cannot defend with the data: revise or HOLD it (do not apply). Log each held item as "held by QA: reason" in state/refresh-log.md.
- Write every real qa_lesson from the skeptics as a lesson tagged "qa" in state/lessons.jsonl (a forward-looking rule), so the next run reads it first.
- Keep all escalations as proposals / Command Center items only; never auto-fire irreversible or user-visible actions.

Then apply the QA-approved proposal per the playbook: resolve predictions + append lessons in state/lessons.jsonl; re-rank commandCenter.items in content.json (renderer uses ARRAY ORDER: reorder + renumber, done items last; only the commandCenter block; validate it parses); update state/experiment-roadmap.md; append 2-3 lines to state/refresh-log.md.
${dryRun
    ? '- DRY RUN: do NOT write any file, do NOT run build.py, do NOT commit. REPORT what you WOULD apply and hold. Set wrote=false, committed=null.'
    : '- Then run `python3 build.py`, and COMMIT EXACTLY ONCE (stage only the routine files, never `git add -A`): `git add content.json data.js index.html history.jsonl state/lessons.jsonl state/refresh-log.md state/experiment-roadmap.md "state/run-$(date +%F).json" && git commit -m "chore: daily marketing routine $(date +%F)" && git push origin main`. Set wrote=true, committed=true (or false if push failed).'}

Return ONLY the Synthesis JSON: reranked (each {rank,title,sev}), predictions_resolved, predictions_opened, wrote, committed, summary (3 lines: top movement, top action, anything needing Alejo incl. QA holds + escalations), scoreboard (one line: resolved with verdicts, opened, qa catches this run, calibration hitRate/n).`,
  { schema: SYNTH, label: 'apply+publish', phase: 'Publish' },
)

return { dryRun, orient, experiments, funnel, campaigns, lifecycle, proposal, qa, apply }

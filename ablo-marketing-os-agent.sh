#!/bin/bash
# Ablo Marketing OS -- autonomous reasoning layer (the "brain" pass). HARDENED.
#
# Runs the marketing reasoning headless via `claude`, inside an ISOLATED git
# worktree under ~/.local/state (outside ~/Documents: no macOS TCC issues, and
# the live main/Pages site is never touched by accident). The headless agent only
# re-ranks content.json (commandCenter.items) and appends to state/lessons.jsonl;
# this wrapper owns ALL git and the deploy decision, and gates every publish.
#
# Safety model (defense in depth):
#   - single-instance lock (shared with the data-refresh job)
#   - the agent runs under a SCOPED --settings with acceptEdits (NOT bypass, which
#     would ignore deny rules) so it cannot read ~/.claude/.env, ~/.ssh, etc.
#   - wall-clock timeout on the agent
#   - publish is gated on: agent exit 0 + valid non-empty envelope, then a
#     fail-closed validator (content.json parses, lessons.jsonl parses, NO secret
#     shapes or literal ~/.claude/.env values in either file)
#   - only content.json + state/lessons.jsonl are ever committed; push uses
#     --force-with-lease
#   - PUSH_MODE=live builds in the worktree and only fast-forwards main if build.py
#     succeeds (atomic); main is never touched with an unbuilt/ invalid tree.
#
# PUSH_MODE (env): review (default) -> branch agent/daily; live -> deploy to main.
# Other env: AGENT_MODEL (default sonnet), AGENT_BUDGET (default 6), AGENT_TIMEOUT (default 1200s).
set -uo pipefail
export PATH="/Users/alejo/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="$HOME/Documents/Claude/ablo-marketing-os"
WT="$HOME/.local/state/ablo-mktos-agent"
BR="agent/daily"
LOCK="$HOME/.local/state/ablo-mktos.lock"
SETTINGS="$HOME/.local/state/ablo-mktos-agent-settings.json"
VALIDATE="$HOME/.local/bin/ablo-mktos-validate.py"
PUSH_MODE="${PUSH_MODE:-review}"
MODEL="${AGENT_MODEL:-sonnet}"
TIMEOUT="${AGENT_TIMEOUT:-1200}"
LIVE_TARGET="${LIVE_TARGET:-main}"   # deploy ref for live mode; override to a throwaway branch to test
LOG_DIR="$HOME/.local/log"; LOG="$LOG_DIR/ablo-marketing-os-agent.log"
JSON="$LOG_DIR/agent-last.json"
mkdir -p "$LOG_DIR" "$(dirname "$LOCK")"
# rotate the log if it passes ~5MB
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv -f "$LOG" "$LOG.1"
log(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
# Telegram digest: no-op unless BOTH token + chat_id are present in ~/.claude/.env.
notify(){
  [ -n "${ABLO_MOS_TELEGRAM_TOKEN:-}" ] && [ -n "${ABLO_MOS_TELEGRAM_CHAT_ID:-}" ] || return 0
  curl -s --max-time 15 "https://api.telegram.org/bot${ABLO_MOS_TELEGRAM_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${ABLO_MOS_TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=$1" -d disable_web_page_preview=true >>"$LOG" 2>&1 || true
}

# --- single-instance lock (shared with the 09:00 data-refresh job) ----------
# Robust to a SIGKILLed prior run: steal the lock if its holder PID is dead or
# the lock is >30m old (older than any legitimate run), so an orphaned lockdir
# can never deadlock the daily pipeline.
if mkdir "$LOCK" 2>/dev/null; then echo $$ > "$LOCK/pid"; else
  _lp="$(cat "$LOCK/pid" 2>/dev/null || echo '')"
  _age=$(( $(date +%s) - $(stat -f%m "$LOCK" 2>/dev/null || date +%s) ))
  if { [ -n "$_lp" ] && ! kill -0 "$_lp" 2>/dev/null; } || [ "$_age" -gt 1800 ]; then
    rm -rf "$LOCK"; if mkdir "$LOCK" 2>/dev/null; then echo $$ > "$LOCK/pid"; log "stole a stale lock (dead holder or >30m old)."; else log "lock contended; exiting."; exit 0; fi
  else
    log "another ablo-mktos job holds the lock; exiting."; exit 0
  fi
fi
cleanup(){ rm -rf "$LOCK" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
log "===== agent run start (mode=$PUSH_MODE model=$MODEL) ====="

# --- auth: subscription OAuth token, nothing inherited (launchd-safe) -------
[ -f "$HOME/.claude/.env" ] && source "$HOME/.claude/.env"
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_CUSTOM_HEADERS
export CLAUDE_CODE_OAUTH_TOKEN
[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && { log "FATAL: no CLAUDE_CODE_OAUTH_TOKEN in ~/.claude/.env"; exit 1; }

cd "$HOME" 2>/dev/null || true

# --- refresh the isolated worktree to the latest origin/main ----------------
git -C "$REPO" worktree prune >>"$LOG" 2>&1 || true
git -C "$REPO" fetch origin main >>"$LOG" 2>&1 || { log "FATAL: fetch failed"; exit 1; }
if git -C "$REPO" worktree list 2>/dev/null | grep -q "$WT"; then
  git -C "$WT" checkout -B "$BR" origin/main >>"$LOG" 2>&1 && git -C "$WT" reset --hard origin/main >>"$LOG" 2>&1 \
    || { log "FATAL: worktree refresh failed"; exit 1; }
else
  rm -rf "$WT"
  git -C "$REPO" worktree add -B "$BR" "$WT" origin/main >>"$LOG" 2>&1 || { log "FATAL: worktree add failed"; exit 1; }
fi
git -C "$WT" clean -fd >>"$LOG" 2>&1 || true

# --- freshness gate: never reason on (or deploy) stale data ------------------
# If the 09:00 data refresh did not land, origin/main's data.js is yesterday's.
# Reasoning/deploying on it would publish stale numbers, so skip the day cleanly.
# Bypass for manual runs with AGENT_SKIP_FRESHNESS=1; tune with AGENT_MAX_DATA_AGE_H.
if [ "${AGENT_SKIP_FRESHNESS:-0}" != "1" ]; then
  AGE_H="$(python3 - "$WT/data.js" <<'PY'
import json, sys, datetime
try:
    t = open(sys.argv[1], encoding="utf-8").read()
    i = t.find("window.ABLO_OS = "); j = t.rfind("};")
    d = json.loads(t[i + len("window.ABLO_OS = "):j + 1])
    iso = (d.get("meta") or {}).get("updatedISO")
    dt = datetime.datetime.fromisoformat(iso)
    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"{(now - dt).total_seconds() / 3600:.1f}")
except Exception:
    print("NA")
PY
)"
  MAXAGE="${AGENT_MAX_DATA_AGE_H:-18}"
  if [ "$AGE_H" = "NA" ]; then
    log "freshness: could not read data.js timestamp; proceeding (fail-open)."
  elif awk "BEGIN{exit !($AGE_H > $MAXAGE)}"; then
    log "SKIP: data.js is ${AGE_H}h old (> ${MAXAGE}h) -- the 09:00 refresh did not land. No reasoning, no deploy."
    notify "Ablo MOS $(date '+%F'): skipped. data.js is ${AGE_H}h old, the 09:00 data refresh did not land."
    exit 0
  else
    log "freshness OK: data.js is ${AGE_H}h old."
  fi
fi

# --- run the reasoning pass headless, CONFINED (scoped settings, timeout) ----
PROMPT="You are the Ablo Studio marketing operator running the daily reasoning pass, headless and unattended. Your current directory is an isolated git worktree of the marketing OS; edit files HERE by relative path only.

Goal everything ranks against: first paying customers, CAC < \$300, signup->paid >= 8%.

Do this, in order:
1. Read ./data.js (window.ABLO_OS): live funnel, campaigns, experiments, lifecycle, KPIs.
2. Read ./state/lessons.jsonl FIRST. For any open prediction whose 'due' date has passed, resolve it: read the real metric from the data, add status:resolved + actual + verdict(hit|partial|miss) + resolved_date, and append a one-line lesson record.
3. Re-rank ./content.json commandCenter.items by leverage toward the goal. Renumber rank 1..N. Update each item's status to today's reality. Move resolved items to the bottom (done:true, sev:done). Add an item for any new high-severity leak the data shows.
4. Append the leading new bet as a prediction record to ./state/lessons.jsonl (schema: {\"type\":\"prediction\",\"id\":\"PRED-YYYY-MM-DD-slug\",\"date\":...,\"action\":...,\"metric\":\"<a real history.jsonl key>\",\"baseline\":N,\"predicted\":N,\"horizon_days\":N,\"due\":\"YYYY-MM-DD\",\"status\":\"open\"}).

5. QA pressure-test before you finalize. Re-read your re-rank and your new prediction and try to REFUTE them. Re-verify every number you used against the data in this directory. For any claim you cannot defend from the data, revise it or drop it. Do not call an experiment a winner unless its sample clears the floor (about 200 exposures per variant), and stay humble when calibration is thin. Append any mistake you catch as a lesson record tagged qa, so the next run reads it first, and note in your summary anything QA made you change or hold.

Voice: editorial, sparse, concrete, no em dashes. EDIT ONLY ./content.json and ./state/lessons.jsonl. Never read files outside this directory. Do NOT regenerate data.js, do NOT run shell commands.

Finish with a 3-line summary (top movement, top action, anything needing Alejo), a one-line prediction scoreboard, plus a final line that starts with QA: stating pass, or revised N, or held N, reporting what your step-5 QA check did."

# portable wall-clock timeout (no gtimeout dependency)
run_to(){ local secs="$1"; shift
  "$@" & local cpid=$!
  ( sleep "$secs"; kill -TERM "$cpid" 2>/dev/null; sleep 5; kill -KILL "$cpid" 2>/dev/null ) & local kpid=$!
  wait "$cpid"; local rc=$?
  kill -TERM "$kpid" 2>/dev/null; wait "$kpid" 2>/dev/null
  return $rc
}

cd "$WT"
run_to "$TIMEOUT" claude -p "$PROMPT" \
  --settings "$SETTINGS" \
  --add-dir "$WT" \
  --permission-mode acceptEdits \
  --allowedTools "Read Edit Write Grep Glob" \
  --model "$MODEL" \
  --max-budget-usd "${AGENT_BUDGET:-6}" \
  --no-session-persistence \
  --output-format json \
  >"$JSON" 2>>"$LOG"
CLDRC=$?
cd "$HOME"
log "claude exit=$CLDRC"

# --- GATE 1: agent must have exited cleanly with a valid, successful envelope -
if [ "$CLDRC" -ne 0 ]; then
  log "ABORT: agent exited nonzero ($CLDRC, timeout/crash/budget). Nothing published."
  notify "Ablo MOS $(date '+%F'): ABORTED. agent exited $CLDRC (timeout/crash/budget). Nothing published."; exit 1
fi
ENV_OK="$(python3 -c "import json,sys
try:
    d=json.load(open('$JSON'))
except Exception as e:
    print('BADJSON:'+str(e)); sys.exit(0)
print('ERR' if d.get('is_error') else 'OK')
print((d.get('result') or '').strip()[:6000])
print('cost=\$'+str(round(d.get('total_cost_usd') or 0,3)))" 2>>"$LOG")"
if [ -z "$ENV_OK" ] || ! printf '%s' "$ENV_OK" | head -1 | grep -q '^OK$'; then
  log "ABORT: agent envelope missing/error: $(printf '%s' "$ENV_OK" | head -1). Nothing published."
  notify "Ablo MOS $(date '+%F'): ABORTED. agent returned an error or empty result. Nothing published."; exit 1
fi
SUMMARY="$(printf '%s\n' "$ENV_OK" | tail -n +2)"
log "--- agent summary ---"; printf '%s\n' "$SUMMARY" >> "$LOG"

# QA verdict for the notification: the agent's step-5 self-check reports a 'QA:' line.
# If it is missing, the QA step likely did not run -- surface that loudly, not silently.
# The agent emits the line as markdown ("**QA: revised 2, held 1.**"), so allow a
# leading "*"/"_"/space run and strip the markdown before the MISSING gate compares it.
# (Without this the regex never matched and EVERY live run was wrongly withheld.)
QA_LINE="$(printf '%s\n' "$SUMMARY" | grep -iE '^[*_ ]*QA:' | head -1 | sed -E 's/^[*_ ]+//; s/\*+//g')"
[ -z "$QA_LINE" ] && QA_LINE="QA: MISSING -- self-check may not have run; check the log"
log "QA verdict: $QA_LINE"

# --- GATE 2: fail-closed validator (JSON parses + NO secrets in the output) --
if ! python3 "$VALIDATE" "$WT" >>"$LOG" 2>&1; then
  log "ABORT: validation/secret-scan FAILED (see above). Nothing published."
  notify "Ablo MOS $(date '+%F'): ABORTED. validation/secret-scan failed. Nothing published."; exit 1
fi

# --- stage ONLY the two reasoning files (nothing else can be published) ------
git -C "$WT" add content.json state/lessons.jsonl >>"$LOG" 2>&1
if git -C "$WT" diff --cached --quiet; then
  log "no reasoning changes this run; nothing to publish."
  notify "Ablo MOS $(date '+%F'): ran clean, no changes to the queue today."; exit 0
fi
git -C "$WT" -c user.name='Ablo MOS Agent' -c user.email='agent@ablo.local' \
  commit -m "agent: daily reasoning $(date '+%F')" >>"$LOG" 2>&1

# QA deploy gate: never auto-deploy to live if the self-check did not run (QA: MISSING).
# A missing QA downgrades this run to a review proposal on agent/daily, not a live deploy.
DEPLOY_MODE="$PUSH_MODE"
if [ "$PUSH_MODE" = "live" ] && printf '%s' "$QA_LINE" | grep -qi 'MISSING'; then
  DEPLOY_MODE="review"
  log "QA GATE: self-check did not run ($QA_LINE). Withholding live deploy; pushing a review proposal instead."
  notify "Ablo MOS $(date '+%F'): live deploy WITHHELD by the QA gate ($QA_LINE). Pushed to agent/daily for review instead of main."
fi
if [ "$DEPLOY_MODE" = "live" ]; then
  # Atomic deploy: build IN the worktree; only fast-forward main if build.py wins.
  if ! ( cd "$WT" && python3 build.py ) >>"$LOG" 2>&1; then
    log "ABORT(live): build.py failed on the agent's content.json. main untouched."
    notify "Ablo MOS $(date '+%F'): live deploy ABORTED. build.py failed. site unchanged."; exit 1
  fi
  if ! python3 "$VALIDATE" "$WT" >>"$LOG" 2>&1; then
    log "ABORT(live): post-build validation failed. main untouched."
    notify "Ablo MOS $(date '+%F'): live deploy ABORTED. post-build validation failed. site unchanged."; exit 1
  fi
  git -C "$WT" add content.json state/lessons.jsonl data.js history.jsonl >>"$LOG" 2>&1
  git -C "$WT" -c user.name='Ablo MOS Agent' -c user.email='agent@ablo.local' \
    commit -m "chore: autonomous marketing routine $(date '+%F')" --amend >>"$LOG" 2>&1
  if git -C "$WT" push --force-with-lease origin "$BR":"$LIVE_TARGET" >>"$LOG" 2>&1; then
    log "LIVE deploy: fast-forwarded $LIVE_TARGET (atomic, build-verified)."
    notify "Ablo MOS $(date '+%F'): deployed to live (build + validator passed).
$QA_LINE

$SUMMARY"
  else
    log "live push rejected ($LIVE_TARGET moved since fetch, or lease stale). No deploy this run."
    notify "Ablo MOS $(date '+%F'): deploy skipped, $LIVE_TARGET moved since fetch. Will retry next run."
  fi
else
  if git -C "$WT" push --force-with-lease origin "$BR" >>"$LOG" 2>&1; then
    log "review branch pushed: $BR (diff vs main = the proposal)."
    notify "Ablo MOS $(date '+%F'): proposal pushed to agent/daily for review.
$QA_LINE

$SUMMARY"
  else
    log "branch push rejected (lease stale / reviewer commit). Left as-is."
  fi
fi

printf '%s\n' "$SUMMARY" > "$LOG_DIR/agent-digest.txt"
log "===== agent run done ====="

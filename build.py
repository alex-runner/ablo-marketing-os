#!/usr/bin/env python3
"""
Ablo Studio Marketing OS - site generator.

Reads the curated strategy (content.json) and merges in LIVE data:
  - PostHog experiments  (REST, key from ~/.claude/.env)
  - Meta campaign metrics (read from the ablo-ads-autopilot local state)
  - the autopilot's funnel intelligence (insights.json)

Writes data.js  ->  window.ABLO_OS = {...}, which index.html renders.

Design goals: stdlib only, and every live source degrades gracefully. If a
pull fails we log it and fall back to the curated content, so the site never
breaks. Run daily by the launchd routine (see refresh.sh).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content.json"
OUT = HERE / "data.js"
HISTORY = HERE / "history.jsonl"  # append-only daily time-series (one row per UTC day)
REGISTRY = HERE / "coverage-registry.json"  # git-tracked manifest of what the OS models (Coverage Reconciler)

# The ablo-ads-autopilot keeps fresh Meta state here (refreshed every 6h).
AUTOPILOT = Path(
    "/Users/alejo/Documents/Claude/Brain/projects/ablo/Ablo Studio/autopilot/state"
)
ENV_FILE = Path.home() / ".claude" / ".env"

# Foundation strategy layer — the canonical marketing context lives as markdown in
# the Brain (Obsidian), NOT in this repo. build.py reads it and renders it, so
# strategy is edited there, not here. Overridable via ABLO_STRATEGY_DIR. The
# expected-doc set + ordering live in strategy-registry.json (git-tracked here).
STRATEGY_DIR = Path(os.environ.get(
    "ABLO_STRATEGY_DIR",
    "/Users/alejo/Documents/Claude/Brain/projects/ablo/Ablo Studio/marketing-strategy/foundation",
))
STRATEGY_REGISTRY = HERE / "strategy-registry.json"

log = lambda m: print(f"[build] {m}", file=sys.stderr)


def tidy(s):
    """Light cleanup of machine-generated copy: no double-hyphen dashes, no em dashes."""
    if not s:
        return s
    return s.replace(" -- ", ", ").replace("--", ", ").replace(" — ", ", ").replace("—", ", ")


def load_env(path):
    """Parse `export KEY='value'` / `KEY=value` lines without sourcing a shell."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line[7:].strip() if line.startswith("export ") else line
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'").strip('"')
    return env


# ---------------------------------------------------------------- PostHog ----
def fetch_experiments(env):
    """Return a list of live experiments, or [] on any failure."""
    key = env.get("POSTHOG_PERSONAL_API_KEY")
    pid = env.get("POSTHOG_PROJECT_ID", "419152")
    if not key:
        log("no POSTHOG_PERSONAL_API_KEY; skipping live experiments")
        return []
    host = env.get("POSTHOG_HOST", "")
    region = "eu" if "eu" in host.lower() else "us"
    base = f"https://{region}.posthog.com"
    url = f"{base}/api/projects/{pid}/experiments/?limit=50"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        log(f"PostHog fetch failed ({e}); falling back to curated experiments")
        return []

    out = []
    for ex in payload.get("results", []):
        if ex.get("archived") or ex.get("deleted"):
            continue
        start, end = ex.get("start_date"), ex.get("end_date")
        if end:
            status = "Complete"
        elif start:
            status = "Running"
        else:
            status = "Draft"
        desc = (ex.get("description") or "").strip()
        m = re.search(r"[Pp]rimary metric[:\s]+([A-Za-z0-9_ ]+)", desc)
        metric = m.group(1).strip().rstrip(".") if m else _first_metric_name(ex)
        out.append(
            {
                "id": f"PH-{ex.get('id')}",
                "name": ex.get("name", "Untitled experiment"),
                "status": status,
                "flag": ex.get("feature_flag_key") or "",
                "hypothesis": desc,
                "metric": metric,
                "started": _short_date(start),
                "url": f"{base}/project/{pid}/experiments/{ex.get('id')}",
            }
        )
    log(f"PostHog: {len(out)} experiment(s) live")
    return out


def _first_metric_name(ex):
    for field in ("metrics", "metrics_secondary"):
        arr = ex.get(field) or []
        if arr and isinstance(arr, list) and isinstance(arr[0], dict):
            return arr[0].get("name") or ""
    return ""


def _short_date(iso):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %-d, %Y")
    except ValueError:
        return iso[:10]


# ------------------------------------------------------------------- Meta ----
def fetch_meta():
    """Pull lifetime numbers + delivery health + funnel intelligence from the autopilot."""
    meta = {
        "spend": None,
        "signups": None,
        "cpl": None,
        "status": "Unknown",
        "asOf": "",
        "deliveryFlag": "",
        "funnelHeadline": "",
        "funnelSuggestions": [],
    }

    latest = AUTOPILOT / "LATEST.md"
    if latest.exists():
        txt = latest.read_text()
        m = re.search(
            r"Lifetime:\s*\$([\d,.]+)\s*spend,\s*([\d,]+)\s*signups,\s*CPL\s*\$([\d.]+)",
            txt,
        )
        if m:
            meta["spend"] = f"${m.group(1)}"
            meta["signups"] = int(m.group(2).replace(",", ""))
            meta["cpl"] = f"${m.group(3)}"
            log(f"Meta: lifetime {meta['spend']} / {meta['signups']} signups / {meta['cpl']} CPL")

    cycle = AUTOPILOT / "last-cycle.json"
    if cycle.exists():
        try:
            c = json.loads(cycle.read_text())
            meta["asOf"] = _short_date(c.get("written_at", ""))
            flags = (c.get("plan") or {}).get("flags") or []
            delivery = [f for f in flags if f.get("kind") == "DELIVERY_HEALTH"]
            if delivery:
                # The autopilot grades delivery: "high" = broken right now,
                # "medium"/"low" = a past stall that has since resumed (the flag
                # is informational, not a current pause). Only the high case is
                # an actual pause -- otherwise the campaign is live and the flag
                # reason is shown as a recovery note, not a "paused" alarm.
                d0 = delivery[0]
                reason = d0.get("reason", "")
                meta["deliveryFlag"] = reason
                # A "high" flag can lag reality: if the reason text says delivery
                # has resumed, the campaign is live again even before the next
                # cycle re-grades it. Treat that as Live, not paused.
                resumed = "resume" in reason.lower()
                meta["status"] = "Delivery paused" if (d0.get("severity") == "high" and not resumed) else "Live"
            else:
                meta["status"] = "Live"
        except (ValueError, KeyError) as e:
            log(f"last-cycle.json parse issue: {e}")

    ins = AUTOPILOT / "insights.json"
    if ins.exists():
        try:
            data = json.loads(ins.read_text())
            meta["funnelHeadline"] = tidy(data.get("headline", ""))
            for s in (data.get("suggestions") or [])[:4]:
                meta["funnelSuggestions"].append(
                    {
                        "step": s.get("step", ""),
                        "severity": s.get("severity", ""),
                        "title": tidy(s.get("title", "")),
                        "evidence": tidy(s.get("evidence", "")),
                    }
                )
            log(f"Meta: funnel intelligence + {len(meta['funnelSuggestions'])} suggestion(s)")
        except (ValueError, KeyError) as e:
            log(f"insights.json parse issue: {e}")

    return meta


# --------------------------------------------------------------- PostHog HQL --
def _hogql(env, query):
    """Run a HogQL query, return result rows (list of lists). None on failure."""
    key = env.get("POSTHOG_PERSONAL_API_KEY")
    pid = env.get("POSTHOG_PROJECT_ID", "419152")
    if not key:
        return None
    host = env.get("POSTHOG_HOST", "")
    region = "eu" if "eu" in host.lower() else "us"
    url = f"https://{region}.posthog.com/api/projects/{pid}/query/"
    body = json.dumps({"query": {"kind": "HogQLQuery", "query": query}}).encode()
    try:
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()).get("results", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        log(f"HogQL failed ({e})")
        return None


# Canonical happy-path stage -> events. Keys MUST match funnelCurated stages.
FUNNEL_STAGES = [
    ("land",     ["$pageview"]),
    ("engage",   ["cta_clicked", "book_call_clicked", "surprise_me_clicked"]),
    ("intent",   ["signup_modal_opened"]),
    ("signup",   ["signup_completed"]),
    ("studio",   ["studio_entered"]),
    ("model",    ["model_generated"]),
    ("import",   ["product_imported", "product_url_submitted", "product_scrape_succeeded"]),
    ("tryon",    ["tryon_completed"]),
    ("download", ["result_downloaded", "results_downloaded_all"]),
    ("pricing",  ["pricing_plan_clicked"]),
    ("checkout", ["checkout_started"]),
]


def fetch_funnel(env, base):
    """Overlay live per-stage reach (4 windows) + the same-user activation
    spine onto the curated funnel block. Returns the curated base unchanged
    if PostHog is unreachable."""
    all_events = sorted({e for _, evs in FUNNEL_STAGES for e in evs})
    ev_list = ", ".join(f"'{e}'" for e in all_events)
    cases = []
    for key, evs in FUNNEL_STAGES:
        cond = (f"event = '{evs[0]}'" if len(evs) == 1
                else "event IN (" + ", ".join(f"'{e}'" for e in evs) + ")")
        cases.append(f"{cond}, '{key}'")
    multi = "multiIf(" + ", ".join(cases) + ", 'other')"
    reach_q = f"""
        SELECT stage,
          count(DISTINCT if(timestamp >= now() - INTERVAL 7 DAY, person_id, NULL)) AS d7,
          count(DISTINCT if(timestamp >= now() - INTERVAL 30 DAY, person_id, NULL)) AS d30,
          count(DISTINCT if(timestamp >= now() - INTERVAL 90 DAY, person_id, NULL)) AS d90,
          count(DISTINCT person_id) AS dall
        FROM (
          SELECT person_id, timestamp, {multi} AS stage
          FROM events
          WHERE timestamp >= now() - INTERVAL 365 DAY AND event IN ({ev_list})
        )
        WHERE stage != 'other'
        GROUP BY stage
    """.strip()
    rows = _hogql(env, reach_q)
    if not rows:
        return base

    counts = {r[0]: {"d7": int(r[1]), "d30": int(r[2]), "d90": int(r[3]), "all": int(r[4])}
              for r in rows if r and r[0]}

    spine_q = """
        SELECT countIf(s>0) a, countIf(s>0 AND en>0) b, countIf(s>0 AND mo>0) c,
               countIf(s>0 AND im>0) d, countIf(s>0 AND ty>0) e, countIf(s>0 AND dl>0) f,
               countIf(s>0 AND pr>0) g, countIf(s>0 AND ch>0) h
        FROM (
          SELECT person_id,
            maxIf(1, event='signup_completed') s, maxIf(1, event='studio_entered') en,
            maxIf(1, event='model_generated') mo,
            maxIf(1, event IN ('product_imported','product_url_submitted')) im,
            maxIf(1, event='tryon_completed') ty,
            maxIf(1, event IN ('result_downloaded','results_downloaded_all')) dl,
            maxIf(1, event='pricing_plan_clicked') pr, maxIf(1, event='checkout_started') ch
          FROM events WHERE timestamp >= now() - INTERVAL 365 DAY GROUP BY person_id
        )
    """.strip()
    spine_rows = _hogql(env, spine_q)

    import copy
    funnel = copy.deepcopy(base)
    funnel["source"] = "PostHog · live HogQL"
    funnel["updated"] = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    for stage in funnel.get("stages", []):
        c = counts.get(stage["key"])
        if c:
            stage["counts"] = c

    if spine_rows and spine_rows[0]:
        v = [int(x) for x in spine_rows[0]]
        denom = v[0] or 1
        steps = funnel.get("spine", {}).get("steps", [])
        for i, step in enumerate(steps):
            if i < len(v):
                step["count"] = v[i]
                step["pct"] = round(v[i] / denom * 100)
        funnel["spine"]["denominator"] = v[0]
    log(f"PostHog funnel: {len(counts)} stages live")
    return funnel


def fetch_signup_methods(env):
    """Distinct persons who completed signup, split by auth method
    (magic_link / google / password). signup_completed.method already
    attributes each signup, so this is clean with no extra instrumentation.
    It's the live measure behind the auth-mix line in the Overview's Current
    Focus. Returns {'magic_link': int, 'google': int, ...} or None on failure
    (curated fallbacks in content.json then keep the narrative intact).

    NOTE: prefer this over a magic_link_requested join — that event undercounts
    (more people sign up via magic link than fire the requested event: 45 vs
    24 as of 2026-06-03), which made the email path look far leakier than it is."""
    q = """
        SELECT properties.method AS method, count(DISTINCT person_id) AS n
        FROM events
        WHERE event='signup_completed' AND timestamp >= now() - INTERVAL 365 DAY
        GROUP BY properties.method
    """.strip()
    rows = _hogql(env, q)
    if not rows:
        return None
    out = {}
    for r in rows:
        if r and r[0] is not None:
            try:
                out[str(r[0])] = int(r[1])
            except (ValueError, TypeError, IndexError):
                continue
    if not out:
        return None
    log(f"PostHog signup methods: {out}")
    return out


# Fill {{key|fallback}} placeholders from a vars dict. Missing or None values
# fall back to the inline literal, so curated prose survives a failed live pull.
_TPL_RE = re.compile(r"\{\{(\w+)\|([^}]*)\}\}")


def apply_template_vars(text, variables):
    def repl(m):
        v = variables.get(m.group(1))
        return str(v) if v is not None else m.group(2)
    return _TPL_RE.sub(repl, text)


def bind_current_focus(content, funnel, methods):
    """Bind the live funnel figures into the Overview's curated Current Focus
    so it can never silently drift from the Funnel tab. Reads the same `funnel`
    object the site renders (which itself falls back to the curated block), plus
    the live signup auth-mix. Pure string substitution over {{key|fallback}}."""
    def stage_all(key):
        for s in funnel.get("stages", []):
            if s.get("key") == key:
                return (s.get("counts") or {}).get("all")
        return None

    intent, signup = stage_all("intent"), stage_all("signup")
    studio, model = stage_all("studio"), stage_all("model")
    methods = methods or {}
    variables = {
        "intent": intent,
        "signup": signup,
        "signupPct": round(signup / intent * 100) if intent and signup is not None else None,
        "studio": studio,
        "model": model,
        "studioNoModelPct": round((studio - model) / studio * 100) if studio and model is not None else None,
        "mlSignups": methods.get("magic_link"),
        "googleSignups": methods.get("google"),
    }
    cf = content.get("overview", {}).get("currentFocus")
    if isinstance(cf, list):
        content["overview"]["currentFocus"] = [apply_template_vars(s, variables) for s in cf]


# ------------------------------------------------------------------- Klaviyo --
KLAVIYO_REV = "2024-10-15"
TRYON_METRIC = "T3S8Cw"  # 'Try-on Completed' — the aha, used as flow conversion metric


def _klaviyo(key, path, method="GET", body=None):
    url = f"https://a.klaviyo.com/api/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Klaviyo-API-Key {key}",
        "revision": KLAVIYO_REV, "accept": "application/json",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def fetch_lifecycle(env, base):
    """Overlay live Klaviyo state (flow statuses, the live Ablo flow's
    messages, prepared lifecycle templates) onto the curated lifecycle block.
    Analysis fields (opportunities, note, message 'read') stay curated."""
    key = env.get("KLAVIYO_API_KEY_ABLO")
    if not key:
        return base
    import copy
    life = copy.deepcopy(base)
    try:
        flows = _klaviyo(key, "flows/?fields%5Bflow%5D=name,status,trigger_type,created&page%5Bsize%5D=50").get("data", [])
    except Exception as e:
        log(f"Klaviyo flows failed ({e})")
        return base

    live_ablo, draft_ablo, other = [], [], []
    for f in flows:
        a = f.get("attributes", {})
        name, status = a.get("name", ""), a.get("status", "")
        low = name.lower()
        if any(x in low for x in ("clawoop", "launchpad", "christmas", "essential flow")):
            other.append(name)
        elif status == "live" and "ablo" in low:
            entry = {"flow": name, "id": f.get("id"), "trigger": a.get("triggerType", ""),
                     "since": _short_date(a.get("created", "")), "status": "live"}
            # Pre-seed messages/read/agg from the curated match so the card
            # always renders even if the live report overlay misses.
            cm = next((x for x in base.get("liveFlows", []) if x.get("id") == entry["id"]), None)
            if cm:
                entry["messages"] = cm.get("messages", [])
                entry["read"] = cm.get("read", "")
                entry["agg"] = cm.get("agg", {})
            live_ablo.append(entry)
        elif status == "draft" and ("ablo" in low or "welcome series" in low):
            draft_ablo.append({"name": name, "trigger": a.get("triggerType", ""), "status": "draft",
                               "note": "Built but never turned on."})

    # Per-message performance for each live Ablo flow (best-effort).
    for lf in live_ablo:
        try:
            report = _klaviyo(key, "flow-values-reports/", "POST", {
                "data": {"type": "flow-values-report", "attributes": {
                    "statistics": ["recipients", "open_rate", "click_rate", "conversions", "conversion_uniques", "unsubscribes"],
                    "timeframe": {"key": "last_90_days"},
                    "conversion_metric_id": TRYON_METRIC,
                    "filter": f"equals(flow_id,\"{lf['id']}\")",
                    "group_by": ["flow_id", "flow_message_id", "flow_message_name"],
                }}})
            results = report.get("data", {}).get("attributes", {}).get("results", [])
            agg = report.get("data", {}).get("attributes", {}).get("flow_aggregation", [])
            msgs, seen = [], {}
            for r in results:
                g, s = r.get("groupings", {}), r.get("statistics", {})
                nm = g.get("flow_message_name", "Message")
                if s.get("recipients", 0) < 2:
                    continue  # skip stray test variations
                seen[nm] = seen.get(nm, 0) + 1
                msgs.append({"name": nm, "timing": "—",
                             "recipients": int(s.get("recipients", 0)),
                             "open": round(s.get("open_rate", 0) * 100, 1),
                             "click": round(s.get("click_rate", 0) * 100, 1),
                             "conv": round(s.get("conversion_rate", 0) * 100, 1),
                             "unsub": int(s.get("unsubscribes", 0))})
            # Curated message structure is authoritative (it reflects the intended
            # A/B/C stages). Overlay live per-message stats by name match, so a flow
            # that was just relaunched shows the right emails, not stale historical
            # sends (e.g. the repurposed Activate flow's old onboarding messages).
            curated_msgs = next((x.get("messages", []) for x in base.get("liveFlows", [])
                                 if x.get("id") == lf["id"]), [])
            lf["read"] = next((x.get("read", "") for x in base.get("liveFlows", [])
                               if x.get("id") == lf["id"]), lf.get("read", ""))
            if curated_msgs:
                merged = []
                for cm in curated_msgs:
                    e = dict(cm)
                    tok = cm.get("name", "").split("·")[0].strip().lower()
                    live_m = next((m for m in msgs if tok and tok in m.get("name", "").lower()), None)
                    if live_m:
                        for k in ("recipients", "open", "click", "conv", "unsub"):
                            e[k] = live_m.get(k, 0)
                    merged.append(e)
                lf["messages"] = merged
            elif msgs:
                lf["messages"] = msgs
            if agg:
                s = agg[0].get("statistics", {})
                lf["agg"] = {"recipients": int(s.get("recipients", 0)),
                             "open": round(s.get("open_rate", 0) * 100, 1),
                             "click": round(s.get("click_rate", 0) * 100, 1),
                             "conv": int(s.get("conversions", 0)),
                             "convUniques": int(s.get("conversion_uniques", 0)),
                             "convLabel": "Try-on completed"}
        except Exception as e:
            log(f"Klaviyo flow report failed for {lf['id']} ({e}); keeping curated messages")
            cm = next((x for x in base.get("liveFlows", []) if x.get("id") == lf["id"]), None)
            if cm:
                lf["messages"], lf["read"], lf["agg"] = cm.get("messages", []), cm.get("read", ""), cm.get("agg", {})

    if live_ablo:
        life["liveFlows"] = live_ablo
    # The A/B/C emails are now wired into the live flows, so the "built but unwired"
    # (prepared) concept is obsolete; leave it as the curated block has it (empty).
    if draft_ablo:
        life["draftFlows"] = draft_ablo
    if other:
        life["otherProduct"] = sorted(set(other))
    life["source"] = "Klaviyo · live API"
    life["updated"] = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    log(f"Klaviyo: {len(live_ablo)} live flow(s) (A/B/C wired)")
    return life


# ------------------------------------------------------------------ ClickUp --
ABLO_STUDIO_LIST = "901415977874"  # ClickUp · Space Runners (Ablo) · "Ablo Studio" list


def fetch_clickup(env):
    """Live task feed from the Ablo Studio ClickUp list (source of truth for
    action items). Read-only. None on failure."""
    key = env.get("CLICKUP_TOKEN_ABLO")
    if not key:
        return None
    # include_closed=true so the queue reconciler can see completed tasks (a card
    # whose work is done in ClickUp should auto-flag, even though the visible feed
    # below only lists the still-open tasks).
    url = (f"https://api.clickup.com/api/v2/list/{ABLO_STUDIO_LIST}/task"
           "?archived=false&include_closed=true&subtasks=false&order_by=due_date")
    try:
        req = urllib.request.Request(url, headers={"Authorization": key})
        with urllib.request.urlopen(req, timeout=30) as r:
            tasks = json.loads(r.read().decode()).get("tasks", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        log(f"ClickUp fetch failed ({e})")
        return None

    counts, rows = {}, []
    for t in tasks:
        st = (t.get("status") or {}).get("status", "unknown")
        counts[st] = counts.get(st, 0) + 1
        due = t.get("due_date")
        rows.append({
            "name": t.get("name", ""),
            "status": st,
            "color": (t.get("status") or {}).get("color", ""),
            "type": (t.get("status") or {}).get("type", ""),
            "url": t.get("url", ""),
            "due": _short_date(datetime.fromtimestamp(int(due) / 1000, timezone.utc).isoformat()) if due else "",
            "assignee": (t.get("assignees") or [{}])[0].get("username", "").strip() if t.get("assignees") else "",
        })
    # surface in-progress first, then to-do, capped — the live execution layer
    order = {"in progress": 0, "to do": 1}
    active = [r for r in rows if r["type"] != "closed" and r["type"] != "done"]
    active.sort(key=lambda r: (order.get(r["status"], 2), r["due"] or "9"))
    log(f"ClickUp: {len(tasks)} task(s) · {counts}")
    # `all` is the full compact pool (open + closed) used only by the reconciler;
    # it is popped before the clickup block is embedded in data.js.
    return {"source": "ClickUp · live", "updated": datetime.now(timezone.utc).strftime("%B %-d, %Y"),
            "listUrl": f"https://app.clickup.com/9003194404/v/li/{ABLO_STUDIO_LIST}",
            "counts": counts, "open": active[:12], "total": len(tasks),
            "all": [{"name": r["name"], "status": r["status"], "type": r["type"], "url": r["url"]} for r in rows]}


# -------------------------------------------------------------- Instagram ----
IG_ACCOUNT = "17841404306089983"  # @ablo.ai business account


def fetch_instagram(env):
    """Live Instagram organic stats via the Meta Graph API (the ads token has
    account-read scope). Post-level engagement + publishing need an IG token
    with instagram_content_publish — currently expired. None on failure."""
    token = env.get("META_ADS_TOKEN")
    if not token:
        return None
    url = (f"https://graph.facebook.com/v21.0/{IG_ACCOUNT}"
           f"?fields=username,followers_count,media_count&access_token={token}")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.loads(r.read().decode())
        if "error" in d:
            return None
        log(f"Instagram: @{d.get('username')} {d.get('followers_count')} followers")
        return {"username": d.get("username"), "followers": d.get("followers_count"),
                "posts": d.get("media_count"), "source": "Meta Graph · live",
                "canPost": False, "postNote": "Posting + post-level engagement need an IG token with instagram_content_publish scope (the META_IG_TOKEN is expired, refresh it to enable agent posting)."}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        log(f"Instagram fetch failed ({e})")
        return None


# ------------------------------------------------------------- conversions ---
def fetch_paying(env):
    """Distinct Studio self-serve paying customers, from the PostHog purchase
    event. That event only fires inside Studio, so it is inherently scoped to
    self-serve, no Stripe charge filtering needed. None on failure (KPI then
    falls back to its curated value)."""
    try:
        rows = _hogql(env, "SELECT count(DISTINCT person_id) FROM events WHERE event = 'purchase_completed'")
    except Exception as e:  # noqa: BLE001 -- never let a slow/failed pull crash the build
        log(f"Conversions fetch failed ({e}); KPI falls back to curated")
        return None
    if not rows:
        return None
    try:
        paying = int(rows[0][0])
    except (IndexError, TypeError, ValueError):
        return None
    log(f"Conversions: {paying} paying customer(s) via PostHog purchase_completed")
    return paying


# ----------------------------------------------------------------- channels --
CHANNEL_Q = """
SELECT coalesce(nullIf(properties.utm_source, ''), '(direct)') AS source,
  count(DISTINCT person_id) AS users,
  count(DISTINCT if(event = 'signup_completed', person_id, NULL)) AS signups,
  count(DISTINCT if(event = 'tryon_completed', person_id, NULL)) AS tryons,
  count(DISTINCT if(event = 'checkout_started', person_id, NULL)) AS checkouts
FROM events
WHERE timestamp >= toDateTime('2026-05-01 00:00:00')
GROUP BY source
""".strip()


def _channel_name(src):
    s = (src or "").lower()
    if "meta" in s or s in ("fb", "facebook"):
        return "Meta Ads"
    if "linkedin" in s:
        return "LinkedIn"
    if s in ("ig", "instagram"):
        return "Instagram (organic)"
    if "google" in s or "adwords" in s:
        return "Google"
    if "email" in s or "klaviyo" in s:
        return "Email"
    if "direct" in s:
        return "Direct / untagged"
    return (src or "Other").title()


def fetch_channel_attribution(env):
    """Live per-channel acquisition from PostHog UTM stamps, tied through to
    signups, try-ons and checkouts. None on failure."""
    rows = _hogql(env, CHANNEL_Q)
    if not rows:
        return None
    agg = {}
    for r in rows:
        if not r:
            continue
        name = _channel_name(r[0])
        a = agg.setdefault(name, {"channel": name, "users": 0, "signups": 0, "tryons": 0, "checkouts": 0})
        a["users"] += int(r[1]); a["signups"] += int(r[2]); a["tryons"] += int(r[3]); a["checkouts"] += int(r[4])
    chans = sorted(agg.values(), key=lambda x: x["signups"], reverse=True)
    total_su = sum(c["signups"] for c in chans) or 1
    for c in chans:
        c["signupShare"] = round(c["signups"] / total_su * 100)
    top = chans[0] if chans else None
    insight = ""
    if top and top["signupShare"] >= 40:
        insight = (f"{top['signupShare']}% of signups come from {top['channel']}"
                   + (" — acquisition is dominated by untagged / organic traffic, not paid. "
                      "Tag founder posts and referral links with UTMs to see what is really working, "
                      "and weigh whether paid is earning its share."
                      if top["channel"].startswith("Direct") else "."))
    log(f"PostHog channels: {len(chans)} source(s), top {top['channel'] if top else '-'}")
    return {"attribution": chans, "insight": insight,
            "updated": datetime.now(timezone.utc).strftime("%B %-d, %Y"), "source": "PostHog UTM · live"}


# ------------------------------------------------------------ landing pages --
# Per-entry-page conversion (the visitor's FIRST $pageview pathname -> did they
# engage, did they sign up). This is what makes top-of-funnel CRO measurable: an
# aggregate "land -> engage" rate hides WHICH page bleeds the visit. With this,
# a homepage rewrite or a paid landing-page variant is a per-page, testable bet
# instead of a hunch. argMinIf picks the earliest pageview path per person.
LANDING_Q = """
SELECT entry, count() AS visitors,
  countIf(eng > 0) AS engagers,
  countIf(sig > 0) AS signups
FROM (
  SELECT person_id,
    argMinIf(properties.$pathname, timestamp, event = '$pageview') AS entry,
    maxIf(1, event IN ('cta_clicked','surprise_me_clicked','book_call_clicked')) AS eng,
    maxIf(1, event = 'signup_completed') AS sig
  FROM events
  WHERE timestamp >= now() - INTERVAL 60 DAY
    AND event IN ('$pageview','cta_clicked','surprise_me_clicked','book_call_clicked','signup_completed')
  GROUP BY person_id
)
WHERE entry != ''
GROUP BY entry
HAVING visitors >= 5
ORDER BY visitors DESC
LIMIT 30
""".strip()

# Entry paths that are app/auth surfaces, not marketing landing pages. Excluded
# from the "which landing page converts" read so they do not muddy CRO targeting
# (e.g. /auth/verify shows a fake-high signup rate — those visitors were already
# mid-signup when they hit it).
_NON_LANDING = {"/auth/verify", "/auth", "/login", "/studio", "/app"}

# The /try value-first flow fires its OWN event taxonomy (tbs_* = "try before
# signup") and stitches anonymous->identified at signup. Keying its conversion to
# the first-pageview pathname (LANDING_Q) undercounts it badly: that attribution
# caught ~2 of 24 real signup-wall reaches and credited /try signups to other entry
# pages, reading a fake 1.5%. Re-measure /try by its TRUE cohort: everyone whose
# entry signal is tbs_page_viewed, counted through the tbs_* steps. Signups stay a
# floor (a signup under a split identified id can fall outside the cohort), but far
# truer than the pathname read. See ClickUp 86ba2wp4t.
# Per-event distinct reach (NOT intersected on one person set): the /try flow is
# anonymous and PostHog re-splits person_ids across steps, so intersecting deeper
# steps with the tbs_page_viewed set silently drops most of them (it read generate=5
# when the real reach is 25). We count each step's own distinct-user reach, and scope
# signup_completed to anyone who fired any tbs_* event. The intermediate "customize"
# step (a 4-event union) over-counts under the same fragmentation, so it is dropped;
# the reliable, monotonic spine is land -> generate -> signup-wall -> signup.
TRY_COHORT_Q = """
SELECT
  count(DISTINCT if(event = 'tbs_page_viewed', person_id, NULL)) AS landed,
  count(DISTINCT if(event = 'tbs_generate_clicked', person_id, NULL)) AS generated,
  count(DISTINCT if(event = 'tbs_signup_wall_shown', person_id, NULL)) AS hit_wall,
  count(DISTINCT if(event = 'signup_completed', person_id, NULL)) AS signed
FROM events
WHERE timestamp >= now() - INTERVAL 60 DAY
  AND ( event LIKE 'tbs_%'
        OR (event = 'signup_completed' AND person_id IN (
            SELECT DISTINCT person_id FROM events
            WHERE timestamp >= now() - INTERVAL 60 DAY AND event LIKE 'tbs_%')) )
""".strip()


def _correct_try_row(env, pages):
    """Overwrite the /try row in `pages` with its true tbs_* cohort funnel (see
    TRY_COHORT_Q), so every downstream read (Funnel tab, the /try experiment, the
    CRO insight) uses the honest number instead of the pathname-attribution artifact.
    Mutates `pages` in place; returns the funnel dict, or None on failure / no data
    so the build degrades gracefully instead of crashing."""
    rows = _hogql(env, TRY_COHORT_Q)
    if not rows or not rows[0]:
        return None
    try:
        landed, generated, hit_wall, signed = [int(x) for x in rows[0]]
    except (ValueError, TypeError):
        return None
    if landed <= 0:
        return None
    # Defensive monotonic clamp: fragmentation could in principle push a downstream
    # step above its parent; keep the displayed funnel sane (no-op on healthy data).
    generated = min(generated, landed)
    hit_wall = min(hit_wall, generated)
    signed = min(signed, landed)
    corrected = {
        "path": "/try", "visitors": landed, "engagers": generated, "signups": signed,
        "engagePct": round(generated / landed * 100, 1),
        "signupPct": round(signed / landed * 100, 1),
        "isLanding": True, "measure": "tbs-cohort",
        "note": ("measured by the tbs_* cohort (entry = tbs_page_viewed) reach, not "
                 "first-pageview pathname; signups are a floor (anon->identified split "
                 "may hide a few). ClickUp 86ba2wp4t."),
    }
    row = next((p for p in pages if p.get("path") == "/try"), None)
    if row:
        row.update(corrected)
    else:
        pages.append(corrected)
    log(f"try-correction: /try true funnel {landed} land -> {generated} generate -> "
        f"{hit_wall} wall -> {signed} signup ({corrected['signupPct']}% view->signup)")
    return {"landed": landed, "generated": generated, "hitWall": hit_wall, "signed": signed}


def fetch_landing_pages(env):
    """Live per-landing-page bounce + signup conversion from PostHog. None on
    failure. Surfaces the worst-converting high-volume entry page so the daily
    routine targets homepage / landing CRO with data, not a hunch."""
    rows = _hogql(env, LANDING_Q)
    if not rows:
        return None
    pages = []
    for r in rows:
        if not r or not r[0]:
            continue
        path, visitors = r[0], int(r[1])
        engagers, signups = int(r[2]), int(r[3])
        pages.append({
            "path": path, "visitors": visitors,
            "engagers": engagers, "signups": signups,
            "engagePct": round(engagers / visitors * 100, 1) if visitors else 0,
            "signupPct": round(signups / visitors * 100, 1) if visitors else 0,
            "isLanding": path not in _NON_LANDING,
        })
    # Correct the /try row to its true tbs_* cohort BEFORE the insight is computed,
    # so the CRO read never quotes the pathname-attribution artifact.
    try_funnel = _correct_try_row(env, pages)
    # Read the leak: among real-volume marketing landing pages (>= 20 visitors),
    # call out the homepage and the best/worst landing-page conversion. The
    # worst/best contrast only uses pages that actually drive signup (>= 1 signup)
    # so a no-signup-by-design path like /try (the anonymous try-on flow) can't
    # masquerade as the worst CRO target. A 2x gap between two functioning paid
    # landing pages is proof the page, not the ad, is the lever.
    landing = [p for p in pages if p["isLanding"] and p["visitors"] >= 20]
    convertible = [p for p in landing if p["signups"] >= 1]
    insight = ""
    if landing:
        home = next((p for p in landing if p["path"] == "/"), None)
        bits = []
        if home:
            bits.append(f"Homepage takes {home['visitors']} visitors but only "
                        f"{home['engagePct']}% click any CTA and {home['signupPct']}% sign up")
        if len(convertible) >= 2:
            worst = min(convertible, key=lambda p: p["signupPct"])
            best = max(convertible, key=lambda p: p["signupPct"])
            if worst is not best and worst["signupPct"] * 2 <= best["signupPct"]:
                bits.append(f"{worst['path']} converts {worst['signupPct']}% to signup vs "
                            f"{best['path']} at {best['signupPct']}%, so the landing page, not "
                            f"the ad, is the leak — a clean CRO test")
        insight = ". ".join(bits) + ("." if bits else "")
    log(f"PostHog landing pages: {len(pages)} entry page(s) read")
    return {"pages": pages, "insight": insight, "window": "60d", "tryFunnel": try_funnel,
            "updated": datetime.now(timezone.utc).strftime("%B %-d, %Y"),
            "source": "PostHog · live HogQL (first-pageview pathname; /try via tbs_* cohort)"}


# ------------------------------------------------------------------ history --
# Daily distinct-user reach per stage, reconstructed in full from the PostHog
# event log on every run (self-healing — no drift, no dedupe needed). Non-
# reconstructable fields (Meta cost, email rates, cumulative rates) are
# persisted forward from today in history.jsonl.
DAILY_Q = """
SELECT toString(toDate(timestamp)) AS d,
  count(DISTINCT if(event = '$pageview', person_id, NULL)) AS landed,
  count(DISTINCT if(event IN ('cta_clicked','book_call_clicked','surprise_me_clicked'), person_id, NULL)) AS engaged,
  count(DISTINCT if(event = 'signup_modal_opened', person_id, NULL)) AS modal,
  count(DISTINCT if(event = 'signup_completed', person_id, NULL)) AS signups,
  count(DISTINCT if(event = 'model_generated', person_id, NULL)) AS models,
  count(DISTINCT if(event IN ('product_imported','product_url_submitted'), person_id, NULL)) AS imports,
  count(DISTINCT if(event = 'tryon_completed', person_id, NULL)) AS tryons,
  count(DISTINCT if(event IN ('result_downloaded','results_downloaded_all'), person_id, NULL)) AS downloads,
  count(DISTINCT if(event = 'checkout_started', person_id, NULL)) AS checkouts
FROM events
WHERE timestamp >= toDateTime('2026-05-19 00:00:00')
GROUP BY d ORDER BY d
""".strip()

# Fields that cannot be recomputed from the event log — persisted day by day.
PERSIST_KEYS = ["spend_lifetime", "cpl", "signups_meta", "email_open", "email_click",
                "email_recipients", "aha_rate", "activation_rate", "payment_rate",
                "paying_customers", "ig_followers", "home_engage_pct", "home_signup_pct"]
PH_COLS = ["landed", "engaged", "modal", "signups", "models", "imports", "tryons", "downloads", "checkouts"]


def _money(s):
    try:
        return round(float(str(s).replace("$", "").replace(",", "")), 2)
    except (ValueError, TypeError, AttributeError):
        return None


def snapshot_history(env, funnel, meta_live, lifecycle, instagram=None, paying=None, landing=None):
    """Upsert today's row and rewrite history.jsonl. Returns the last 120 days
    for embedding. PostHog reach is recomputed in full; Meta/Klaviyo/rate
    fields persist forward (incl. the homepage top-of-funnel CRO rates, so the
    land->engage / land->signup leak is trendable over time)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1) PostHog daily reach (full history, authoritative)
    rows_ph = _hogql(env, DAILY_Q) or []
    ph = {}
    for r in rows_ph:
        if r and r[0]:
            ph[r[0]] = {PH_COLS[i]: int(r[i + 1]) for i in range(len(PH_COLS))}

    # 2) read previously persisted (non-reconstructable) fields
    persisted = {}
    if HISTORY.exists():
        for line in HISTORY.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            d = row.get("date")
            if d:
                persisted[d] = {k: row[k] for k in PERSIST_KEYS if row.get(k) is not None}

    # 3) today's persisted fields from the live pulls
    rates = {}
    for s in (funnel.get("spine", {}) or {}).get("steps", []):
        lab = (s.get("label", "") or "").lower()
        if s.get("aha"):
            rates["aha_rate"] = s.get("pct")
        elif s.get("payment"):
            rates["payment_rate"] = s.get("pct")
        elif "model" in lab:
            rates["activation_rate"] = s.get("pct")
    agg = ((lifecycle.get("liveFlows") or [{}])[0] or {}).get("agg", {})
    today_fields = {
        "spend_lifetime": _money(meta_live.get("spend")),
        "cpl": _money(meta_live.get("cpl")),
        "signups_meta": meta_live.get("signups"),
        "email_open": agg.get("open"),
        "email_click": agg.get("click"),
        "email_recipients": agg.get("recipients"),
        # Real paying-customer count (PostHog purchase_completed). None on a failed
        # pull -> dropped below so the prior day's value persists (never overwrite
        # a real count with a placeholder 0).
        "paying_customers": paying,
        "ig_followers": (instagram or {}).get("followers"),
        **rates,
    }
    # Homepage top-of-funnel CRO rates (stable, highest-volume entry page) persisted
    # today-forward so the land->engage / land->signup leak trends in history + Trends.
    if landing:
        home = next((p for p in (landing.get("pages") or []) if p.get("path") == "/"), None)
        if home:
            today_fields["home_engage_pct"] = home.get("engagePct")
            today_fields["home_signup_pct"] = home.get("signupPct")
    persisted[today] = {k: v for k, v in today_fields.items() if v is not None}

    # 4) merge across the union of dates and rewrite
    dates = sorted(set(ph) | set(persisted))
    rows = []
    for d in dates:
        row = {"date": d}
        row.update(ph.get(d, {}))
        row.update(persisted.get(d, {}))
        rows.append(row)
    HISTORY.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    log(f"history: {len(rows)} day(s) ({dates[0] if dates else '-'} → {today})")
    return {"rows": rows[-120:], "updated": today, "phLive": bool(rows_ph)}


# Spend from finished ad flights. The autopilot's spend_lifetime is the CURRENT
# flight only and resets to ~0 when a new flight starts, so a day where it drops
# vs the prior day marks a closed flight; the prior day's value was that flight's
# final spend. This auto-accumulates closed flights from history -- no manual
# bumping ever. PRE_HISTORY covers flights that closed before history.jsonl began
# (a fixed historical fact that never changes).
CLOSED_FLIGHTS_PRE_HISTORY = 631.32

# LinkedIn ad spend is pulled LIVE from the Marketing API (see fetch_linkedin_spend).
# This constant is only the FALLBACK shown if the API/token is unavailable (a
# defensible last-known total of the Wave 1 + Wave 2 promoted posts).
LINKEDIN_CLOSED_SPEND = 450.0
LINKEDIN_VERSION = "202506"  # LinkedIn API version (YYYYMM); bump when LinkedIn sunsets it


# ----------------------------------------------------------------- LinkedIn ----
def _update_env_keys(path, kv):
    """Rewrite ~/.claude/.env, replacing the given keys (export KEY='val'), 0600."""
    lines = path.read_text().splitlines() if path.exists() else []
    kept = [l for l in lines
            if not any(re.match(rf"\s*(export\s+)?{k}=", l) for k in kv)]
    for k, v in kv.items():
        kept.append(f"export {k}='{v}'")
    new_text = "\n".join(kept) + "\n"
    if path.exists():
        # Back up the master secret file before rewriting it (rolling .bak, 0600),
        # and refuse to write if the rewrite would silently drop any unrelated key.
        bak = path.parent / (path.name + ".bak")
        bak.write_text(path.read_text()); os.chmod(bak, 0o600)
        def _keys(text):
            out = set()
            for ln in text.splitlines():
                m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=", ln)
                if m:
                    out.add(m.group(1))
            return out
        dropped = _keys("\n".join(lines)) - _keys(new_text) - set(kv)
        if dropped:
            raise RuntimeError(f"env rewrite would drop keys {sorted(dropped)}; aborted (backup at {bak})")
    path.write_text(new_text)
    os.chmod(path, 0o600)


def _linkedin_refresh(env):
    """Mint a fresh access token from the stored refresh token; persist it. None on failure."""
    rt, cid, cs = env.get("LINKEDIN_REFRESH_TOKEN"), env.get("LINKEDIN_CLIENT_ID"), env.get("LINKEDIN_CLIENT_SECRET")
    if not (rt and cid and cs):
        return None
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": rt,
        "client_id": cid, "client_secret": cs,
    }).encode()
    try:
        req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken",
            data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        log(f"LinkedIn token refresh failed ({e})")
        return None
    at = resp.get("access_token")
    if not at:
        return None
    updates = {"LINKEDIN_ADS_TOKEN": at}
    if resp.get("refresh_token"):  # LinkedIn rotates refresh tokens
        updates["LINKEDIN_REFRESH_TOKEN"] = resp["refresh_token"]
    _update_env_keys(ENV_FILE, updates)
    env.update(updates)
    log("LinkedIn: access token auto-refreshed")
    return at


def fetch_linkedin_spend(env):
    """Lifetime LinkedIn ad spend (all campaigns) via the Marketing API adAnalytics
    endpoint. Auto-refreshes the token on 401. Returns a float, or None on any
    failure (caller falls back to LINKEDIN_CLOSED_SPEND)."""
    tok, acct = env.get("LINKEDIN_ADS_TOKEN"), env.get("LINKEDIN_AD_ACCOUNT_ID")
    if not tok or not acct:
        return None
    acct_urn = f"urn:li:sponsoredAccount:{acct}".replace(":", "%3A")
    q = ("q=analytics&pivot=ACCOUNT&timeGranularity=ALL"
         "&dateRange=(start:(year:2024,month:1,day:1),end:(year:2030,month:12,day:31))"
         f"&accounts=List({acct_urn})&fields=costInLocalCurrency")
    url = "https://api.linkedin.com/rest/adAnalytics?" + q

    def _call(token):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    try:
        data = _call(tok)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):  # expired/invalid token -> refresh once and retry
            tok = _linkedin_refresh(env)
            if not tok:
                return None
            try:
                data = _call(tok)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
                return None
        else:
            log(f"LinkedIn spend fetch failed (HTTP {e.code})")
            return None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log(f"LinkedIn spend fetch failed ({e})")
        return None

    els = data.get("elements", [])
    if not els:
        return None
    total = round(sum(float(e.get("costInLocalCurrency", 0) or 0) for e in els), 2)
    log(f"LinkedIn: ${total:,.2f} lifetime spend (live)")
    return total


def _closed_flights_spend(history_rows):
    total = CLOSED_FLIGHTS_PRE_HISTORY
    prev = None
    for r in history_rows:
        s = r.get("spend_lifetime")
        if s is None:
            continue
        try:
            s = float(s)
        except (TypeError, ValueError):
            continue
        if prev is not None and s < prev - 0.01:  # spend dropped = new flight = prior flight closed
            total += prev
        prev = s
    return total


# ----------------------------------------------------------------- learning --
# Self-improvement memory. state/lessons.jsonl is an append-only, git-tracked
# ledger the marketing-os-refresh agent writes: falsifiable `prediction` records
# and durable `lesson` records. build.py reads it back so every run starts with
# what past runs learned, computes the agent's calibration (were its bets right?),
# and flags predictions whose horizon has elapsed and need resolving. This is the
# deterministic surfacing half of the predict→observe→score→learn loop; the agent
# does the judging. Degrades to an empty structure if the ledger is missing.
LESSONS = HERE / "state" / "lessons.jsonl"

_VERDICT_PTS = {"hit": 1.0, "partial": 0.5, "miss": 0.0}


def load_learning(today=None):
    out = {
        "lessons": [],
        "openPredictions": [],
        "dueForReview": [],
        "calibration": {"n": 0, "hits": 0, "hitRate": None},
        "counts": {"lessons": 0, "predictions": 0, "resolved": 0, "open": 0},
    }
    if not LESSONS.exists():
        return out
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lessons, preds = [], []
    for line in LESSONS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            log(f"lessons.jsonl: skipped unparseable line")
            continue
        kind = rec.get("type")
        if kind == "lesson":
            lessons.append(rec)
        elif kind == "prediction":
            preds.append(rec)

    lessons.sort(key=lambda r: r.get("date", ""), reverse=True)
    open_preds = [p for p in preds if p.get("status") == "open"]
    resolved = [p for p in preds if p.get("status") == "resolved"]

    pts = [_VERDICT_PTS[p["verdict"]] for p in resolved if p.get("verdict") in _VERDICT_PTS]
    n = len(pts)
    hits = sum(1 for p in resolved if p.get("verdict") == "hit")

    out["lessons"] = lessons[:12]
    out["openPredictions"] = sorted(open_preds, key=lambda p: p.get("due", "9999"))
    # A bet whose horizon has elapsed but is still open: the agent must resolve it.
    out["dueForReview"] = [p for p in open_preds if p.get("due", "9999") <= today]
    out["calibration"] = {
        "n": n,
        "hits": hits,
        "hitRate": round(sum(pts) / n, 2) if n else None,
    }
    out["counts"] = {
        "lessons": len(lessons),
        "predictions": len(preds),
        "resolved": len(resolved),
        "open": len(open_preds),
    }
    return out


# ---------------------------------------------------- before/after ship ------
def fetch_signup_experiment(env, base):
    """Before/after read on the 'Google primary' signup-modal ship (2026-05-27).
    Full rollout, not a PostHog A/B, so we measure signup-modal completion before
    vs after the ship date. Returns base with a live signal, or base on failure."""
    SHIP = "2026-05-27"
    q = (
        "SELECT "
        "count(DISTINCT if(event='signup_modal_opened' AND ts <  toDateTime('%(s)s'), pid, NULL)) AS ob, "
        "count(DISTINCT if(event='signup_completed'    AND ts <  toDateTime('%(s)s'), pid, NULL)) AS sb, "
        "count(DISTINCT if(event='signup_modal_opened' AND ts >= toDateTime('%(s)s'), pid, NULL)) AS oa, "
        "count(DISTINCT if(event='signup_completed'    AND ts >= toDateTime('%(s)s'), pid, NULL)) AS sa "
        "FROM (SELECT person_id AS pid, timestamp AS ts, event FROM events "
        "WHERE event IN ('signup_modal_opened','signup_completed') AND timestamp >= toDateTime('2026-05-18'))"
    ) % {"s": SHIP}
    rows = _hogql(env, q)
    out = dict(base)
    if not rows or not rows[0]:
        return out
    try:
        ob, sb, oa, sa = [int(x) for x in rows[0]]
    except (ValueError, TypeError):
        return out
    before = (sb / ob * 100) if ob else 0.0
    after = (sa / oa * 100) if oa else 0.0
    delta = after - before
    note = " Low sample while delivery is paused, directional only." if (ob + oa) < 80 else ""
    out["signal"] = (
        f"Modal completion before May 27: {before:.0f}% ({sb}/{ob}). "
        f"After: {after:.0f}% ({sa}/{oa}). Change: {delta:+.0f} pts.{note}"
    )
    # Numeric result so the queue reconciler can use it as a deterministic
    # done-signal (the ship is live the moment delta is measurable and positive).
    out["delta"] = round(delta, 1)
    out["before"] = round(before, 1)
    out["after"] = round(after, 1)
    out["shipped"] = bool(oa) and delta > 0
    log(f"signup before/after: {before:.0f}% -> {after:.0f}% ({delta:+.0f} pts)")
    return out


def fetch_try_experiment(env, base, landing):
    """OS-tracked read on the /try (value-first) vs homepage paid landing A/B.
    A Meta-level landing split, NOT a PostHog experiment, so it never shows in the
    experiments API. /try is measured by its true tbs_* cohort (see _correct_try_row,
    applied inside fetch_landing_pages), which corrects the earlier first-pageview-
    pathname undercount. Reads the already-corrected /try row + funnel from `landing`;
    runs no query of its own. Returns base enriched, or base unchanged on no data."""
    out = dict(base)
    pages = {p.get("path"): p for p in ((landing or {}).get("pages") or [])}
    home, tryp = pages.get("/"), pages.get("/try")
    cmp_bits = []
    if home:
        cmp_bits.append(f"Homepage {home.get('signupPct')}% signup ({home.get('signups')}/{home.get('visitors')})")
    if tryp:
        cmp_bits.append(f"/try {tryp.get('signupPct')}% ({tryp.get('signups')}/{tryp.get('visitors')}, tbs_* cohort)")
    funnel_bit = ""
    fn = (landing or {}).get("tryFunnel")
    if fn:
        out["tryFunnel"] = fn
        funnel_bit = (f" /try value-first funnel: {fn['landed']} land -> {fn['generated']} generate -> "
                      f"{fn['hitWall']} hit the signup wall -> {fn['signed']} signup.")
    caveat = (" Note: /try is measured by its tbs_* cohort (true entry signal), correcting the earlier "
              "first-pageview-pathname undercount (the old 1.5% was an attribution artifact). Signups remain "
              "a floor: anonymous->identified magic-link stitching can split a signer off the cohort "
              "(ClickUp 86ba2wp4t). Thin sample, directional only.")
    out["signal"] = (" vs ".join(cmp_bits) + ("." if cmp_bits else "") + funnel_bit + caveat).strip()
    if home and tryp and isinstance(home.get("signupPct"), (int, float)) and isinstance(tryp.get("signupPct"), (int, float)):
        out["status"] = "Running, /try ahead (thin)" if tryp["signupPct"] >= home["signupPct"] else "Running, /try behind (thin)"
    log(f"try-experiment: home {home.get('signupPct') if home else '?'}% vs /try {tryp.get('signupPct') if tryp else '?'}% (tbs cohort)")
    return out


# -------------------------------------------------------------- reconcile ----
_DONE_TYPES = {"done", "closed"}


def _best_clickup_match(keywords, pool):
    """Return the ClickUp task whose name best matches the keyword list, or None.
    A task matches when its lower-cased name contains a keyword phrase; ties break
    toward more keyword hits, then toward a done/closed task (resolution wins)."""
    best, best_score = None, 0
    for t in pool:
        name = (t.get("name") or "").lower()
        hits = sum(1 for k in keywords if k.lower() in name)
        if not hits:
            continue
        score = hits * 2 + (1 if t.get("type") in _DONE_TYPES else 0)
        if score > best_score:
            best, best_score = t, score
    return best


def reconcile_queue(content, meta_live, experiments, clickup):
    """Cross-check each curated Command Center item against the live signals this
    build already gathered, and attach a `live` overlay so the dashboard self-
    corrects when the hand-written status drifts from reality.

    Deterministic and non-destructive: it never rewrites the curated item, it only
    annotates it. Items opt in with an optional `verify` block; items without one
    are left untouched. This is the always-on guardrail between the slower
    LLM-driven marketing-os-refresh reasoning passes.

    verify = {
      "signal":  "signupModalShipped" | "metaDeliveryLive",   # named live signals
      "clickup": ["keyword", ...],                             # match a ClickUp task
      "doneWhen": "signal" | "clickup"                         # what flips it to done
    }
    """
    cc = content.get("commandCenter") or {}
    items = cc.get("items") or []
    pool = (clickup or {}).get("all") or []

    # Named deterministic signals, each -> (is_done, evidence string) or None.
    sx = next((e for e in experiments
               if isinstance(e, dict) and isinstance(e.get("delta"), (int, float))
               and ("signup" in (e.get("name", "").lower()) or "google" in (e.get("name", "").lower()))),
              None)
    signals = {}
    if sx is not None:
        signals["signupModalShipped"] = (
            bool(sx.get("shipped")),
            f"experiment: modal completion {sx.get('before')}% -> {sx.get('after')}% ({sx.get('delta'):+g} pts)",
        )
    if meta_live.get("status"):
        live = meta_live["status"] == "Live"
        signals["metaDeliveryLive"] = (live, f"autopilot: delivery {meta_live['status'].lower()}")

    flagged = 0
    for it in items:
        v = it.get("verify")
        if not v:
            continue
        evidence, ct = [], None
        done_when = v.get("doneWhen")  # which channel is allowed to flip "done"
        sig_done = ct_done = False

        sig = v.get("signal")
        if sig and sig in signals:
            sig_done, sig_ev = signals[sig]
            evidence.append(sig_ev)

        kws = v.get("clickup")
        if kws:
            ct = _best_clickup_match(kws, pool)
            if ct:
                evidence.append(f"ClickUp: “{ct['name']}” is {ct['status']}")
                ct_done = ct.get("type") in _DONE_TYPES

        # Only the channel named by doneWhen may flip the card to done. With no
        # doneWhen the signals are evidence-only (watch items never auto-complete).
        done_signal = (sig_done if done_when == "signal"
                       else ct_done if done_when == "clickup"
                       else False)

        # How the human wrote it.
        written_done = bool(it.get("done")) or bool(re.search(r"shipp|done|complete|live again|resolved", it.get("status", ""), re.I))
        verdict = "done" if (done_signal or written_done) else "active"
        # Disagreement: live says done but the card doesn't (the bug that bit us),
        # or the card claims done with no live evidence to back it.
        disagree = (done_signal and not written_done) or (written_done and not done_signal and bool(evidence))

        it["live"] = {
            "verdict": verdict,
            "doneSignal": done_signal,
            "evidence": evidence,
            "disagree": disagree,
            "clickup": ({"name": ct["name"], "status": ct["status"], "url": ct.get("url", "")} if ct else None),
        }
        if disagree:
            flagged += 1

    log(f"reconcile: {sum(1 for it in items if it.get('verify'))} verified item(s), {flagged} disagreement(s)")


def bind_objectives_kpis(content, activation, meta_live, paying, total_signups):
    """Live-bind the Command Center's north-star KPI anchor so it reads 'where we
    are' not just 'where we want to be', and stays coherent with the KPI strip.
    All four KPIs are live:
      - Paying customers:    live purchase_completed count / 5 (the brag).
      - Signup → paid:       live paying / signups, the make-or-break revenue KPI.
      - Signup → activation: signup → try-on, from the funnel spine.
      - CPL:                 Meta cost / signup (string matched to the KPI tile).
    `purchase_completed` IS instrumented (PR #37); paying is just genuinely 0 so
    far (no sales yet, confirmed by Alejo), so the live 0 is accurate and the
    anchor auto-flips on the first sale. Measurable KPIs fold their target into
    the label and show the live value; "Paying customers" keeps the "n / 5" form.

    Pure, non-destructive data binding. Idempotent: build reloads content.json
    fresh each run, so each k.v always starts as its curated target."""
    kpis = ((content.get("commandCenter") or {}).get("objectives") or {}).get("kpis") or []
    # Use the CPL string exactly as the KPI strip shows it (e.g. "$6.09") so the
    # two surfaces stay coherent — matching numbers is the whole point here.
    cpl_now = (meta_live or {}).get("cpl") or None
    act_now = activation.replace("~", "") if activation and activation != "—" else None
    paid_pct = (f"{round(paying / total_signups * 100)}%"
                if paying is not None and total_signups else None)
    for k in kpis:
        label, target = (k.get("k") or "").lower(), k.get("v", "")
        if "paying" in label and paying is not None:
            k["v"] = f"{paying} / 5"
        elif "paid" in label and paid_pct is not None:
            k["k"], k["v"] = f"{k['k']} · goal {target}", paid_pct
        elif "activation" in label and act_now:
            k["k"], k["v"] = f"{k['k']} · goal {target}", act_now
        elif "cpl" in label and cpl_now:
            k["k"], k["v"] = f"{k['k']} · goal {target}", cpl_now
    log("objectives KPIs: bound paying, signup→paid, activation, CPL to live values")


# ============================================================== COVERAGE =====
# The Coverage Reconciler. Every build it enumerates the live marketing surface
# (events / experiments / ClickUp tasks) and diffs it against coverage-registry.json
# (what the OS is told to model). Live-but-unmodeled = a blind spot. v1 is
# detect + escalate only: no auto-wiring, and it NEVER writes content.json — it
# touches only data.js (live.coverage) and coverage-registry.json (write-on-change).
# Design: docs/superpowers/specs/2026-06-04-coverage-reconciler-design.md
#
# Every scanner is fail-open: any pull failure makes that dimension return None
# ("no data"), the build continues, and a None dimension is SKIPPED by the differ
# so a failed pull can never emit false "stale" entries.

# Weak signal: a ClickUp task name that *looks* like an experiment. Used ONLY to
# escalate (surface in the Coverage tab for a human to triage) — never to auto-
# create a card. A false match is cheap: it adds a line to a triage list, not a
# junk card to the user-facing Experiments tab.
_EXPERIMENT_NAME_RE = re.compile(r"experiment|test|a/b|split|variant", re.I)


def load_registry():
    """Read coverage-registry.json. Returns the parsed dict, or a minimal empty
    skeleton on any failure (missing/corrupt) so the build never crashes."""
    skeleton = {"version": 1, "dimensions": {}, "clickupTasks": {}}
    if not REGISTRY.exists():
        log("coverage: no coverage-registry.json; seeding empty (everything live will surface)")
        return skeleton
    try:
        return json.loads(REGISTRY.read_text())
    except (ValueError, OSError) as e:
        log(f"coverage: registry unreadable ({e}); using empty skeleton")
        return skeleton


def scan_events(env):
    """Live event taxonomy over 30d: distinct-user + raw-event counts per event.
    Returns {event: {users, count}} or None on failure (dimension skipped)."""
    q = """
        SELECT event,
          count(DISTINCT person_id) AS users,
          count() AS cnt
        FROM events
        WHERE timestamp >= now() - INTERVAL 30 DAY
        GROUP BY event
    """.strip()
    rows = _hogql(env, q)
    if rows is None:  # None = pull failed; [] = pull succeeded but no events
        return None
    out = {}
    for r in rows:
        if not r or not r[0]:
            continue
        try:
            out[str(r[0])] = {"users": int(r[1]), "count": int(r[2])}
        except (ValueError, TypeError, IndexError):
            continue
    log(f"coverage scan_events: {len(out)} distinct event(s) live (30d)")
    return out


def scan_experiments(env, posthog_experiments, clickup):
    """Live experiment surface = PostHog experiment objects (already pulled) +
    open Ablo Studio ClickUp tasks whose name matches the experiment regex (a weak
    ESCALATE-only signal). Returns {posthog:[ids], clickupCandidates:[{id,name}]}
    or None only if BOTH inputs are unavailable.

    The PostHog ids are normalized to the same 'PH-<id>' form build.py uses, so
    they line up with registry.experiments.modeled."""
    ph_ids = []
    for e in (posthog_experiments or []):
        if isinstance(e, dict) and e.get("id"):
            ph_ids.append(str(e["id"]))

    # ClickUp candidates: open tasks whose name looks like an experiment. We only
    # consider the still-open feed (clickup['open']); closed experiments are not
    # actionable blind spots.
    clickup_candidates = None
    if clickup is not None:
        clickup_candidates = []
        for t in (clickup.get("open") or []):
            nm = t.get("name") or ""
            if _EXPERIMENT_NAME_RE.search(nm):
                tid = _task_id_from_url(t.get("url", ""))
                if tid:
                    clickup_candidates.append({"id": tid, "name": nm, "url": t.get("url", "")})

    if not ph_ids and clickup_candidates is None:
        return None
    log(f"coverage scan_experiments: {len(ph_ids)} PostHog · "
        f"{len(clickup_candidates) if clickup_candidates is not None else 'n/a'} ClickUp experiment-like task(s)")
    return {"posthog": ph_ids, "clickupCandidates": clickup_candidates}


def scan_clickup(clickup, registry):
    """Open Ablo Studio tasks that the OS surfaces nowhere — i.e. whose id is NOT
    in registry.clickupTasks.modeled and NOT in experiments.clickupMapped. These
    are marketing work the OS does not model. Returns [{id,name,url,status}] or
    None on failure."""
    if clickup is None:
        return None
    mapped = set((((registry.get("dimensions") or {}).get("experiments") or {})
                  .get("clickupMapped") or {}).values())
    modeled = set(((registry.get("clickupTasks") or {}).get("modeled") or []))
    referenced = mapped | modeled
    out = []
    for t in (clickup.get("open") or []):
        tid = _task_id_from_url(t.get("url", ""))
        if not tid or tid in referenced:
            continue
        out.append({"id": tid, "name": t.get("name", ""), "url": t.get("url", ""),
                    "status": t.get("status", "")})
    log(f"coverage scan_clickup: {len(out)} open task(s) the OS surfaces nowhere")
    return out


def _task_id_from_url(url):
    """ClickUp task urls end in /t/<id>. Extract the id (the stable key we diff on)."""
    if not url:
        return None
    m = re.search(r"/t/([A-Za-z0-9]+)/?$", url)
    return m.group(1) if m else url.rstrip("/").rsplit("/", 1)[-1] or None


def reconcile_coverage(registry, scans):
    """Pure differ. For each dimension: blind = live - modeled - ignore (filtered
    by threshold, ranked by volume); stale = modeled - live (only for dimensions
    whose live scan SUCCEEDED, so a failed pull never emits false stale). No I/O.

    `scans` = {events, experiments, clickup} where any value may be None ("no data").
    Returns {blindSpots:[...], stale:[...]} with blind items shaped
    {key, dimension, where, volume, cluster?, action, status:'escalated'}."""
    dims = registry.get("dimensions") or {}
    blind, stale = [], []

    # -- events -------------------------------------------------------------
    ev_reg = dims.get("events") or {}
    ev_live = scans.get("events")
    if ev_live is not None:
        modeled = set(ev_reg.get("modeled") or [])
        ignore = set(ev_reg.get("ignore") or [])
        threshold = ev_reg.get("minUsers30d", 0) or 0
        # Cluster unmodeled events by their prefix-before-'_' so a whole new flow
        # (e.g. tbs_*) reads as one blind spot, ranked by the cluster's total reach.
        clusters = {}
        singles = []
        for ev, stat in ev_live.items():
            if ev in modeled or ev in ignore:
                continue
            users = stat.get("users", 0)
            if "_" in ev:
                prefix = ev.split("_", 1)[0]
                c = clusters.setdefault(prefix, {"events": [], "users": 0})
                c["events"].append(ev)
                c["users"] = max(c["users"], users)  # cluster reach ~ its busiest event (distinct-user, not summable)
            else:
                singles.append((ev, users))
        for prefix, c in clusters.items():
            if c["users"] < threshold:
                continue
            key = prefix + "_*"
            blind.append({
                "key": key, "dimension": "events",
                "where": f"PostHog, {c['users']} users/30d ({len(c['events'])} events)",
                "volume": c["users"], "cluster": True,
                "action": f"Investigate the {key} flow; map a funnel stage or dismiss it to the registry with a reason",
                "status": "escalated",
            })
        for ev, users in singles:
            if users < threshold:
                continue
            blind.append({
                "key": ev, "dimension": "events",
                "where": f"PostHog, {users} users/30d",
                "volume": users, "cluster": False,
                "action": f"Decide if {ev} is a funnel signal to model or noise to dismiss",
                "status": "escalated",
            })
        # stale: modeled but absent from the live taxonomy (possible tracking regression)
        for ev in sorted(modeled):
            if ev not in ev_live:
                stale.append({"key": ev, "dimension": "events",
                              "note": "modeled but 0 users in 30d — possible tracking regression"})

    # -- experiments --------------------------------------------------------
    ex_reg = dims.get("experiments") or {}
    ex_live = scans.get("experiments")
    if ex_live is not None:
        modeled = set(ex_reg.get("modeled") or [])
        mapped = set((ex_reg.get("clickupMapped") or {}).values())
        ignore = set(ex_reg.get("ignore") or [])
        # PostHog experiment objects not yet modeled (rare; normally auto-modeled
        # via PH-<id>, but a brand-new one the registry hasn't seen surfaces here).
        for pid in (ex_live.get("posthog") or []):
            if pid in modeled or pid in ignore:
                continue
            blind.append({
                "key": pid, "dimension": "experiments",
                "where": "PostHog experiments", "volume": None,
                "action": "New PostHog experiment not yet in the OS; wire an experiment card or dismiss",
                "status": "escalated",
            })
        # ClickUp experiment-looking tasks not already mapped/ignored.
        cands = ex_live.get("clickupCandidates")
        if cands is not None:
            for c in cands:
                tid = c.get("id")
                if not tid or tid in mapped or tid in ignore or tid in modeled:
                    continue
                blind.append({
                    "key": tid, "dimension": "experiments",
                    "where": f"ClickUp Ablo Studio · “{(c.get('name') or '')[:60]}” matches an experiment name",
                    "volume": None,
                    "action": "Confirm it is a real experiment, then wire an OS-* card (agent owns content.json) or dismiss",
                    "status": "escalated",
                })

    # -- clickup ------------------------------------------------------------
    ck_live = scans.get("clickup")
    if ck_live is not None:
        ck_reg = registry.get("clickupTasks") or {}
        ignore = set(ck_reg.get("ignore") or [])
        for t in ck_live:
            tid = t.get("id")
            if not tid or tid in ignore:
                continue
            blind.append({
                "key": tid, "dimension": "clickup",
                "where": f"ClickUp Ablo Studio · “{(t.get('name') or '')[:60]}” [{t.get('status','')}]",
                "volume": None,
                "action": "Marketing work the OS surfaces nowhere; wire a Command Center item or dismiss",
                "status": "escalated",
            })

    # Rank blind spots by volume desc (None volume sinks below counted ones),
    # then by dimension + key for a stable, deterministic order.
    blind.sort(key=lambda b: (-(b.get("volume") or 0), b.get("dimension", ""), b.get("key", "")))
    stale.sort(key=lambda s: (s.get("dimension", ""), s.get("key", "")))
    return {"blindSpots": blind, "stale": stale}


def autowire_coverage(registry, diff, env):
    """v1: NO-OP. Detection + escalate only — every blind spot stays 'escalated'
    for the agent/human to resolve. The signature takes `registry` (not content)
    on purpose: even in v2 the auto-wirer may only ever touch coverage-registry.json,
    never the brain-owned content.json. Returns (registry, autowired_log).

    Kept as a real seam so v2 can introduce the two mechanical wirings (page/
    destination, explicit-tag experiment) without changing the build wiring."""
    return registry, []


def _canonical_registry(reg):
    """Deterministic serialization: sorted keys + sorted list members so logically
    identical registry state is byte-identical across runs. The `updated` field is
    excluded from the structural comparison (it tracks content changes, not the
    run timestamp), so a no-op build never rewrites the file."""
    def _sort(v):
        if isinstance(v, dict):
            return {k: _sort(v[k]) for k in sorted(v)}
        if isinstance(v, list):
            # members are scalars (event names / ids); sort for stability
            return sorted(v, key=lambda x: (str(type(x)), x))
        return v
    body = {k: v for k, v in reg.items() if k != "updated"}
    return json.dumps(_sort(body), ensure_ascii=False, indent=2, sort_keys=True)


def write_registry_if_changed(registry, today):
    """Write coverage-registry.json ONLY when its structural content changed vs the
    on-disk file. A no-op build leaves the file byte-identical (no diff, no daily
    commit noise). `updated` bumps only on a real change. Atomic temp-then-replace
    so a crashed build can't corrupt the registry. Returns True if it wrote."""
    new_canon = _canonical_registry(registry)
    old_canon = None
    if REGISTRY.exists():
        try:
            old_canon = _canonical_registry(json.loads(REGISTRY.read_text()))
        except (ValueError, OSError):
            old_canon = None
    if old_canon == new_canon:
        return False  # structurally identical -> never touch the file

    out = dict(registry)
    out["updated"] = today
    # Serialize with the same stable ordering used for comparison so the on-disk
    # form round-trips to byte-identical canon next run.
    sorted_body = json.loads(new_canon)
    sorted_body["updated"] = today
    text = json.dumps(sorted_body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(text)
    os.replace(tmp, REGISTRY)
    return True


def scan_coverage(env, posthog_experiments, clickup, registry):
    """Run every v1 scanner. Each is fail-open and returns None ("no data") on a
    failed pull. Returns {events, experiments, clickup}."""
    return {
        "events": scan_events(env),
        "experiments": scan_experiments(env, posthog_experiments, clickup),
        "clickup": scan_clickup(clickup, registry),
    }


def build_coverage(env, posthog_experiments, clickup, today):
    """Orchestrate the Coverage Reconciler and return the live.coverage block.
    Fully fail-open: any unexpected error yields an empty coverage block so the
    build (and the site render) never break."""
    try:
        registry = load_registry()
        scans = scan_coverage(env, posthog_experiments, clickup, registry)
        diff = reconcile_coverage(registry, scans)
        registry, autowired = autowire_coverage(registry, diff, env)
        wrote = write_registry_if_changed(registry, today)
        blind, stale = diff["blindSpots"], diff["stale"]
        log(f"coverage: {len(blind)} blind spot(s), {len(stale)} stale, "
            f"{len(autowired)} auto-wired · registry {'written' if wrote else 'unchanged'}")
        return {
            "updated": today,
            "blindSpots": blind,
            "stale": stale,
            "autowired": autowired,
            "summary": {"blind": len(blind), "autowired": len(autowired), "stale": len(stale)},
        }
    except Exception as e:  # noqa: BLE001 -- coverage must never break the build
        log(f"coverage: unexpected failure ({e}); emitting empty coverage block")
        return {"updated": today, "blindSpots": [], "stale": [], "autowired": [],
                "summary": {"blind": 0, "autowired": 0, "stale": 0}}


# --------------------------------------------------------------- strategy ----
def _parse_frontmatter(text):
    """Split a markdown doc into (frontmatter dict, body). Minimal flat YAML:
    `key: value` lines between the leading --- fences. No pyyaml dependency.
    'null'/empty -> None; surrounding quotes stripped. Returns ({}, text) when
    there is no frontmatter block."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in block.split("\n"):
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
            v = v[1:-1]
        if v == "" or v.lower() == "null":
            v = None
        fm[k] = v
    return fm, body


def load_strategy_registry():
    try:
        return json.loads(STRATEGY_REGISTRY.read_text())
    except Exception:  # noqa: BLE001
        return {}


def fetch_strategy(registry):
    """Read the foundation markdown folder and assemble the live.strategy block:
    each registry doc gets its current status + embedded body, plus a coverage
    summary (counts by status). Fail-open: a missing folder or unreadable file
    degrades that doc to status 'missing', never breaks the build."""
    docs_meta = (registry or {}).get("docs", [])
    groups = (registry or {}).get("groups", [])
    VALID = {"complete", "draft", "stub"}
    out_docs, present = [], 0
    for d in docs_meta:
        rec = {
            "key": d.get("key"), "title": d.get("title"), "group": d.get("group"),
            "mkt1": d.get("mkt1"), "osSection": d.get("osSection"),
            "feeds": d.get("feeds"), "file": d.get("file"),
            "status": "missing", "updated": None, "owner": None, "body": None,
            "wordCount": 0,
        }
        path = STRATEGY_DIR / (d.get("file") or "")
        try:
            if path.is_file():
                fm, body = _parse_frontmatter(path.read_text())
                st = (fm.get("status") or "").lower()
                rec["status"] = st if st in VALID else "draft"
                rec["updated"] = fm.get("updated")
                rec["owner"] = fm.get("owner")
                rec["body"] = body.strip()
                rec["wordCount"] = len(body.split())
                present += 1
        except Exception as e:  # noqa: BLE001
            log(f"strategy: failed to read {d.get('file')} ({e})")
        out_docs.append(rec)
    counts = {"complete": 0, "draft": 0, "stub": 0, "missing": 0}
    for r in out_docs:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    total = len(out_docs)
    summary = {
        "total": total, "present": present,
        "complete": counts["complete"], "draft": counts["draft"],
        "stub": counts["stub"], "missing": counts["missing"],
        "pct": round(100 * counts["complete"] / total) if total else 0,
        "gaps": [r["key"] for r in out_docs if r["status"] in ("stub", "missing")],
    }
    mounted = STRATEGY_DIR.is_dir()
    log(f"strategy: {present}/{total} docs present · {counts['complete']} complete, "
        f"{counts['draft']} draft, {counts['stub']} stub, {counts['missing']} missing"
        + ("" if mounted else " · source folder NOT mounted (fail-open)"))
    return {
        "updated": (registry or {}).get("updated"),
        "source": (registry or {}).get("source"),
        "mounted": mounted,
        "groups": groups,
        "statusLabels": (registry or {}).get("statusLabels", {}),
        "statusTone": (registry or {}).get("statusTone", {}),
        "statusOrder": (registry or {}).get("statusOrder", []),
        "docs": out_docs,
        "summary": summary,
    }


def build_strategy():
    """Orchestrate the foundation read. Fully fail-open: any error yields an empty
    strategy block so the build (and the site render) never break."""
    try:
        return fetch_strategy(load_strategy_registry())
    except Exception as e:  # noqa: BLE001
        log(f"strategy: unexpected failure ({e}); emitting empty strategy block")
        return {"updated": None, "mounted": False, "groups": [], "docs": [],
                "statusLabels": {}, "statusTone": {}, "statusOrder": [],
                "summary": {"total": 0, "present": 0, "complete": 0, "draft": 0,
                            "stub": 0, "missing": 0, "pct": 0, "gaps": []}}


# ------------------------------------------------------------------ build ----
def build():
    content = json.loads(CONTENT.read_text())
    live_experiments = fetch_experiments(load_env(ENV_FILE))
    meta_live = fetch_meta()

    # Tokens: process environment as the base (shell / launchd env vars), with
    # ~/.claude/.env overlaid when present (the local machine's source of truth).
    env = {**os.environ, **load_env(ENV_FILE)}
    posthog_live = bool(live_experiments)
    if posthog_live:
        experiments = live_experiments
    else:
        # Graceful fallback: accurate last-known experiments from content.json
        # (auto-upgrades to live once the PostHog key gets experiment:read scope).
        experiments = content.get("experimentsCurated", {}).get("liveFallback", [])

    # Tracked before/after ship (not a PostHog A/B): the Google-primary signup change.
    sx = content.get("experimentsCurated", {}).get("signupExperiment")
    if sx:
        experiments = list(experiments) + [fetch_signup_experiment(env, sx)]

    # Live product funnel (PostHog) and lifecycle (Klaviyo), overlaid on the
    # curated fallbacks. Each degrades to its curated block on failure.
    funnel = fetch_funnel(env, content.get("funnelCurated", {}))
    lifecycle = fetch_lifecycle(env, content.get("lifecycleCurated", {}))
    funnel_live = funnel.get("source", "").startswith("PostHog · live")
    klaviyo_live = lifecycle.get("source", "").startswith("Klaviyo · live")

    # Keep the Overview's Current Focus numbers bound to the live funnel so the
    # narrative and the Funnel tab can never disagree (the coherence rule).
    bind_current_focus(content, funnel, fetch_signup_methods(env))

    # Live channel attribution from PostHog UTMs (ties each source through to
    # signup / try-on / checkout). None on failure.
    channels_live = fetch_channel_attribution(env)

    # Live per-landing-page conversion (entry pathname -> engage -> signup). Makes
    # top-of-funnel CRO a measurable, per-page bet instead of an aggregate hunch.
    landing_live = fetch_landing_pages(env)

    # Wire the /try-vs-homepage paid landing A/B as an OS-tracked experiment, fed
    # from the live per-page signup rate + the /try value-first (tbs_*) funnel, so a
    # Meta-level landing split surfaces in the Experiments tab with a live verdict.
    tx = content.get("experimentsCurated", {}).get("tryExperiment")
    if tx:
        experiments = list(experiments) + [fetch_try_experiment(env, tx, landing_live)]

    # ClickUp task feed (source of truth for action items) + IG organic stats.
    clickup = fetch_clickup(env)
    instagram = fetch_instagram(env)
    paying = fetch_paying(env)

    # Daily time-series — snapshot today and rewrite history.jsonl.
    history = snapshot_history(env, funnel, meta_live, lifecycle, instagram, paying=paying, landing=landing_live)

    # Self-improvement memory — read the agent's own ledger back into the OS so
    # every run starts with what past runs learned (and what bets are due to score).
    learning = load_learning()

    # Activation = same-user signup -> try-on (the aha), straight from the funnel.
    # Neutral placeholder if the funnel pull fails -- never show a stale number.
    activation = "—"
    try:
        spine = funnel.get("spine", {}).get("steps", [])
        aha = next((s for s in spine if s.get("aha")), None)
        if aha:
            activation = f"~{aha['pct']}%"
    except (KeyError, TypeError):
        pass

    # Paid spend sub-line: the autopilot reports only the CURRENT flight's
    # lifetime (it resets when a new campaign starts), so anchor all-time with the
    # closed-flight total (auto-derived from history, no manual bumping) + the live
    # flight. Spend is context here, not a hero metric: CPL + weekly burn are what
    # the call should act on.
    CLOSED_FLIGHTS_SPEND = _closed_flights_spend(history.get("rows", []))

    # Blended paid spend across channels. Meta from the autopilot (live), LinkedIn
    # live from the Marketing API (falls back to LINKEDIN_CLOSED_SPEND if the token
    # is missing/expired and can't refresh).
    meta_all_time = CLOSED_FLIGHTS_SPEND + _money(meta_live.get("spend"))
    linkedin_live = fetch_linkedin_spend(env)
    linkedin_spend = linkedin_live if linkedin_live is not None else LINKEDIN_CLOSED_SPEND
    total_paid = meta_all_time + linkedin_spend

    # Lifetime signups = ALL sources (Meta + LinkedIn + organic + direct), taken
    # from the PostHog "Signed up" stage all-window count, not Meta-attributed only.
    signups = meta_live["signups"]  # Meta-attributed (kept for CPL math)
    total_signups = None
    try:
        sig_stage = next((s for s in funnel.get("stages", []) if s.get("key") == "signup"), None)
        if sig_stage:
            total_signups = sig_stage.get("counts", {}).get("all")
    except (KeyError, TypeError):
        pass
    signups_value = str(total_signups) if total_signups is not None else (str(signups) if signups is not None else "—")
    # Blended CAC = all paid spend / all signups. This is a FLOOR: it includes
    # organic signups in the denominator, so true paid-only CAC is higher. The
    # sub-label states the method so it can't be read as paid-only.
    blended_cac = f"${total_paid / total_signups:.2f}" if total_signups else "—"
    kpis = [
        # Paying customers from the PostHog purchase event (Studio-scoped by nature).
        {"label": "Paying customers",
         "value": f"{paying} / 5" if paying is not None else "0 / 5",
         "sub": "self-serve only · the brag · CAC < $300", "tone": "accent"},
        {"label": "Lifetime signups", "value": signups_value, "sub": "all-time, all sources", "tone": "default"},
        {"label": "Blended CAC", "value": blended_cac, "sub": "all paid ÷ all signups · target ≤ $20", "tone": "default"},
        {"label": "Activation", "value": activation, "sub": "signup → try-on · target ≥ 50%", "tone": "default"},
        {"label": "Total ad spend", "value": f"${total_paid:,.0f}", "sub": f"Meta ~${meta_all_time:,.0f} + LinkedIn ${linkedin_spend:,.0f}{'' if linkedin_live is not None else ' (cached)'}", "tone": "default"},
        {"label": "Live experiments", "value": str(len(experiments)) if experiments else "1", "sub": "running in PostHog", "tone": "default"},
    ]

    now = datetime.now(timezone.utc)
    content["meta"]["updated"] = now.strftime("%B %-d, %Y")
    content["meta"]["updatedISO"] = now.isoformat()

    # Coverage Reconciler — diff the live marketing surface (events / experiments /
    # ClickUp) against coverage-registry.json. Fully fail-open; writes only the
    # registry (on real change) and the live.coverage block below, never content.json.
    # Runs before clickup['all'] is popped (it reads clickup['open'], which survives).
    coverage = build_coverage(env, experiments, clickup, now.strftime("%Y-%m-%d"))
    # Foundation strategy layer — read the canonical markdown docs from the Brain
    # (Obsidian) and embed them + a coverage summary. Source of truth for strategy
    # lives there now, not in content.json. Fail-open (empty block if unreadable).
    strategy = build_strategy()
    # Self-improving Command Center: stamp it reviewed on every run so the action
    # queue always reflects "checked today". Deeper status re-ranking (resolve
    # done items, surface new leaks) is done by the marketing-os-refresh agent
    # skill, which reasons over the live funnel/campaigns/experiments/lifecycle.
    if "commandCenter" in content:
        content["commandCenter"]["updated"] = content["meta"]["updated"]
        # Live-bind the north-star KPI anchor (all four KPIs) to current values.
        bind_objectives_kpis(content, activation, meta_live, paying, total_signups)
        # Always-on deterministic guardrail: annotate each curated item with the
        # live verdict so the queue self-corrects when its hand-written status
        # drifts (the "stale priority" gap). Runs every build, no LLM needed.
        reconcile_queue(content, meta_live, experiments, clickup)
    if clickup:
        clickup.pop("all", None)  # reconciler-only pool; don't embed it in data.js

    # Per-source health for the footer status lights. Three states so an OUTAGE
    # reads loud and distinct from a source that is curated-by-design:
    #   live = credentials present and the pull succeeded (green)
    #   down = credentials present but the pull failed, we are on cached data (red)
    #   off  = no credentials configured / not connected (grey, calm)
    def _health(has_creds, ok):
        return ("live" if ok else "down") if has_creds else "off"
    _HDETAIL = {"live": "live", "down": "pull failed · on cached data", "off": "not connected"}
    source_health = [
        {"key": "posthog",   "label": "PostHog",   "state": _health(bool(env.get("POSTHOG_PERSONAL_API_KEY")), funnel_live or posthog_live or channels_live is not None)},
        {"key": "meta",      "label": "Meta",      "state": _health(bool(env.get("META_ADS_TOKEN")), signups is not None)},
        {"key": "klaviyo",   "label": "Klaviyo",   "state": _health(bool(env.get("KLAVIYO_API_KEY_ABLO")), klaviyo_live)},
        {"key": "clickup",   "label": "ClickUp",   "state": _health(bool(env.get("CLICKUP_TOKEN_ABLO")), clickup is not None)},
        {"key": "instagram", "label": "Instagram", "state": _health(bool(env.get("META_ADS_TOKEN")), instagram is not None)},
        {"key": "linkedin",  "label": "LinkedIn",  "state": _health(bool(env.get("LINKEDIN_ADS_TOKEN")), linkedin_live is not None)},
    ]
    for _s in source_health:
        _s["detail"] = _HDETAIL[_s["state"]]
    content["live"] = {
        "kpis": kpis,
        "experiments": experiments,
        "meta": meta_live,
        "funnel": funnel,
        "lifecycle": lifecycle,
        "channels": channels_live,
        "landingPages": landing_live,
        "clickup": clickup,
        "instagram": instagram,
        "history": history,
        "learning": learning,
        "coverage": coverage,
        "strategy": strategy,
        "refreshedSources": {
            "posthog": posthog_live,
            "meta": signups is not None,
            "funnel": funnel_live,
            "klaviyo": klaviyo_live,
            "channels": channels_live is not None,
            "landingPages": landing_live is not None,
            "clickup": clickup is not None,
            "instagram": instagram is not None,
            "history": history.get("phLive", False),
        },
        "sourceHealth": source_health,
    }

    banner = (
        "/* AUTO-GENERATED by build.py. Do not edit by hand. */\n"
        "/* Curated strategy lives in content.json; live data refreshes daily. */\n"
    )
    OUT.write_text(banner + "window.ABLO_OS = " + json.dumps(content, ensure_ascii=False, indent=2) + ";\n")
    log(f"wrote {OUT.name} · updated {content['meta']['updated']}")
    log(f"posthog={'live' if posthog_live else 'cached'} meta={'live' if signups is not None else 'cached'}")
    cal = learning["calibration"]
    log(
        f"learning: {learning['counts']['lessons']} lessons · "
        f"calibration {cal['hitRate'] if cal['hitRate'] is not None else 'n/a'} (n={cal['n']}) · "
        f"{len(learning['dueForReview'])} prediction(s) due for review"
    )


if __name__ == "__main__":
    build()

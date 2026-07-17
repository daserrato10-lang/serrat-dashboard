#!/usr/bin/env python3
"""
Serrat Relojes — Instagram Dashboard Generator
1. Toma un snapshot diario de métricas por post
2. Acumula historia en .tmp/post_snapshots.json
3. Genera dashboard HTML con gráficas interactivas
"""

import os, json, time, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.request, urllib.parse

# ── Config ────────────────────────────────────────────────────

ROOT      = Path(__file__).parent.parent
ENV       = ROOT / ".env"
OUT       = ROOT / ".tmp" / "dashboard.html"
SNAPSHOTS = ROOT / ".tmp" / "post_snapshots.json"
TAGS_FILE        = ROOT / "post_tags.json"
EXPERIMENTS_FILE = ROOT / "experiments.json"

def load_env():
    env = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

cfg      = load_env()
TOKEN    = cfg.get("IG_TOKEN",  os.environ.get("IG_TOKEN", ""))
IG_ID    = cfg.get("IG_ID",     os.environ.get("IG_ID", ""))
GH_TOKEN = cfg.get("GH_TOKEN",  os.environ.get("GH_TOKEN", ""))
GH_REPO  = cfg.get("GH_REPO",   os.environ.get("GH_REPO", ""))
BASE  = "https://graph.facebook.com/v21.0"

# ── API ───────────────────────────────────────────────────────

def ig_get(path, params=None):
    params = params or {}
    params["access_token"] = TOKEN
    qs  = urllib.parse.urlencode(params)
    url = f"{BASE}/{path}?{qs}"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(data["error"]["message"])
    return data

def get_perfil():
    return ig_get(IG_ID, {"fields": "username,followers_count,follows_count,media_count,website"})

def get_insights(days=28):
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    until = int(datetime.now(timezone.utc).timestamp())
    daily  = ig_get(f"{IG_ID}/insights", {
        "metric": "reach,follower_count", "period": "day",
        "since": since, "until": until
    })
    totals = ig_get(f"{IG_ID}/insights", {
        "metric": "profile_views,website_clicks,total_interactions,likes,comments,shares,saves",
        "metric_type": "total_value", "period": "day",
        "since": since, "until": until
    })
    result = {}
    for m in daily.get("data", []):
        vals = m.get("values", [])
        result[m["name"]] = sum(v["value"] for v in vals if isinstance(v.get("value"), (int, float)))
        if m["name"] == "reach":
            result["reach_daily"] = [{"date": v["end_time"][:10], "value": v["value"]} for v in vals]
    for m in totals.get("data", []):
        result[m["name"]] = (m.get("total_value") or {}).get("value", 0)
    return result

def get_all_insights():
    results = {}
    for days in [7, 14, 28]:
        results[days] = get_insights(days)
        time.sleep(0.3)
    return results

def get_posts(limit=30):
    media = ig_get(f"{IG_ID}/media", {
        "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink",
        "limit": limit
    })
    posts = media.get("data", [])
    for post in posts:
        try:
            ins = ig_get(f"{post['id']}/insights", {"metric": "reach,saved,shares"})
            for m in ins.get("data", []):
                post[f"metric_{m['name']}"] = (m.get("values") or [{}])[0].get("value", 0)
        except Exception:
            post["metric_reach"] = post["metric_saved"] = post["metric_shares"] = 0
        time.sleep(0.1)
    return posts

def get_demografia():
    def fetch(breakdown):
        try:
            return ig_get(f"{IG_ID}/insights", {
                "metric": "follower_demographics", "metric_type": "total_value",
                "period": "lifetime", "breakdown": breakdown
            })
        except Exception:
            return None
    return {"age_gender": fetch("age,gender"), "country": fetch("country"), "city": fetch("city")}

def parse_breakdowns(data):
    try:
        return data["data"][0]["total_value"]["breakdowns"][0]["results"]
    except Exception:
        return []

# ── Snapshots ─────────────────────────────────────────────────

def parse_ig_timestamp(ts):
    """Convierte timestamp de Instagram (ISO 8601) a datetime UTC."""
    if not ts:
        return None
    # Formato: 2026-07-01T20:15:00+0000
    ts = ts.replace("+0000", "+00:00")
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None

def save_snapshot(posts, followers=0):
    """Guarda un snapshot con timestamp exacto por post."""
    colombia       = timezone(timedelta(hours=-5))
    now_col        = datetime.now(colombia)
    today          = now_col.strftime("%Y-%m-%d")
    snapshot_taken = datetime.now(timezone.utc).isoformat()

    if SNAPSHOTS.exists():
        history = json.loads(SNAPSHOTS.read_text())
    else:
        history = {}

    if today in history:
        print(f"  ℹ️  Snapshot de {today} ya existe — se omite duplicado.")
        return history

    meta = {"taken_at": snapshot_taken}
    if followers:
        meta["followers_count"] = followers
    history[today] = {"_meta": meta}
    for post in posts:
        pid = post["id"]
        history[today][pid] = {
            "published":    post.get("timestamp", "")[:10],
            "published_at": post.get("timestamp", ""),   # hora exacta
            "caption":      (post.get("caption") or "")[:120].replace("\n", " "),
            "type":         post.get("media_type", ""),
            "permalink":    post.get("permalink", ""),
            "likes":        post.get("like_count", 0),
            "comments":     post.get("comments_count", 0),
            "reach":        post.get("metric_reach", 0),
            "saved":        post.get("metric_saved", 0),
            "shares":       post.get("metric_shares", 0),
        }

    SNAPSHOTS.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    print(f"  ✅ Snapshot guardado: {today} a las {snapshot_taken[11:16]} UTC ({len(posts)} posts)")
    return history

def hours_between(pub_at_str, snap_taken_str):
    """Horas exactas entre publicación y momento del snapshot."""
    pub  = parse_ig_timestamp(pub_at_str)
    snap = parse_ig_timestamp(snap_taken_str)
    if pub and snap:
        return round((snap - pub).total_seconds() / 3600, 1)
    return None

def build_series_entry(date_str, snap_taken_at, data):
    """Construye un punto de serie con horas exactas."""
    hours = hours_between(data.get("published_at", ""), snap_taken_at)
    # Fallback a días*24 si no hay timestamp exacto (snapshots viejos)
    if hours is None:
        try:
            pub_date  = datetime.strptime(data.get("published", ""), "%Y-%m-%d").date()
            snap_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            hours     = (snap_date - pub_date).days * 24
        except Exception:
            hours = 0
    return {
        "snapshot_date": date_str,
        "hours":         hours,
        "reach":         data.get("reach", 0),
        "likes":         data.get("likes", 0),
        "comments":      data.get("comments", 0),
        "saved":         data.get("saved", 0),
        "shares":        data.get("shares", 0),
    }

def build_growth_data(history):
    """
    Solo posts publicados DESPUÉS del primer snapshot.
    Serie en horas exactas desde publicación.
    """
    first_snapshot_date = min(k for k in history.keys() if not k.startswith("_")) if history else "9999-12-31"

    all_posts = {}
    for date_str, snap in history.items():
        if date_str.startswith("_"):
            continue
        for pid, data in snap.items():
            if pid == "_meta":
                continue
            if data.get("published", "") < first_snapshot_date:
                continue
            if pid not in all_posts:
                all_posts[pid] = {
                    "id":           pid,
                    "caption":      data["caption"],
                    "type":         data["type"],
                    "permalink":    data["permalink"],
                    "published":    data["published"],
                    "published_at": data.get("published_at", ""),
                    "series":       []
                }

    for date_str in sorted(history.keys()):
        if date_str.startswith("_"):
            continue
        snap         = history[date_str]
        snap_taken   = (snap.get("_meta") or {}).get("taken_at", date_str + "T18:00:00+00:00")
        for pid, data in snap.items():
            if pid == "_meta" or pid not in all_posts:
                continue
            all_posts[pid]["series"].append(build_series_entry(date_str, snap_taken, data))

    result = [p for p in all_posts.values() if p["series"]]
    result.sort(key=lambda x: x["published_at"] or x["published"], reverse=True)
    return result

def build_growth_data_all(history):
    """Todos los posts sin filtro de fecha — para el modal."""
    all_posts = {}
    for date_str, snap in history.items():
        if date_str.startswith("_"):
            continue
        for pid, data in snap.items():
            if pid == "_meta":
                continue
            if pid not in all_posts:
                all_posts[pid] = {
                    "id":           pid,
                    "caption":      data["caption"],
                    "type":         data["type"],
                    "permalink":    data["permalink"],
                    "published":    data["published"],
                    "published_at": data.get("published_at", ""),
                    "series":       []
                }

    for date_str in sorted(history.keys()):
        if date_str.startswith("_"):
            continue
        snap       = history[date_str]
        snap_taken = (snap.get("_meta") or {}).get("taken_at", date_str + "T18:00:00+00:00")
        for pid, data in snap.items():
            if pid == "_meta" or pid not in all_posts:
                continue
            all_posts[pid]["series"].append(build_series_entry(date_str, snap_taken, data))

    result = [p for p in all_posts.values() if p["series"]]
    result.sort(key=lambda x: x["published_at"] or x["published"], reverse=True)
    return result

def get_daily_business_metrics():
    """Website clicks y profile views de las últimas 24 horas (ventana 1d)."""
    now_ts  = int(datetime.now(timezone.utc).timestamp())
    day1_ts = now_ts - 86400
    try:
        data = ig_get(f"{IG_ID}/insights", {
            "metric": "website_clicks,profile_views",
            "metric_type": "total_value",
            "period": "day",
            "since": day1_ts, "until": now_ts
        })
        result = {}
        for m in data.get("data", []):
            result[m["name"]] = (m.get("total_value") or {}).get("value", 0)
        return result
    except Exception as e:
        print(f"  ⚠️  No se pudo obtener métricas diarias de negocio: {e}")
        return {}

# ── Follower growth ───────────────────────────────────────────

def build_follower_series(history, all_posts):
    """
    Construye serie diaria de seguidores ganados a partir de los _meta de cada snapshot.
    Solo incluye días con followers_count registrado (desde que se implementó el tracking).
    Agrupa por día Colombia sumando deltas de los 4 slots de 6h.
    """
    from datetime import datetime, timezone, timedelta

    COL = timezone(timedelta(hours=-5))

    # Recopilar snapshots con followers_count, ordenados
    snaps = []
    for key in sorted(history.keys()):
        if key.startswith("_"):
            continue
        meta = history[key].get("_meta", {})
        fc = meta.get("followers_count")
        if fc is None:
            continue
        taken_str = meta.get("taken_at", "")
        try:
            taken_utc = datetime.fromisoformat(taken_str.replace("Z", "+00:00"))
            taken_col = taken_utc.astimezone(COL)
        except Exception:
            continue
        snaps.append({"key": key, "followers": fc, "taken": taken_col})

    if len(snaps) < 2:
        return []

    # Calcular delta entre snapshots consecutivos → agrupar por día Colombia
    by_day = {}
    for i in range(1, len(snaps)):
        prev, curr = snaps[i-1], snaps[i]
        delta = curr["followers"] - prev["followers"]
        day = curr["taken"].strftime("%Y-%m-%d")
        if day not in by_day:
            by_day[day] = {"delta": 0, "followers": curr["followers"]}
        by_day[day]["delta"] += delta

    if not by_day:
        return []

    # Baseline: mediana de los deltas diarios (robusto a picos)
    deltas = [v["delta"] for v in by_day.values()]
    sorted_deltas = sorted(deltas)
    mid = len(sorted_deltas) // 2
    baseline = sorted_deltas[mid] if len(sorted_deltas) % 2 else (sorted_deltas[mid-1] + sorted_deltas[mid]) / 2

    result = []
    for day in sorted(by_day.keys()):
        d = by_day[day]
        result.append({
            "date":      day,
            "delta":     d["delta"],
            "followers": d["followers"],
            "baseline":  round(baseline, 1),
            "organic":   round(max(0, d["delta"] - baseline), 1),
        })

    return result

# ── Website clicks / Profile views serie ─────────────────────

def build_clicks_series(history):
    """
    Construye serie diaria de website_clicks y profile_views
    desde el _meta de cada snapshot (acumula a partir de cuando
    take_snapshot.py empieza a guardarlos).
    """
    COL = timezone(timedelta(hours=-5))
    by_day = {}
    for key in sorted(history.keys()):
        if key.startswith("_"):
            continue
        meta = history[key].get("_meta", {})
        wc   = meta.get("website_clicks")
        pv   = meta.get("profile_views")
        if wc is None and pv is None:
            continue
        taken_str = meta.get("taken_at", "")
        try:
            taken_utc = datetime.fromisoformat(taken_str.replace("Z", "+00:00"))
            day       = taken_utc.astimezone(COL).strftime("%Y-%m-%d")
        except Exception:
            day = key[:10]
        # El valor más reciente del día gana (sobrescribe slots anteriores)
        by_day[day] = {"website_clicks": wc or 0, "profile_views": pv or 0}

    return [{"date": d, **v} for d, v in sorted(by_day.items())]

# ── Tags ─────────────────────────────────────────────────────

CATEGORIES = ["atracción", "conexión", "conversión", "sin etiquetar"]

def load_tags():
    if TAGS_FILE.exists():
        return json.loads(TAGS_FILE.read_text())
    return {}

def save_tags_file(tags):
    TAGS_FILE.write_text(json.dumps(tags, ensure_ascii=False, indent=2))

def load_experiments():
    if EXPERIMENTS_FILE.exists():
        return json.loads(EXPERIMENTS_FILE.read_text())
    return {}

# ── HTML ──────────────────────────────────────────────────────

# Lab JS template — regular string so JS {} don't need escaping
_LAB_JS = """
// ── Lab ─────────────────────────────────────────────────────────────────────
const EXPERIMENTS_INIT = __EXPS__;
const LAB_REACH = __REACH__;
let _experiments = null;

async function _loadExpFromServer() {
  try { const r = await fetch("/experiments"); if (!r.ok) return null; return await r.json(); }
  catch(e) { return null; }
}

function renderLab(exps) {
  _experiments = JSON.parse(JSON.stringify(exps));
  const el = document.getElementById("labExperiments");
  if (!el) return;
  const ids = Object.keys(exps);
  if (!ids.length) {
    el.innerHTML = '<p style="color:#555588;font-size:.82rem;padding:20px 0">Sin experimentos. Pídele a Claude que registre los posts de prueba como experimento.</p>';
    return;
  }
  el.innerHTML = ids.map(id => _buildExpCard(id, exps[id])).join("");
  el.querySelectorAll("[data-lab-field]").forEach(function(inp) {
    inp.addEventListener("blur", function() {
      var card = this.closest("[data-exp-id]");
      if (!card) return;
      var expId = card.dataset.expId;
      var field = this.dataset.labField;
      var vi    = this.dataset.varIdx;
      if (vi !== undefined) {
        _experiments[expId].variants[parseInt(vi)][field] = this.value.trim();
      } else {
        _experiments[expId][field] = this.value.trim();
      }
      _doSaveExp(expId);
    });
  });
}

function _buildExpCard(id, exp) {
  var STATUS = {
    pendiente: {label:"⏳ Pendiente", color:"#fb8c00"},
    en_curso:  {label:"🔬 En curso",  color:"#43a047"},
    listo:     {label:"🔍 Listo para analizar", color:"#5c6bc0"},
    cerrado:   {label:"✅ Cerrado",   color:"#555577"}
  };
  var s        = STATUS[exp.status] || STATUS.pendiente;
  var isClosed = exp.status === "cerrado";
  var winner   = exp.winner_id;
  var emojis   = ["🥇","🥈","🥉","·","·","·"];

  var sorted = (exp.variants || []).map(function(v, i) {
    var r = LAB_REACH[v.post_id] || {};
    return {label:v.label, post_id:v.post_id, what_changed:v.what_changed, permalink:v.permalink,
            idx:i, reach:r.reach||0, saves:r.saves||0, shares:r.shares||0};
  }).sort(function(a,b) { return b.reach - a.reach; });

  var maxR = sorted.length && sorted[0].reach ? sorted[0].reach : 1;

  var varCards = sorted.map(function(v, rank) {
    var isW = winner === v.post_id;
    var bar = Math.round(v.reach / maxR * 100);
    var winBadge  = isW ? '<span class="lab-winner-badge">GANADOR</span>' : "";
    var markBtn   = (!winner && !isClosed)
      ? '<button class="lab-mark-winner" data-eid="' + id + '" data-pid="' + v.post_id + '" onclick="markWinner(this.dataset.eid,this.dataset.pid)">Marcar ganador</button>'
      : "";
    var disAttr = isClosed ? " disabled" : "";
    return '<div class="lab-variant' + (isW ? " lab-winner" : "") + '">'
      + '<div class="lab-variant-header">'
      + '<span class="lab-rank">' + (emojis[rank]||"·") + " " + (v.label||"?") + "</span>"
      + winBadge + markBtn
      + '<a href="' + (v.permalink||"#") + '" target="_blank" class="lab-link">ver ↗</a>'
      + "</div>"
      + '<div class="lab-reach-bar"><div class="lab-reach-fill" style="width:' + bar + '%"></div></div>'
      + '<div class="lab-metrics">'
      + "<span>Reach: <strong>" + v.reach.toLocaleString() + "</strong></span>"
      + "<span>Guardados: <strong>" + v.saves + "</strong></span>"
      + "<span>Compartidos: <strong>" + v.shares + "</strong></span>"
      + "</div>"
      + '<label class="lab-field-label" style="margin-top:8px">¿Qué cambió en esta variante?</label>'
      + '<textarea class="lab-field" data-lab-field="what_changed" data-var-idx="' + v.idx + '"'
      + ' placeholder="ej: hook visual — reloj en muñeca en vez de reloj sobre superficie" rows="2"' + disAttr + ">"
      + (v.what_changed||"") + "</textarea>"
      + "</div>";
  }).join("");

  var expNum  = id.replace("exp_","").replace(/^0+/,"");
  var closeBtn = !isClosed
    ? '<button class="lab-close-btn" data-eid="' + id + '" onclick="closeExp(this.dataset.eid)">Cerrar experimento</button>'
    : '<button class="lab-close-btn" data-eid="' + id + '" style="color:#555588" onclick="reopenExp(this.dataset.eid)">Reabrir</button>';

  return '<div class="card lab-card" data-exp-id="' + id + '"' + (isClosed ? ' style="opacity:.75"' : "") + ">"
    + '<div class="lab-card-header">'
    + '<div style="display:flex;align-items:center;gap:8px">'
    + '<span class="lab-status-badge" style="background:' + s.color + '20;color:' + s.color + ';border:1px solid ' + s.color + '40">' + s.label + "</span>"
    + '<span class="lab-content-type">' + (exp.content_type||"") + "</span>"
    + "</div>"
    + '<span class="lab-card-id">Exp #' + expNum + "</span>"
    + "</div>"
    + '<h3 class="lab-exp-name">&ldquo;' + exp.name + "&rdquo;</h3>"
    + '<div style="margin-bottom:16px">'
    + '<label class="lab-field-label">Variable testeada</label>'
    + '<input class="lab-field" data-lab-field="variable_tested"'
    + ' placeholder="ej: hook visual — primeros 3 segundos del video"'
    + ' value="' + (exp.variable_tested||"").replace(/"/g,"&quot;") + '"' + (isClosed ? " disabled" : "") + ">"
    + "</div>"
    + '<div class="lab-variants">' + varCards + "</div>"
    + '<div style="margin-bottom:16px">'
    + '<label class="lab-field-label">💡 Aprendizaje</label>'
    + '<textarea class="lab-field lab-insight-field" data-lab-field="insight"'
    + ' placeholder="ej: hooks con reloj en muñeca generan 3x más reach para audiencia nueva" rows="3"' + (isClosed ? " disabled" : "") + ">"
    + (exp.insight||"") + "</textarea>"
    + "</div>"
    + '<div class="lab-actions">' + closeBtn
    + ' <span id="lab-saved-' + id + '" style="font-size:.68rem;color:#43a047;display:none">✓ guardado</span>'
    + "</div>"
    + "</div>";
}

async function _doSaveExp(expId, cb) {
  try {
    var r = await fetch("/save-experiment", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({id: expId, data: _experiments[expId]})
    });
    if (r.ok) {
      var el = document.getElementById("lab-saved-" + expId);
      if (el) { el.style.display = "inline"; setTimeout(function(){ el.style.display = "none"; }, 2000); }
      if (cb) cb();
    }
  } catch(e) { console.error("Lab save:", e); }
}

function markWinner(expId, postId) {
  if (!_experiments[expId]) return;
  _experiments[expId].winner_id = postId;
  _experiments[expId].status = "listo";
  _doSaveExp(expId, function(){ renderLab(_experiments); });
}

function closeExp(expId) {
  if (!_experiments[expId]) return;
  _experiments[expId].status = "cerrado";
  _experiments[expId].decided_at = new Date().toISOString().slice(0,10);
  _doSaveExp(expId, function(){ renderLab(_experiments); });
}

function reopenExp(expId) {
  if (!_experiments[expId]) return;
  _experiments[expId].status = "pendiente";
  _experiments[expId].decided_at = null;
  _doSaveExp(expId, function(){ renderLab(_experiments); });
}

function showTab(tab) {
  document.getElementById("dashContent").style.display = tab === "dash" ? "" : "none";
  document.getElementById("labContent").style.display  = tab === "lab"  ? "" : "none";
  document.getElementById("tabBtnDash").classList.toggle("active", tab === "dash");
  document.getElementById("tabBtnLab").classList.toggle("active",  tab === "lab");
}

(async function initLab() {
  var fromServer = await _loadExpFromServer();
  renderLab(fromServer || EXPERIMENTS_INIT || {});
})();
"""

COLORS = [
    "#5c6bc0","#43a047","#fb8c00","#e91e63","#00897b",
    "#8e24aa","#1e88e5","#f4511e","#39ac73","#c0ca33"
]
TAG_COLORS = {
    "atracción":     "#e91e63",
    "conexión":      "#43a047",
    "conversión":    "#1e88e5",
    "sin etiquetar": "#555577",
}

def build_html(perfil, insights, posts, demo, history):
    # insights puede ser {7: {...}, 14: {...}, 28: {...}} o dict plano (legacy)
    if isinstance(insights, dict) and 7 in insights:
        insights_by_window = {str(k): v for k, v in insights.items()}
        ins28 = insights.get(28, {})
    else:
        insights_by_window = {"7": insights, "14": insights, "28": insights}
        ins28 = insights

    updated   = datetime.now().strftime("%d %b %Y, %I:%M %p")
    followers = perfil.get("followers_count", 0)

    # Valores por defecto para el render inicial (28d)
    reach    = ins28.get("reach", 0)
    pviews   = ins28.get("profile_views", 0)
    wclicks  = ins28.get("website_clicks", 0)
    fgained  = ins28.get("follower_count", 0)
    inter    = ins28.get("total_interactions", 0)
    likes    = ins28.get("likes", 0)
    comments = ins28.get("comments", 0)
    shares   = ins28.get("shares", 0)
    saves    = ins28.get("saves", 0)

    raw_tags  = load_tags()
    pinned_ids = raw_tags.pop("_pinned", [])
    tags       = raw_tags
    pinned_set = set(pinned_ids)
    eng_rate = round(inter / reach * 100, 2) if reach else 0

    reach_labels = json.dumps([d["date"] for d in ins28.get("reach_daily", [])])

    # ── Follower growth — delta entre snapshots ───────────────
    follower_series = build_follower_series(history, [])
    reach_values = json.dumps([d["value"] for d in ins28.get("reach_daily", [])])
    insights_json = json.dumps(insights_by_window)

    # ── Website clicks / Profile views — desde snapshots ─────
    clicks_series = build_clicks_series(history)

    # Growth data — ranking (solo posts desde primer snapshot) y modal (todos)
    growth_posts   = build_growth_data(history)
    all_posts_data = build_growth_data_all(history)

    def enrich_post(p, tag):
        p["tag"] = tag
        series = p["series"]
        last   = series[-1] if series else {}
        hours  = last.get("hours") or 0
        p["vida_util"] = round(last.get("reach", 0) / hours, 2) if hours > 0 else 0
        p["vu_series"] = [
            {"hours": s.get("hours", 0),
             "vu": round(s.get("reach", 0) / s.get("hours", 1), 2) if s.get("hours", 0) > 0 else 0}
            for s in series
        ]
        # Alcance a las 48h: snapshot más cercano a 48h de vida
        snap_48 = min(series, key=lambda s: abs(s.get("hours", 0) - 48)) if series else None
        p["reach_48h"]       = snap_48.get("reach", 0) if snap_48 else 0
        p["reach_48h_hours"] = round(snap_48.get("hours", 0), 1) if snap_48 else 0

    for p in growth_posts:
        enrich_post(p, tags.get(p["id"], "sin etiquetar"))

    for p in all_posts_data:
        enrich_post(p, tags.get(p["id"], "sin etiquetar"))

    growth_json    = json.dumps(growth_posts, ensure_ascii=False)
    all_posts_json = json.dumps(all_posts_data, ensure_ascii=False)
    colors_json    = json.dumps(COLORS)
    categories_json = json.dumps(CATEGORIES)
    tag_colors_json = json.dumps(TAG_COLORS)
    pinned_json          = json.dumps(list(pinned_set))
    follower_series_json = json.dumps(follower_series, ensure_ascii=False)
    clicks_series_json   = json.dumps(clicks_series, ensure_ascii=False)

    # Lab — reach map por post y experimentos
    lab_reach_map = {}
    for p in all_posts_data:
        if p["series"]:
            last = p["series"][-1]
            lab_reach_map[p["id"]] = {
                "reach":  last.get("reach", 0),
                "saves":  last.get("saved", 0),
                "shares": last.get("shares", 0),
            }
    experiments     = load_experiments()
    experiments_str = json.dumps(experiments, ensure_ascii=False)
    lab_reach_str   = json.dumps(lab_reach_map, ensure_ascii=False)
    lab_js = _LAB_JS.replace("__EXPS__", experiments_str).replace("__REACH__", lab_reach_str)

    # ── Sección: Conclusiones probadas ───────────────────────
    # ── Playbook: reglas cortas de experimentos cerrados válidos ──
    PLAYBOOK_RULES = []
    for exp_id, exp in experiments.items():
        if not isinstance(exp, dict) or exp.get("status") != "cerrado":
            continue
        insight = exp.get("insight", "").strip()
        if not insight or insight.startswith("⚠️"):
            continue
        # Extraer reglas del insight (frases separadas por —)
        PLAYBOOK_RULES.append({
            "title": exp.get("name", exp_id),
            "rules": insight,
            "source": exp_id.replace("_", " ").upper(),
        })

    playbook_html = ""
    for r in PLAYBOOK_RULES:
        # Partir el insight en frases cortas en puntos separados por "."
        sentences = [s.strip() for s in r["rules"].replace("✅", "").split(".") if s.strip() and len(s.strip()) > 10]
        items_html = "".join(
            f'<li style="margin-bottom:6px;color:#cccce0;font-size:.8rem;line-height:1.5">{s}.</li>'
            for s in sentences
        )
        playbook_html += (
            f'<div style="background:rgba(0,255,165,.05);border-left:3px solid #00ffa5;border-radius:8px;'
            f'padding:14px 16px;margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<strong style="font-size:.82rem;color:#eeeeff">{r["title"]}</strong>'
            f'<span style="font-size:.65rem;background:#00ffa522;color:#00ffa5;border-radius:4px;padding:2px 7px">{r["source"]}</span>'
            f'</div>'
            f'<ul style="margin:0;padding-left:16px">{items_html}</ul>'
            f'</div>'
        )
    if not playbook_html:
        playbook_html = '<p style="color:#555588;font-size:.82rem">Aún no hay experimentos cerrados con resultados válidos.</p>'

    # ── Árbol de decisión ────────────────────────────────────
    decision_tree_html = """
<div style="font-size:.8rem;line-height:1.6">
  <p style="color:#8888aa;margin:0 0 14px">Antes de grabar variantes, responde estas preguntas:</p>

  <div style="background:rgba(255,255,255,.04);border-radius:8px;padding:14px 16px;margin-bottom:8px">
    <strong style="color:#eeeeff">¿Los fotogramas del video son idénticos entre variantes?</strong>
    <div style="margin-top:10px;padding-left:14px;border-left:2px solid #333355">
      <div style="margin-bottom:8px">
        <span style="color:#ff5555">→ Sí</span>
        <span style="color:#8888aa"> (mismo clip, diferente texto/audio/música)</span><br>
        <span style="background:rgba(255,85,85,.1);color:#ff8888;border-radius:6px;padding:4px 10px;display:inline-block;margin-top:4px;font-size:.75rem">
          ❌ No uses Trial Reels — Instagram detecta el duplicado y suprime todas las variantes excepto la primera. No aprenderás nada del hook.
        </span>
      </div>
      <div>
        <span style="color:#00ffa5">→ No</span>
        <span style="color:#8888aa"> (videos genuinamente distintos)</span><br>
        <div style="margin-top:8px;padding-left:14px;border-left:2px solid #333355">
          <strong style="color:#eeeeff">¿El hook cambia desde el segundo 1 en los fotogramas?</strong>
          <div style="margin-top:8px;padding-left:14px;border-left:2px solid #333355">
            <div style="margin-bottom:8px">
              <span style="color:#00ffa5">→ Sí</span>
              <span style="color:#8888aa"> (cara en cámara con guión diferente, o B-roll de apertura distinto)</span><br>
              <span style="background:rgba(0,255,165,.08);color:#00ffa5;border-radius:6px;padding:4px 10px;display:inline-block;margin-top:4px;font-size:.75rem">
                ✅ Puedes subirlos en ráfaga como Trial Reels — el fingerprint los trata como contenido distinto.
              </span>
            </div>
            <div>
              <span style="color:#fb8c00">→ No del todo</span>
              <span style="color:#8888aa"> (mismo B-roll, diferente orden de clips o cortes sutiles)</span><br>
              <span style="background:rgba(251,140,0,.08);color:#ffbb55;border-radius:6px;padding:4px 10px;display:inline-block;margin-top:4px;font-size:.75rem">
                ⚠️ Zona de riesgo — el fingerprint puede o no detectarlo. Si el experimento importa, espera 24h entre variantes o usa B-roll diferente de apertura.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>"""

    # Número de snapshots
    num_snapshots = len(history)
    first_snapshot = min(history.keys()) if history else "—"

    # Posts table
    posts_rows = ""
    for p in posts:
        caption  = (p.get("caption") or "").replace("\n", " ")[:120]
        kind_icon = {"IMAGE": "🖼️", "VIDEO": "🎥", "CAROUSEL_ALBUM": "🎞️"}.get(p.get("media_type",""), "📄")
        r = p.get("metric_reach", 0)
        eng = round((p.get("like_count",0) + p.get("comments_count",0)) / r * 100, 1) if r else 0
        pub = p.get("timestamp","")[:10]
        pid = p.get("id","")
        post_tag = tags.get(pid, "sin etiquetar")
        tag_color = TAG_COLORS.get(post_tag, "#555577")
        try:
            days_old = (datetime.now().date() - datetime.strptime(pub, "%Y-%m-%d").date()).days
        except Exception:
            days_old = "?"
        cat_options = "".join(
            f'<option value="{c}" {"selected" if c==post_tag else ""}>{c}</option>'
            for c in CATEGORIES
        )
        is_pinned   = pid in pinned_set
        pin_icon    = "📌" if is_pinned else "📍"
        pin_title   = "Fijado — excluido de insights" if is_pinned else "Marcar como fijado en el perfil"
        pin_cls     = " pin-active" if is_pinned else ""
        posts_rows += f"""
        <tr class="clickable" data-pid="{pid}" onclick="openModal(this.dataset.pid)">
          <td>{pub}<br><small style="color:#666">{days_old}d</small></td>
          <td class="caption">{caption}</td>
          <td class="center">{kind_icon}</td>
          <td class="center">
            <select class="tag-select" data-pid="{pid}" style="border-color:{tag_color};color:{tag_color}"
                    onclick="event.stopPropagation()" onchange="saveTag(this)">
              {cat_options}
            </select>
          </td>
          <td class="center">
            <button class="pin-btn{pin_cls}" data-pid="{pid}" title="{pin_title}"
                    onclick="event.stopPropagation(); togglePin(this.dataset.pid)">{pin_icon}</button>
          </td>
          <td class="num">{p.get("like_count",0):,}</td>
          <td class="num">{p.get("comments_count",0):,}</td>
          <td class="num">{r:,}</td>
          <td class="num">{p.get("metric_saved",0):,}</td>
          <td class="num">{p.get("metric_shares",0):,}</td>
          <td class="num">{eng}%</td>
          <td class="center"><a href="{p.get("permalink","")}" target="_blank" onclick="event.stopPropagation()">↗</a></td>
        </tr>"""

    # Demographics
    age_rows = ""
    for r in sorted(parse_breakdowns(demo.get("age_gender")), key=lambda x: -x["value"])[:12]:
        label = " / ".join(r.get("dimension_values", []))
        age_rows += f'<tr><td>{label}</td><td class="num">{r["value"]:,}</td></tr>'

    country_rows = ""
    for r in sorted(parse_breakdowns(demo.get("country")), key=lambda x: -x["value"])[:10]:
        label = r.get("dimension_values", [""])[0]
        country_rows += f'<tr><td>{label}</td><td class="num">{r["value"]:,}</td></tr>'

    city_rows = ""
    for r in sorted(parse_breakdowns(demo.get("city")), key=lambda x: -x["value"])[:10]:
        label = r.get("dimension_values", [""])[0]
        city_rows += f'<tr><td>{label}</td><td class="num">{r["value"]:,}</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Serrat Relojes — Dashboard Instagram</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f0f1a;color:#e0e0f0;min-height:100vh}}
  .top-bar{{background:#1a1a2e;padding:18px 32px;display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid #2d2d55}}
  .top-bar h1{{font-size:1.3rem;font-weight:700;color:#fff}}
  .top-bar .updated{{font-size:0.75rem;color:#8888aa}}
  .content{{max-width:1300px;margin:0 auto;padding:24px}}
  h2{{font-size:.85rem;font-weight:600;color:#9090cc;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;margin-top:28px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}}
  .kpi{{background:#1a1a2e;border-radius:10px;padding:18px;border:1px solid #2a2a44;position:relative;overflow:hidden}}
  .kpi::before{{content:"";position:absolute;top:0;left:0;width:4px;height:100%;background:var(--accent,#5c6bc0)}}
  .kpi .label{{font-size:.7rem;color:#8888aa;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}}
  .kpi .value{{font-size:1.8rem;font-weight:700;color:#fff;line-height:1}}
  .kpi .sub{{font-size:.68rem;color:#6666aa;margin-top:4px}}
  .kpi.green{{--accent:#43a047}}.kpi.blue{{--accent:#1e88e5}}.kpi.purple{{--accent:#8e24aa}}
  .kpi.orange{{--accent:#fb8c00}}.kpi.teal{{--accent:#00897b}}.kpi.pink{{--accent:#e91e63}}
  .card{{background:#1a1a2e;border-radius:10px;padding:22px;border:1px solid #2a2a44;margin-top:20px}}
  .table-wrap{{overflow-x:auto;margin-top:14px;border-radius:10px;border:1px solid #2a2a44}}
  table{{width:100%;border-collapse:collapse;font-size:.8rem}}
  thead tr{{background:#16213e}}
  thead th{{padding:10px 12px;text-align:left;color:#9090cc;font-weight:600;white-space:nowrap;font-size:.72rem;text-transform:uppercase;letter-spacing:.5px}}
  tbody tr{{border-top:1px solid #1e1e38;transition:background .15s}}
  tbody tr:hover{{background:#1e1e38}}
  tbody td{{padding:9px 12px;color:#cccce0;vertical-align:middle}}
  .caption{{max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .num{{text-align:right;font-variant-numeric:tabular-nums}}
  .center{{text-align:center}}
  a{{color:#7986cb;text-decoration:none}}
  a:hover{{color:#aab4ff}}
  .demo-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
  .demo-box{{background:#1a1a2e;border-radius:10px;padding:18px;border:1px solid #2a2a44}}
  .demo-box h3{{font-size:.75rem;color:#9090cc;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px}}

  /* Controls */
  .controls{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;align-items:center}}
  .ctrl-label{{font-size:.72rem;color:#8888aa;text-transform:uppercase;letter-spacing:.5px;margin-right:2px}}
  .btn-group{{display:flex;gap:6px;flex-wrap:wrap}}
  .btn{{padding:5px 14px;border-radius:20px;border:1px solid #3a3a5c;background:transparent;
        color:#9090cc;cursor:pointer;font-size:.75rem;transition:all .15s}}
  .btn:hover{{background:#2a2a44;color:#fff}}
  .btn.active{{background:#5c6bc0;border-color:#5c6bc0;color:#fff;font-weight:600}}
  .snapshot-info{{font-size:.72rem;color:#555588;margin-left:auto}}
  /* Modal */
  .modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;
                  display:flex;align-items:center;justify-content:center;padding:20px;
                  opacity:0;pointer-events:none;transition:opacity .2s}}
  .modal-overlay.open{{opacity:1;pointer-events:all}}
  .modal{{background:#1a1a2e;border:1px solid #3a3a5c;border-radius:14px;
          width:100%;max-width:820px;max-height:90vh;overflow-y:auto;padding:28px;
          transform:translateY(16px);transition:transform .2s}}
  .modal-overlay.open .modal{{transform:translateY(0)}}
  .modal-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px}}
  .modal-title{{font-size:1rem;font-weight:700;color:#fff;max-width:88%;line-height:1.4}}
  .modal-meta{{font-size:.75rem;color:#8888aa;margin-bottom:18px}}
  .modal-close{{background:none;border:none;color:#666;cursor:pointer;font-size:1.4rem;
                line-height:1;padding:0;margin-left:8px;flex-shrink:0}}
  .modal-close:hover{{color:#fff}}
  .modal-metric-btns{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px}}
  .modal-stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:20px}}
  .modal-stat{{background:#13132a;border-radius:8px;padding:12px;text-align:center}}
  .modal-stat .s-label{{font-size:.65rem;color:#8888aa;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
  .modal-stat .s-value{{font-size:1.3rem;font-weight:700;color:#fff}}
  tbody tr.clickable{{cursor:pointer}}
  tbody tr.clickable:hover td{{background:#222240}}
  .tag-select{{background:#13132a;border:1px solid #3a3a5c;border-radius:12px;
              padding:3px 8px;font-size:.7rem;cursor:pointer;outline:none;
              transition:border-color .15s;max-width:120px}}
  .tag-select:hover{{background:#1e1e38}}
  .insight-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:4px}}
  .insight-box{{background:#13132a;border-radius:10px;padding:18px;border:1px solid #2a2a44}}
  .insight-box h3{{font-size:.72rem;color:#9090cc;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px}}
  .insight-row{{display:flex;align-items:center;gap:10px;margin-bottom:10px}}
  .insight-label{{font-size:.75rem;color:#cccce0;min-width:90px}}
  .insight-bar-wrap{{flex:1;background:#1e1e38;border-radius:4px;height:8px;overflow:hidden}}
  .insight-bar{{height:100%;border-radius:4px;transition:width .4s}}
  .insight-val{{font-size:.75rem;color:#fff;font-weight:600;min-width:52px;text-align:right}}
  .insight-note{{font-size:.65rem;color:#444466;margin-top:6px;text-align:center}}
  .save-tags-btn{{background:#5c6bc0;border:none;color:#fff;padding:6px 16px;border-radius:20px;
                  cursor:pointer;font-size:.75rem;display:none;margin-left:auto}}
  .save-tags-btn:hover{{background:#7986cb}}
  .save-tags-wrap{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
  .save-tags-note{{font-size:.68rem;color:#444466;display:none}}
  .pin-btn{{background:none;border:none;cursor:pointer;font-size:.95rem;padding:1px 4px;
            border-radius:6px;opacity:.4;transition:opacity .15s}}
  .pin-btn:hover{{opacity:1}}
  .pin-btn.pin-active{{opacity:1}}
  /* Tab nav */
  .tab-nav{{display:flex;gap:0;margin-bottom:28px;border-bottom:2px solid #2a2a44}}
  .tab-btn{{padding:10px 24px;background:none;border:none;border-bottom:2px solid transparent;
            color:#8888aa;cursor:pointer;font-size:.85rem;margin-bottom:-2px;transition:all .15s}}
  .tab-btn.active{{color:#fff;border-bottom-color:#5c6bc0;font-weight:600}}
  .tab-btn:hover{{color:#cccce0}}
  /* Lab */
  .lab-card{{margin-bottom:20px}}
  .lab-card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
  .lab-card-id{{font-size:.7rem;color:#555588}}
  .lab-status-badge{{font-size:.68rem;padding:3px 10px;border-radius:20px;font-weight:600}}
  .lab-content-type{{font-size:.68rem;color:#8888aa;margin-left:8px;text-transform:capitalize}}
  .lab-exp-name{{font-size:.95rem;font-weight:600;color:#fff;margin:0 0 16px}}
  .lab-field-label{{display:block;font-size:.68rem;color:#8888aa;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
  .lab-field{{width:100%;background:#13132a;border:1px solid #2a2a44;border-radius:8px;
              padding:10px 12px;color:#cccce0;font-size:.8rem;font-family:inherit;
              resize:vertical;transition:border-color .15s;box-sizing:border-box}}
  .lab-field:focus{{outline:none;border-color:#5c6bc0}}
  .lab-field:disabled{{opacity:.5;cursor:not-allowed}}
  .lab-insight-field{{min-height:70px}}
  .lab-variants{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-bottom:16px}}
  .lab-variant{{background:#13132a;border:1px solid #2a2a44;border-radius:10px;padding:14px}}
  .lab-variant.lab-winner{{border-color:#43a04760;background:#43a04710}}
  .lab-variant-header{{display:flex;align-items:center;gap:6px;margin-bottom:8px;flex-wrap:wrap}}
  .lab-rank{{font-size:.82rem;font-weight:600;color:#fff}}
  .lab-link{{font-size:.7rem;color:#7986cb;margin-left:auto}}
  .lab-winner-badge{{font-size:.62rem;background:#43a047;color:#fff;padding:2px 8px;border-radius:10px;font-weight:700}}
  .lab-mark-winner{{font-size:.62rem;background:none;border:1px solid #3a3a5c;color:#8888aa;
                    padding:2px 8px;border-radius:10px;cursor:pointer}}
  .lab-mark-winner:hover{{border-color:#5c6bc0;color:#fff}}
  .lab-reach-bar{{height:4px;background:#1e1e38;border-radius:2px;margin-bottom:8px;overflow:hidden}}
  .lab-reach-fill{{height:100%;background:#5c6bc0;border-radius:2px}}
  .lab-variant.lab-winner .lab-reach-fill{{background:#43a047}}
  .lab-metrics{{display:flex;gap:12px;font-size:.72rem;color:#8888aa;margin-bottom:10px;flex-wrap:wrap}}
  .lab-metrics strong{{color:#cccce0}}
  .lab-actions{{display:flex;align-items:center;gap:12px}}
  .lab-close-btn{{background:#1e1e38;border:1px solid #3a3a5c;color:#cccce0;
                  padding:6px 16px;border-radius:20px;cursor:pointer;font-size:.75rem}}
  .lab-close-btn:hover{{border-color:#5c6bc0;color:#fff}}
</style>
</head>
<body>

<div class="top-bar">
  <h1>⌚ Serrat Relojes — Dashboard Instagram</h1>
  <span class="updated">Actualizado: {updated}</span>
</div>

<div class="content">

  <!-- TAB NAV -->
  <nav class="tab-nav">
    <button class="tab-btn active" id="tabBtnDash" onclick="showTab('dash')">📊 Dashboard</button>
    <button class="tab-btn" id="tabBtnLab" onclick="showTab('lab')">🧪 Lab</button>
  </nav>

  <div id="dashContent">

  <!-- KPIs estáticos -->
  <h2>Cuenta</h2>
  <div class="kpi-grid">
    <div class="kpi green">
      <div class="label">Seguidores</div>
      <div class="value">{followers:,}</div>
      <div class="sub">total actual</div>
    </div>
  </div>

  <!-- KPIs con filtro de tiempo -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-top:28px;margin-bottom:14px">
    <h2 style="margin:0">Métricas del período</h2>
    <div class="btn-group" id="windowBtns">
      <button class="btn" data-w="7">7 días</button>
      <button class="btn" data-w="14">14 días</button>
      <button class="btn active" data-w="28">28 días</button>
    </div>
  </div>
  <div class="kpi-grid" id="kpiPeriod">
    <div class="kpi blue"><div class="label">Alcance</div><div class="value kpi-val" data-key="reach">{reach:,}</div></div>
    <div class="kpi purple"><div class="label">Visitas de perfil</div><div class="value kpi-val" data-key="profile_views">{pviews:,}</div></div>
    <div class="kpi orange"><div class="label">Clics al sitio web</div><div class="value kpi-val" data-key="website_clicks">{wclicks:,}</div></div>
    <div class="kpi teal"><div class="label">Seguidores ganados</div><div class="value kpi-val" data-key="follower_count">{fgained:,}</div></div>
    <div class="kpi pink"><div class="label">Tasa de engagement</div><div class="value" id="kpiEng">{eng_rate}%</div><div class="sub">interacciones / alcance</div></div>
  </div>

  <div class="kpi-grid" style="margin-top:14px">
    <div class="kpi blue"><div class="label">Total interacciones</div><div class="value kpi-val" data-key="total_interactions">{inter:,}</div></div>
    <div class="kpi pink"><div class="label">Likes</div><div class="value kpi-val" data-key="likes">{likes:,}</div></div>
    <div class="kpi purple"><div class="label">Comentarios</div><div class="value kpi-val" data-key="comments">{comments:,}</div></div>
    <div class="kpi teal"><div class="label">Compartidos</div><div class="value kpi-val" data-key="shares">{shares:,}</div></div>
    <div class="kpi orange"><div class="label">Guardados</div><div class="value kpi-val" data-key="saves">{saves:,}</div></div>
  </div>

  <div class="card" style="margin-top:20px">
    <h2 style="margin-top:0">Alcance diario <span id="reachChartLabel">(28d)</span></h2>
    <canvas id="reachChart" style="max-height:200px"></canvas>
  </div>

  <!-- RANKING POR VIDA ÚTIL -->
  <div class="card">
    <h2 style="margin-top:0">Ranking de posts <small style="font-size:.65rem;color:#555588;font-weight:400;text-transform:none;letter-spacing:0">— basado en alcance a las 48h de vida</small></h2>
    <div class="controls">
      <span class="ctrl-label">Ordenar por:</span>
      <div class="btn-group" id="metricBtns">
        <button class="btn active" data-metric="reach_48h">Alcance 48h</button>
        <button class="btn" data-metric="vida_util">Vida útil</button>
        <button class="btn" data-metric="reach">Alcance total</button>
        <button class="btn" data-metric="likes">Likes</button>
      </div>
      <span class="snapshot-info">📸 {num_snapshots} snapshots · desde {first_snapshot}</span>
    </div>
    <p id="noDataMsg" style="color:#555588;font-size:.8rem;text-align:center;padding:30px 0;display:none">
      Aún no hay posts rastreados desde {first_snapshot}. 📅
    </p>
    <canvas id="rankingChart" style="max-height:380px"></canvas>
  </div>

  <!-- FOLLOWER GROWTH -->
  <div class="card" id="followerGrowthCard">
    <h2 style="margin-top:0">Seguidores ganados por día
      <small style="font-size:.65rem;color:#555588;font-weight:400;text-transform:none;letter-spacing:0">
        — orgánico estimado vs baseline de pauta constante
      </small>
    </h2>
    <div id="followerNoData" style="display:none;color:#555588;font-size:.8rem;padding:20px 0;text-align:center">
      Aún no hay suficientes snapshots con conteo de seguidores.<br>
      Los datos se acumularán a partir del próximo cron. 📅
    </div>
    <canvas id="followerChart" style="max-height:220px"></canvas>
    <p id="followerNote" style="font-size:.68rem;color:#444466;margin-top:10px;text-align:center"></p>
  </div>

  <!-- WEBSITE CLICKS -->
  <div class="card" id="clicksCard">
    <h2 style="margin-top:0">Clics al sitio web por día
      <small style="font-size:.65rem;color:#555588;font-weight:400;text-transform:none;letter-spacing:0">
        — correlación con contenido publicado · últimos 28 días
      </small>
    </h2>
    <div style="display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap">
      <button class="btn active" id="clicksMetricClicks" onclick="switchClicksMetric('clicks')">Clics al sitio</button>
      <button class="btn" id="clicksMetricViews" onclick="switchClicksMetric('views')">Visitas de perfil</button>
      <button class="btn" id="clicksMetricBoth" onclick="switchClicksMetric('both')">Ambas</button>
    </div>
    <div id="clicksNoData" style="display:none;color:#555588;font-size:.8rem;padding:20px 0;text-align:center">
      No hay datos de clics disponibles para este período. 📅
    </div>
    <canvas id="clicksChart" style="max-height:240px"></canvas>
    <p id="clicksNote" style="font-size:.68rem;color:#444466;margin-top:10px;text-align:center"></p>
  </div>

  <!-- INSIGHTS -->
  <h2>¿Qué funciona mejor? <small style="font-size:.65rem;color:#555588;font-weight:400;text-transform:none;letter-spacing:0">— alcance promedio a las 48h por categoría</small></h2>
  <div class="insight-grid">
    <div class="insight-box">
      <h3>Por formato</h3>
      <div id="insightFormat"><p style="color:#444466;font-size:.75rem">Cargando…</p></div>
      <p class="insight-note">alcance 48h promedio · reach total entre paréntesis</p>
    </div>
    <div class="insight-box">
      <h3>Por etapa del embudo</h3>
      <div id="insightTag"><p style="color:#444466;font-size:.75rem">Cargando…</p></div>
      <p class="insight-note">etiqueta los posts en la tabla para ver este análisis</p>
    </div>
    <div class="insight-box">
      <h3>Por hora de publicación</h3>
      <div id="insightHour"><p style="color:#444466;font-size:.75rem">Cargando…</p></div>
      <p class="insight-note">mañana (&lt;12h) · tarde (12-18h) · noche (&gt;18h) hora Colombia</p>
    </div>
  </div>

  <h2>Últimos 30 posts <small style="color:#555588;font-size:.7rem;font-weight:400">— haz clic en cualquier fila para ver su historial · cambia el tipo de contenido con el selector</small></h2>
  <div class="save-tags-wrap">
    <span class="save-tags-note" id="tagsNote">Cambios sin guardar</span>
    <button class="save-tags-btn" id="saveTagsBtn" onclick="saveTags()">💾 Guardar etiquetas</button>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Fecha</th><th>Caption</th><th>Formato</th><th>Tipo contenido</th>
          <th class="center" title="Posts fijados en el perfil — excluidos de los insights">📌</th>
          <th class="num">Likes</th><th class="num">Coments</th>
          <th class="num">Alcance</th><th class="num">Guardados</th>
          <th class="num">Compartidos</th><th class="num">Eng%</th><th>Link</th>
        </tr>
      </thead>
      <tbody>{posts_rows}</tbody>
    </table>
  </div>

<!-- Modal detalle de post -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title" id="modalTitle"></div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-meta" id="modalMeta"></div>
    <div class="modal-stats" id="modalStats"></div>
    <div class="modal-metric-btns" id="modalMetricBtns">
      <span style="font-size:.7rem;color:#8888aa;align-self:center;margin-right:4px">VER:</span>
      <button class="btn active" data-m="vida_util">Vida útil</button>
      <button class="btn" data-m="reach">Alcance</button>
      <button class="btn" data-m="likes">Likes</button>
      <button class="btn" data-m="saved">Guardados</button>
    </div>
    <canvas id="modalChart" style="max-height:280px"></canvas>
    <p id="modalNoData" style="color:#555588;font-size:.8rem;text-align:center;padding:30px 0;display:none">
      Aún no hay suficientes snapshots para mostrar la curva de este post. Vuelve mañana. 📅
    </p>
  </div>
</div>

  <h2>Audiencia</h2>
  <div class="demo-grid">
    <div class="demo-box">
      <h3>Edad y género</h3>
      <div class="table-wrap" style="border:none">
        <table><tbody>{age_rows}</tbody></table>
      </div>
    </div>
    <div class="demo-box">
      <h3>Top países</h3>
      <div class="table-wrap" style="border:none">
        <table><tbody>{country_rows}</tbody></table>
      </div>
    </div>
    <div class="demo-box">
      <h3>Top ciudades</h3>
      <div class="table-wrap" style="border:none">
        <table><tbody>{city_rows}</tbody></table>
      </div>
    </div>
  </div>

  </div><!-- end dashContent -->

  <!-- LAB TAB -->
  <div id="labContent" style="display:none">
    <div style="margin:0 0 24px">
      <h2 style="margin:0 0 6px;font-size:1.05rem;color:#fff;text-transform:none;letter-spacing:0">🧪 Laboratorio de experimentos</h2>
      <p style="font-size:.78rem;color:#8888aa;margin:0">Documenta qué cambió en cada variante · los datos los muestra el sistema · <strong style="color:#cccce0">juntos llegamos al insight</strong></p>
    </div>

    <!-- Playbook colapsible -->
    <details style="margin-bottom:12px;background:rgba(0,255,165,.03);border:1px solid rgba(0,255,165,.12);border-radius:10px;padding:0">
      <summary style="cursor:pointer;padding:14px 16px;font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#00ffa5;list-style:none;display:flex;justify-content:space-between;align-items:center">
        📖 Playbook — lo que ya funciona
        <span style="font-size:.7rem;color:#00ffa588;font-weight:400;text-transform:none;letter-spacing:0">▾ expandir</span>
      </summary>
      <div style="padding:4px 16px 16px">
        {playbook_html}
      </div>
    </details>

    <!-- Árbol de decisión colapsible -->
    <details style="margin-bottom:24px;background:rgba(124,111,255,.03);border:1px solid rgba(124,111,255,.15);border-radius:10px;padding:0">
      <summary style="cursor:pointer;padding:14px 16px;font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#7c6fff;list-style:none;display:flex;justify-content:space-between;align-items:center">
        🔀 ¿Puedo hacer este experimento con Trial Reels?
        <span style="font-size:.7rem;color:#7c6fff88;font-weight:400;text-transform:none;letter-spacing:0">▾ expandir</span>
      </summary>
      <div style="padding:4px 16px 16px">
        {decision_tree_html}
      </div>
    </details>

    <!-- Experimentos -->
    <h3 style="font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:#8888aa;margin:0 0 14px;font-weight:700">🧪 Experimentos</h3>
    <div id="labExperiments">
      <p style="color:#555588;font-size:.82rem">Cargando…</p>
    </div>
  </div>

</div>

<script>
// ── Filtro de ventana temporal ───────────────────────────────
const INSIGHTS = {insights_json};
let reachChart = null;

function fmt(n) {{ return (n||0).toLocaleString("es-CO"); }}

function renderWindow(w) {{
  const ins = INSIGHTS[String(w)] || {{}};

  // Actualizar KPIs
  document.querySelectorAll(".kpi-val").forEach(el => {{
    el.textContent = fmt(ins[el.dataset.key]);
  }});

  // Engagement
  const eng = ins.total_interactions && ins.reach
    ? (ins.total_interactions / ins.reach * 100).toFixed(2) + "%"
    : "0%";
  document.getElementById("kpiEng").textContent = eng;

  // Gráfico de alcance
  const daily = ins.reach_daily || [];
  const labels = daily.map(d => d.date);
  const values = daily.map(d => d.value);
  document.getElementById("reachChartLabel").textContent = `(${{w}}d)`;

  if (reachChart) reachChart.destroy();
  reachChart = new Chart(document.getElementById("reachChart").getContext("2d"), {{
    type: "bar",
    data: {{
      labels,
      datasets: [{{
        label: "Alcance",
        data: values,
        backgroundColor: "rgba(92,107,192,0.7)",
        borderColor: "#5c6bc0",
        borderWidth: 1,
        borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: "#8888aa", maxTicksLimit: 14 }}, grid: {{ color: "#1e1e38" }} }},
        y: {{ ticks: {{ color: "#8888aa" }}, grid: {{ color: "#1e1e38" }} }}
      }}
    }}
  }});
}}

document.querySelectorAll("#windowBtns .btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll("#windowBtns .btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    renderWindow(parseInt(btn.dataset.w));
  }});
}});

renderWindow(28); // render inicial


// ── Ranking de posts ─────────────────────────────────────────
const GROWTH_POSTS  = {growth_json};
const COLORS        = {colors_json};
const TAG_COLORS    = {tag_colors_json};
const CATEGORIES    = {categories_json};
const METRIC_LABELS = {{ reach_48h:"Alcance 48h", vida_util:"Vida útil (reach/h)", reach:"Alcance total", likes:"Likes" }};

let currentMetric = "reach_48h";
let rankingChart  = null;

// Tags y posts fijados — se cargan desde el servidor al iniciar
let _tags   = {{}};
let _pinned = new Set({pinned_json});

function mergeLocalTags(posts) {{
  posts.forEach(p => {{ if (_tags[p.id]) p.tag = _tags[p.id]; }});
}}

async function loadTagsFromServer() {{
  try {{
    const r = await fetch("/tags");
    if (r.ok) {{
      const data = await r.json();
      const pinnedArr = data._pinned || [];
      _pinned = new Set(pinnedArr);
      _tags = Object.fromEntries(Object.entries(data).filter(([k]) => k !== "_pinned"));
    }}
  }} catch(_) {{}}
  mergeLocalTags(GROWTH_POSTS);
  mergeLocalTags(ALL_POSTS_VU);
  applyTagsToSelects();
  applyPinBtns();
  renderRanking();
  renderInsights();
  if (window.renderClicksChart) window.renderClicksChart(window._clicksMetric || "clicks");
}}

function shortCap(caption, len) {{
  len = len || 45;
  return (caption||"").length > len ? (caption||"").slice(0, len) + "…" : (caption||"");
}}

function getVal(p, metric) {{
  if (metric === "reach_48h")  return p.reach_48h || 0;
  if (metric === "vida_util")  return p.vida_util || 0;
  const last = p.series[p.series.length - 1] || {{}};
  return last[metric] || 0;
}}

function renderRanking() {{
  const ranked = [...GROWTH_POSTS]
    .filter(p => p.series && p.series.length > 0)
    .sort((a, b) => getVal(b, currentMetric) - getVal(a, currentMetric));

  const noData = ranked.length === 0;
  document.getElementById("noDataMsg").style.display    = noData ? "block" : "none";
  document.getElementById("rankingChart").style.display = noData ? "none"  : "block";
  if (noData) {{ if (rankingChart) {{ rankingChart.destroy(); rankingChart = null; }} return; }}

  const labels   = ranked.map(p => (_pinned.has(p.id) ? "📌 " : "") + shortCap(p.caption || p.published, 38));
  const values   = ranked.map(p => getVal(p, currentMetric));
  const bgColors = ranked.map(p => _pinned.has(p.id) ? "#44444433" : (TAG_COLORS[p.tag] || "#5c6bc0") + "bb");
  const borders  = ranked.map(p => _pinned.has(p.id) ? "#666688"   : (TAG_COLORS[p.tag] || "#5c6bc0"));
  const maxVal   = Math.max(...values, 1);

  const cfg = {{
    type: "bar",
    data: {{
      labels,
      datasets: [{{
        data: values,
        backgroundColor: bgColors,
        borderColor: borders,
        borderWidth: 1.5,
        borderRadius: 5
      }}]
    }},
    options: {{
      indexAxis: "y",
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: "#1a1a2e", borderColor: "#3a3a5c", borderWidth: 1,
          titleColor: "#fff", bodyColor: "#cccce0",
          callbacks: {{
            title: items => shortCap(ranked[items[0].dataIndex].caption, 65),
            label: item => {{
              const p = ranked[item.dataIndex];
              const last = p.series[p.series.length-1] || {{}};
              if (currentMetric === "reach_48h")
                return ` Alcance 48h: ${{item.parsed.x.toLocaleString("es-CO")}} · medido a ${{p.reach_48h_hours||"??"}}h`;
              if (currentMetric === "vida_util")
                return ` Vida útil: ${{item.parsed.x.toFixed(1)}} reach/h · ${{Math.round(last.hours||0)}}h de vida`;
              return ` ${{METRIC_LABELS[currentMetric]}}: ${{item.parsed.x.toLocaleString("es-CO")}}`;
            }},
            afterLabel: item => {{
              const p = ranked[item.dataIndex];
              const pinNote = _pinned.has(p.id) ? " 📌 Fijado — tráfico del perfil" : "";
              return ` Tipo: ${{p.tag || "sin etiquetar"}}${{pinNote}}`;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: "#8888aa" }}, grid: {{ color: "#1e1e38" }}, max: maxVal * 1.12 }},
        y: {{ ticks: {{ color: "#ddddf0", font: {{ size: 11, cursor:"pointer" }} }}, grid: {{ color: "#1e1e38" }} }}
      }},
      onClick: (evt, elements) => {{
        if (elements.length > 0) {{
          const idx = elements[0].index;
          openModal(ranked[idx].id);
        }}
      }},
      onHover: (evt, elements) => {{
        evt.native.target.style.cursor = elements.length > 0 ? "pointer" : "default";
      }}
    }}
  }};

  if (rankingChart) rankingChart.destroy();
  rankingChart = new Chart(document.getElementById("rankingChart").getContext("2d"), cfg);
}}

document.querySelectorAll("#metricBtns .btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll("#metricBtns .btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentMetric = btn.dataset.metric;
    renderRanking();
  }});
}});

renderRanking();

// ── Tags inline ──────────────────────────────────────────────
function saveTag(sel) {{
  const pid = sel.dataset.pid;
  const tag = sel.value;
  const color = TAG_COLORS[tag] || "#555577";
  sel.style.borderColor = color;
  sel.style.color = color;

  _tags[pid] = tag;

  GROWTH_POSTS.forEach(p => {{ if (p.id === pid) p.tag = tag; }});
  renderRanking();
  renderInsights();

  document.getElementById("saveTagsBtn").style.display = "inline-block";
  document.getElementById("tagsNote").style.display = "inline";
}}

function togglePin(pid) {{
  if (_pinned.has(pid)) {{
    _pinned.delete(pid);
  }} else {{
    _pinned.add(pid);
  }}
  applyPinBtns();
  renderRanking();
  renderInsights();
  document.getElementById("saveTagsBtn").style.display = "inline-block";
  document.getElementById("tagsNote").style.display = "inline";
}}

function applyPinBtns() {{
  document.querySelectorAll(".pin-btn").forEach(btn => {{
    const isPinned = _pinned.has(btn.dataset.pid);
    btn.textContent = isPinned ? "📌" : "📍";
    btn.classList.toggle("pin-active", isPinned);
    btn.title = isPinned ? "Fijado — excluido de insights" : "Marcar como fijado en el perfil";
  }});
}}

async function saveTags() {{
  const btn  = document.getElementById("saveTagsBtn");
  const note = document.getElementById("tagsNote");
  btn.textContent = "⏳ Guardando…";
  btn.disabled = true;

  try {{
    const payload = {{ ..._tags, _pinned: [..._pinned] }};
    const res = await fetch("/save-tags", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(payload)
    }});

    if (res.ok) {{
      btn.textContent = "✅ Guardado";
      note.style.display = "none";
      setTimeout(() => {{ btn.textContent = "💾 Guardar etiquetas"; btn.disabled = false; }}, 3000);
    }} else {{
      const err = await res.json().catch(() => ({{}}));
      throw new Error(err.error || res.status);
    }}
  }} catch(e) {{
    btn.textContent = "❌ Error — reintenta";
    btn.disabled = false;
    console.error("Error guardando tags:", e);
  }}
}}

function applyTagsToSelects() {{
  document.querySelectorAll(".tag-select").forEach(sel => {{
    const pid = sel.dataset.pid;
    if (_tags[pid]) {{
      sel.value = _tags[pid];
      const color = TAG_COLORS[_tags[pid]] || "#555577";
      sel.style.borderColor = color;
      sel.style.color = color;
    }}
  }});
}}

// ── Insights por tipo ────────────────────────────────────────
const ALL_POSTS_VU = {all_posts_json};

function avg(arr) {{ return arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0; }}

function renderInsightGroup(containerId, groups, unit) {{
  const container = document.getElementById(containerId);
  if (!groups.length) {{
    container.innerHTML = '<p style="color:#444466;font-size:.75rem">Sin datos suficientes aún</p>';
    return;
  }}
  const maxVal = Math.max(...groups.map(g => g.val), 0.01);
  const showReach = groups.some(g => g.reach != null);
  container.innerHTML = groups.map(g => {{
    const pct = Math.round((g.val / maxVal) * 100);
    const color = TAG_COLORS[g.label] || "#5c6bc0";
    const valStr = unit === "reach/h" ? g.val.toFixed(1) : Math.round(g.val).toLocaleString("es-CO");
    const unitStr = unit === "reach 48h" ? "reach" : unit;
    const reachStr = showReach && g.reach != null
      ? `<span style="font-size:.65rem;color:#888;margin-left:8px">· alcance prom: ${{Math.round(g.reach).toLocaleString("es-CO")}}</span>`
      : "";
    return `<div class="insight-row">
      <span class="insight-label">${{g.label}}</span>
      <div class="insight-bar-wrap"><div class="insight-bar" style="width:${{pct}}%;background:${{color}}"></div></div>
      <span class="insight-val">${{valStr}} <span style="font-size:.6rem;color:#666">${{unitStr}}</span>${{reachStr}}</span>
    </div>`;
  }}).join("") + `<p style="font-size:.65rem;color:#444466;margin-top:8px">${{groups.reduce((a,g)=>a+g.n,0)}} posts · ${{groups.map(g=>`${{g.label}}: ${{g.n}}`).join(", ")}}</p>`;
}}

function renderInsights() {{
  const posts = ALL_POSTS_VU.filter(p => p.reach_48h > 0 && !_pinned.has(p.id));

  // Por formato — alcance 48h + reach total promedio
  const byFormat = {{}};
  posts.forEach(p => {{
    const fmt = p.type === "VIDEO" ? "Video" : p.type === "CAROUSEL_ALBUM" ? "Carrusel" : "Foto";
    if (!byFormat[fmt]) byFormat[fmt] = {{ r48: [], reach: [] }};
    byFormat[fmt].r48.push(p.reach_48h);
    const lastSnap = p.series && p.series.length ? p.series[p.series.length-1] : null;
    if (lastSnap && lastSnap.reach > 0) byFormat[fmt].reach.push(lastSnap.reach);
  }});
  const formatGroups = Object.entries(byFormat)
    .map(([label, d]) => ({{ label, val: avg(d.r48), reach: avg(d.reach), n: d.r48.length }}))
    .sort((a,b) => b.val - a.val);
  renderInsightGroup("insightFormat", formatGroups, "reach 48h");

  // Por etapa del embudo
  const byTag = {{}};
  posts.forEach(p => {{
    const t = p.tag || "sin etiquetar";
    if (t === "sin etiquetar") return;
    if (!byTag[t]) byTag[t] = {{ r48: [], reach: [] }};
    byTag[t].r48.push(p.reach_48h);
    const lastSnap = p.series && p.series.length ? p.series[p.series.length-1] : null;
    if (lastSnap && lastSnap.reach > 0) byTag[t].reach.push(lastSnap.reach);
  }});
  const tagGroups = Object.entries(byTag)
    .map(([label, d]) => ({{ label, val: avg(d.r48), reach: avg(d.reach), n: d.r48.length }}))
    .sort((a,b) => b.val - a.val);
  renderInsightGroup("insightTag", tagGroups.length ? tagGroups : [], "reach 48h");

  // Por hora de publicación (Colombia = UTC-5)
  const bySlot = {{ "Mañana (<12h)": {{ r48:[], reach:[] }}, "Tarde (12-18h)": {{ r48:[], reach:[] }}, "Noche (>18h)": {{ r48:[], reach:[] }} }};
  posts.forEach(p => {{
    if (!p.published_at) return;
    const utcH = new Date(p.published_at.replace("+0000","Z")).getUTCHours();
    const colH = (utcH - 5 + 24) % 24;
    const slot = colH < 12 ? "Mañana (<12h)" : colH < 18 ? "Tarde (12-18h)" : "Noche (>18h)";
    bySlot[slot].r48.push(p.reach_48h);
    const lastSnap = p.series && p.series.length ? p.series[p.series.length-1] : null;
    if (lastSnap && lastSnap.reach > 0) bySlot[slot].reach.push(lastSnap.reach);
  }});
  const hourGroups = Object.entries(bySlot)
    .filter(([,d]) => d.r48.length > 0)
    .map(([label, d]) => ({{ label, val: avg(d.r48), reach: avg(d.reach), n: d.r48.length }}))
    .sort((a,b) => b.val - a.val);
  renderInsightGroup("insightHour", hourGroups, "reach 48h");
}}

// Las etiquetas se cargan del servidor — renderInsights y renderRanking
// se vuelven a llamar desde loadTagsFromServer() al completar
loadTagsFromServer();

// ── Follower growth ──────────────────────────────────────────
const FOLLOWER_SERIES = {follower_series_json};

(function renderFollowerChart() {{
  if (!FOLLOWER_SERIES || FOLLOWER_SERIES.length < 2) {{
    document.getElementById("followerNoData").style.display = "block";
    document.getElementById("followerChart").style.display  = "none";
    return;
  }}

  const labels   = FOLLOWER_SERIES.map(d => d.date.slice(5));  // MM-DD
  const total    = FOLLOWER_SERIES.map(d => d.delta);
  const organic  = FOLLOWER_SERIES.map(d => d.organic);
  const baseline = FOLLOWER_SERIES[0].baseline;

  // Calcular posts publicados por día para anotaciones
  const postsByDay = {{}};
  ALL_POSTS_VU.forEach(p => {{
    if (p.published) {{
      const day = p.published.slice(5);  // MM-DD
      if (!postsByDay[day]) postsByDay[day] = [];
      postsByDay[day].push(shortCap(p.caption, 35));
    }}
  }});

  // Nota resumen
  const avgOrganic = Math.round(organic.reduce((a,b)=>a+b,0) / organic.length);
  const maxOrganic = Math.max(...organic);
  const maxDay     = labels[organic.indexOf(maxOrganic)];
  document.getElementById("followerNote").textContent =
    `Baseline pauta: ~${{Math.round(baseline)}} seguidores/día · Orgánico estimado promedio: ~${{avgOrganic}}/día · Pico orgánico: +${{Math.round(maxOrganic)}} el ${{maxDay}}`;

  new Chart(document.getElementById("followerChart").getContext("2d"), {{
    type: "bar",
    data: {{
      labels,
      datasets: [
        {{
          label: "Baseline pauta",
          data: FOLLOWER_SERIES.map(() => baseline),
          type: "line",
          borderColor: "#fb8c00",
          backgroundColor: "transparent",
          borderDash: [5, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          order: 0
        }},
        {{
          label: "Orgánico estimado",
          data: organic,
          backgroundColor: "#43a04799",
          borderColor: "#43a047",
          borderWidth: 1,
          borderRadius: 3,
          order: 1
        }},
        {{
          label: "Pauta (baseline)",
          data: FOLLOWER_SERIES.map(d => Math.min(d.delta, baseline)),
          backgroundColor: "#fb8c0044",
          borderColor: "transparent",
          borderWidth: 0,
          borderRadius: 3,
          order: 2
        }}
      ]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: "index", intersect: false }},
      plugins: {{
        legend: {{ display: true, labels: {{ color: "#9090cc", font: {{ size: 11 }}, boxWidth: 14 }} }},
        tooltip: {{
          backgroundColor: "#1a1a2e", borderColor: "#3a3a5c", borderWidth: 1,
          titleColor: "#fff", bodyColor: "#cccce0",
          callbacks: {{
            afterBody: items => {{
              const day = labels[items[0].dataIndex];
              const posts = postsByDay[day];
              if (posts && posts.length) return ["", "📸 Publicado:", ...posts.map(p => "  · " + p)];
              return [];
            }},
            footer: items => {{
              const d = FOLLOWER_SERIES[items[0].dataIndex];
              return `Total del día: +${{d.delta}} seguidores`;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ stacked: true, ticks: {{ color: "#8888aa", maxRotation: 45 }}, grid: {{ color: "#1e1e38" }} }},
        y: {{
          stacked: true,
          title: {{ display: true, text: "seguidores ganados", color: "#8888aa" }},
          ticks: {{ color: "#8888aa" }},
          grid: {{ color: "#1e1e38" }}
        }}
      }}
    }}
  }});
}})();

// ── Modal de detalle por post ────────────────────────────────
let modalChart   = null;
let modalPost    = null;
let modalMetric  = "vida_util";

const ALL_POSTS  = ALL_POSTS_VU;
const POST_INDEX = {{}};
ALL_POSTS.forEach(p => POST_INDEX[p.id] = p);

function openModal(pid) {{
  modalPost   = POST_INDEX[pid] || null;
  modalMetric = "vida_util";

  document.querySelectorAll("#modalMetricBtns .btn").forEach(b => {{
    b.classList.toggle("active", b.dataset.m === "vida_util");
  }});

  document.getElementById("modalOverlay").classList.add("open");
  document.body.style.overflow = "hidden";
  renderModalChart();
}}

function closeModal() {{
  document.getElementById("modalOverlay").classList.remove("open");
  document.body.style.overflow = "";
  if (modalChart) {{ modalChart.destroy(); modalChart = null; }}
}}

function renderModalChart() {{
  if (!modalPost) return;
  const post = modalPost;

  // Cabecera
  document.getElementById("modalTitle").textContent = post.caption || post.published;
  const typeIcon = {{ IMAGE:"🖼️", VIDEO:"🎥", CAROUSEL_ALBUM:"🎞️" }}[post.type] || "📄";
  const isPinned = _pinned.has(post.id);
  const pinLabel = isPinned ? "📌 Fijado en perfil" : "📍 Marcar como fijado";
  document.getElementById("modalMeta").innerHTML =
    `${{typeIcon}} &nbsp; Publicado el ${{post.published}} &nbsp;·&nbsp; `+
    `<a href="${{post.permalink}}" target="_blank" style="color:#7986cb">Ver en Instagram ↗</a>`+
    `&nbsp;·&nbsp;<button id="modalPinBtn" class="pin-btn${{isPinned ? " pin-active" : ""}}"
       style="font-size:.75rem;opacity:1;padding:2px 8px;border:1px solid #3a3a5c;border-radius:12px;color:#ccc"
       onclick="togglePin('${{post.id}}'); renderModalChart();">${{pinLabel}}</button>`;

  // Stats actuales (último snapshot)
  const last = post.series[post.series.length - 1] || {{}};
  const vuLast = (post.vu_series && post.vu_series[post.vu_series.length-1] || {{}}).vu || 0;
  document.getElementById("modalStats").innerHTML = [
    ["Vida útil", vuLast.toFixed(1) + " r/h"],
    ["Alcance", (last.reach||0).toLocaleString("es-CO")],
    ["Likes", (last.likes||0).toLocaleString("es-CO")],
    ["Guardados", (last.saved||0).toLocaleString("es-CO")],
    ["Horas activo", Math.round(last.hours||0)],
    ["Tipo", post.tag || "sin etiquetar"]
  ].map(([l,v]) => `<div class="modal-stat"><div class="s-label">${{l}}</div><div class="s-value" style="font-size:1.1rem">${{v}}</div></div>`).join("");

  // Sin datos suficientes
  const hasSeries = post.series.length >= 2;
  const hasOne    = post.series.length === 1;
  document.getElementById("modalNoData").style.display  = (!hasSeries) ? "block" : "none";
  document.getElementById("modalChart").style.display   = hasSeries ? "block" : "none";
  if (!hasSeries) {{
    const last0 = post.series[0] || {{}};
    document.getElementById("modalNoData").innerHTML =
      hasOne
        ? `<strong style="color:#8888aa">Solo 1 medición disponible</strong> (a las ${{Math.round(last0.hours||0)}}h de vida)<br>
           Vuelve mañana para ver cómo está evolucionando. 📅`
        : `Aún no hay snapshots para este post. 📅`;
    return;
  }}

  // Obtener serie del post según métrica seleccionada
  let hours, postVals, avgVals, yLabel;

  if (modalMetric === "vida_util") {{
    const vuSeries = post.vu_series || [];
    hours    = vuSeries.map(s => s.hours||0).sort((a,b) => a-b);
    postVals = hours.map(h => {{ const s = vuSeries.find(x=>(x.hours||0)===h); return s ? s.vu : null; }});
    // Promedio de vida útil global
    const avgVuByH = {{}}, cntH = {{}};
    ALL_POSTS.forEach(p => (p.vu_series||[]).forEach(s => {{
      const h = s.hours||0;
      avgVuByH[h] = (avgVuByH[h]||0) + (s.vu||0);
      cntH[h]     = (cntH[h]||0) + 1;
    }}));
    avgVals = hours.map(h => cntH[h] ? +(avgVuByH[h]/cntH[h]).toFixed(2) : null);
    yLabel  = "reach/hora";
  }} else {{
    const avgByDay = {{}}, countByDay = {{}};
    ALL_POSTS.forEach(p => p.series.forEach(s => {{
      const h = s.hours || 0;
      avgByDay[h]   = (avgByDay[h]   || 0) + (s[modalMetric] || 0);
      countByDay[h] = (countByDay[h] || 0) + 1;
    }}));
    hours    = post.series.map(s => s.hours||0).sort((a,b) => a-b);
    postVals = hours.map(h => {{ const s = post.series.find(x=>(x.hours||0)===h); return s ? s[modalMetric]||0 : null; }});
    avgVals  = hours.map(h => countByDay[h] ? Math.round(avgByDay[h]/countByDay[h]) : null);
    yLabel   = METRIC_LABELS[modalMetric] || modalMetric;
  }}

  function fmtHours(h) {{ return h < 168 ? `${{h}}h` : `${{Math.round(h/24)}}d`; }}

  if (modalChart) modalChart.destroy();
  modalChart = new Chart(document.getElementById("modalChart").getContext("2d"), {{
    type: "bar",
    data: {{
      labels: hours.map(h => fmtHours(h)),
      datasets: [
        {{
          label: "Este post",
          data: postVals,
          backgroundColor: "rgba(92,107,192,0.75)",
          borderColor: "#5c6bc0",
          borderWidth: 1.5,
          borderRadius: 5,
          order: 2
        }},
        {{
          label: "Promedio general",
          data: avgVals,
          type: "line",
          borderColor: "#fb8c00",
          backgroundColor: "transparent",
          borderDash: [5,4],
          pointRadius: 5, pointHoverRadius: 7,
          tension: 0, borderWidth: 2,
          order: 1
        }}
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: true, labels: {{ color: "#9090cc", font: {{ size: 11 }}, boxWidth: 14 }} }},
        tooltip: {{
          backgroundColor: "#1a1a2e", borderColor: "#3a3a5c", borderWidth: 1,
          titleColor: "#fff", bodyColor: "#cccce0",
          callbacks: {{
            label: item => ` ${{item.dataset.label}}: ${{(item.parsed.y||0).toLocaleString("es-CO")}}`
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: "#8888aa" }}, grid: {{ color: "#1e1e38" }} }},
        y: {{
          title: {{ display: true, text: yLabel, color: "#8888aa" }},
          ticks: {{ color: "#8888aa" }}, grid: {{ color: "#1e1e38" }}
        }}
      }}
    }}
  }});
}}

document.querySelectorAll("#modalMetricBtns .btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll("#modalMetricBtns .btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    modalMetric = btn.dataset.m;
    if (modalChart) {{ modalChart.destroy(); modalChart = null; }}
    renderModalChart();
  }});
}});

// Cerrar con Escape
document.addEventListener("keydown", e => {{ if (e.key === "Escape") closeModal(); }});

// ── Clics al sitio web ───────────────────────────────────────
// CLICKS_SERIES: [{{date, website_clicks, profile_views}}]
// Datos acumulados desde snapshots Railway (desde jul 16+)
const CLICKS_SERIES = {clicks_series_json};

(function initClicksChart() {{
  const hasData   = CLICKS_SERIES && CLICKS_SERIES.length > 0;
  const hasClicks = hasData && CLICKS_SERIES.some(d => d.website_clicks > 0);
  const hasViews  = hasData && CLICKS_SERIES.some(d => d.profile_views  > 0);

  if (!hasData) {{
    document.getElementById("clicksNoData").style.display = "block";
    document.getElementById("clicksChart").style.display  = "none";
    document.getElementById("clicksMetricClicks").style.display = "none";
    document.getElementById("clicksMetricViews").style.display  = "none";
    document.getElementById("clicksMetricBoth").style.display   = "none";
    return;
  }}
  if (!hasClicks) document.getElementById("clicksMetricClicks").style.display = "none";
  if (!hasViews)  document.getElementById("clicksMetricViews").style.display  = "none";
  if (!hasClicks || !hasViews) document.getElementById("clicksMetricBoth").style.display = "none";

  window._clicksChart  = null;
  window._clicksMetric = hasClicks ? "clicks" : "views";

  window.renderClicksChart = function(metric) {{
    window._clicksMetric = metric;

    // Posts publicados por día — con tags actualizados al momento del render
    const postsByDay = {{}};
    ALL_POSTS_VU.forEach(p => {{
      if (!p.published) return;
      if (!postsByDay[p.published]) postsByDay[p.published] = [];
      const tag  = (_tags[p.id] || p.tag || "sin etiquetar");
      const icon = tag === "atracción" ? "🔴" : tag === "conexión" ? "🟢" : tag === "conversión" ? "🔵" : "⚪";
      postsByDay[p.published].push(`${{icon}} ${{shortCap(p.caption, 40)}}`);
    }});

    const labels = CLICKS_SERIES.map(d => d.date);
    let datasets, noteText;

    if (metric === "clicks") {{
      const vals  = CLICKS_SERIES.map(d => d.website_clicks);
      const total = vals.reduce((a,b) => a+b, 0);
      datasets = [{{
        label: "Clics al sitio",
        data: vals,
        backgroundColor: "#fb8c0099",
        borderColor: "#fb8c00",
        borderWidth: 1.5,
        borderRadius: 4
      }}];
      noteText = `Total: ${{total.toLocaleString("es-CO")}} clics · promedio: ${{Math.round(total/vals.length)}}/día`;
    }} else if (metric === "views") {{
      const vals  = CLICKS_SERIES.map(d => d.profile_views);
      const total = vals.reduce((a,b) => a+b, 0);
      datasets = [{{
        label: "Visitas de perfil",
        data: vals,
        backgroundColor: "#8e24aa99",
        borderColor: "#8e24aa",
        borderWidth: 1.5,
        borderRadius: 4
      }}];
      noteText = `Total: ${{total.toLocaleString("es-CO")}} visitas de perfil · promedio: ${{Math.round(total/vals.length)}}/día`;
    }} else {{
      datasets = [
        {{
          label: "Clics al sitio",
          data: CLICKS_SERIES.map(d => d.website_clicks),
          backgroundColor: "#fb8c0099",
          borderColor: "#fb8c00",
          borderWidth: 1.5, borderRadius: 4, yAxisID: "y"
        }},
        {{
          label: "Visitas de perfil",
          data: CLICKS_SERIES.map(d => d.profile_views),
          type: "line",
          borderColor: "#8e24aa",
          backgroundColor: "transparent",
          borderWidth: 2, pointRadius: 3, tension: 0.3, yAxisID: "y2"
        }}
      ];
      noteText = "Barras: clics al sitio (eje izq) · Línea: visitas de perfil (eje der)";
    }}

    document.getElementById("clicksNote").textContent = noteText;

    const scales = {{
      x: {{ ticks: {{ color: "#8888aa", maxTicksLimit: 20, maxRotation: 45 }}, grid: {{ color: "#1e1e38" }} }},
      y: {{ ticks: {{ color: "#8888aa" }}, grid: {{ color: "#1e1e38" }} }}
    }};
    if (metric === "both") {{
      scales.y2 = {{ position: "right", ticks: {{ color: "#8e24aa" }}, grid: {{ drawOnChartArea: false }} }};
    }}

    if (window._clicksChart) window._clicksChart.destroy();
    window._clicksChart = new Chart(document.getElementById("clicksChart").getContext("2d"), {{
      type: "bar",
      data: {{ labels, datasets }},
      options: {{
        responsive: true,
        interaction: {{ mode: "index", intersect: false }},
        plugins: {{
          legend: {{ display: metric === "both", labels: {{ color: "#9090cc", font: {{ size: 11 }}, boxWidth: 14 }} }},
          tooltip: {{
            backgroundColor: "#1a1a2e", borderColor: "#3a3a5c", borderWidth: 1,
            titleColor: "#fff", bodyColor: "#cccce0",
            callbacks: {{
              afterBody: items => {{
                const day = labels[items[0].dataIndex];
                const posts = postsByDay[day];
                if (posts && posts.length) return ["", "📸 Publicado ese día:", ...posts.map(p => "  " + p)];
                return [];
              }}
            }}
          }}
        }},
        scales
      }}
    }});
  }};

  window.renderClicksChart(window._clicksMetric);
}})();

window.switchClicksMetric = function(metric) {{
  document.querySelectorAll("#clicksCard .btn").forEach(b => b.classList.remove("active"));
  const idMap = {{ clicks: "clicksMetricClicks", views: "clicksMetricViews", both: "clicksMetricBoth" }};
  const el = document.getElementById(idMap[metric]);
  if (el) el.classList.add("active");
  window.renderClicksChart(metric);
}};

{lab_js}
</script>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────

def fetch_snapshots_from_github():
    """Lee post_snapshots.json desde GitHub si no hay archivo local."""
    import base64, urllib.error
    gh_token = cfg.get("GH_TOKEN", os.environ.get("GH_TOKEN", ""))
    gh_repo  = cfg.get("GH_REPO",  os.environ.get("GH_REPO", ""))
    if not gh_token or not gh_repo:
        return None
    url = f"https://api.github.com/repos/{gh_repo}/contents/data/post_snapshots.json"
    headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        return json.loads(base64.b64decode(d["content"]))
    except Exception as e:
        print(f"  ⚠️  No se pudo leer de GitHub: {e}")
        return None

def main():
    print("⏳ Obteniendo datos de Instagram...")

    print("  → Perfil...")
    perfil = get_perfil()

    print("  → Insights 7/14/28 días...")
    insights = get_all_insights()

    print("  → Posts recientes...")
    posts = get_posts(30)

    print("  → Demografía...")
    demo = get_demografia()

    print("  → Guardando snapshot diario...")
    OUT.parent.mkdir(exist_ok=True)

    # Siempre sincronizar con GitHub para tener todos los snapshots
    print("  → Sincronizando snapshots desde GitHub...")
    remote = fetch_snapshots_from_github()
    if remote:
        local = json.loads(SNAPSHOTS.read_text()) if SNAPSHOTS.exists() else {}
        merged = {**remote, **local}   # local gana si hay conflicto (más reciente)
        SNAPSHOTS.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
        n = len([k for k in merged if not k.startswith("_")])
        print(f"  ✅ {n} snapshots (GitHub + local)")

    history = save_snapshot(posts, followers=perfil.get("followers_count", 0))

    print("  → Generando HTML...")
    html = build_html(perfil, insights, posts, demo, history)
    OUT.write_text(html, encoding="utf-8")

    snapshots_count = len(history)
    print(f"\n✅ Dashboard generado: {OUT}")
    print(f"   Seguidores: {perfil.get('followers_count'):,}")
    ins28 = insights.get(28, insights) if isinstance(insights, dict) and 28 in insights else insights
    print(f"   Alcance 28d: {ins28.get('reach', 0):,}")
    print(f"   Posts procesados: {len(posts)}")
    print(f"   Snapshots acumulados: {snapshots_count}")

    import subprocess
    subprocess.Popen(["open", str(OUT)])

if __name__ == "__main__":
    main()

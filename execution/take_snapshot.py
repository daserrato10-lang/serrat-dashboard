#!/usr/bin/env python3
"""
Serrat Relojes — Snapshot automático diario
Corre en Railway (cron). Lee/escribe post_snapshots.json via GitHub API.
Genera dashboard HTML y lo sube a docs/index.html (GitHub Pages).
Notifica por Telegram al finalizar.
"""

import os, json, time, base64, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

# Importar build_html desde generate_dashboard
sys.path.insert(0, str(Path(__file__).parent))
import generate_dashboard as gd

# ── Config desde env vars ─────────────────────────────────────
def env(key):
    val = os.environ.get(key, "")
    # Fallback a .env local si existe
    if not val:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    if k.strip() == key:
                        return v.strip()
    return val

TOKEN        = env("IG_TOKEN")
IG_ID        = env("IG_ID")
TG_BOT_TOKEN = env("TG_BOT_TOKEN")
TG_CHAT_ID   = env("TG_CHAT_ID")
GH_TOKEN     = env("GH_TOKEN")
GH_REPO      = env("GH_REPO")          # formato: "usuario/repo"
GH_SNAPSHOTS = env("GH_SNAPSHOTS_PATH") or "data/post_snapshots.json"
GH_DASHBOARD = "docs/index.html"

BASE_IG = "https://graph.facebook.com/v21.0"
BASE_GH = "https://api.github.com"

# ── Utilidades HTTP ───────────────────────────────────────────

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def http_put(url, data, headers=None):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(url, data=body, method="PUT",
                                  headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

# ── Instagram API ─────────────────────────────────────────────

def ig_get(path, params=None):
    params = params or {}
    params["access_token"] = TOKEN
    url = f"{BASE_IG}/{path}?{urllib.parse.urlencode(params)}"
    data = http_get(url)
    if "error" in data:
        raise RuntimeError(data["error"]["message"])
    return data

def fetch_post_metrics(post):
    """Agrega métricas de reach/saved/shares a un dict de post."""
    try:
        ins = ig_get(f"{post['id']}/insights", {"metric": "reach,saved,shares"})
        for m in ins.get("data", []):
            post[f"metric_{m['name']}"] = (m.get("values") or [{}])[0].get("value", 0)
    except Exception:
        post["metric_reach"] = post.get("metric_reach", 0)
        post["metric_saved"] = post.get("metric_saved", 0)
        post["metric_shares"] = post.get("metric_shares", 0)
    time.sleep(0.15)
    return post

def fetch_single_post(post_id):
    """Obtiene datos básicos de un post por ID."""
    try:
        return ig_get(post_id, {
            "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink"
        })
    except Exception:
        return None

def get_posts(limit=30, history=None):
    """Obtiene los últimos `limit` posts + cualquier post histórico que ya esté en tracking."""
    media = ig_get(f"{IG_ID}/media", {
        "fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink",
        "limit": limit
    })
    posts = media.get("data", [])
    recent_ids = {p["id"] for p in posts}

    # Posts históricos (últimos 90 días) que ya no están en los últimos 30
    if history:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date()
        all_tracked = set()
        for day_str, day_data in history.items():
            try:
                if datetime.strptime(day_str, "%Y-%m-%d").date() >= cutoff:
                    all_tracked.update(pid for pid in day_data if pid != "_meta")
            except ValueError:
                pass
        extra_ids = all_tracked - recent_ids
        for pid in extra_ids:
            p = fetch_single_post(pid)
            if p:
                posts.append(p)

    for post in posts:
        fetch_post_metrics(post)

    return posts

# ── GitHub API — leer y escribir post_snapshots.json ─────────

def gh_headers():
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh_read_snapshots():
    """Lee post_snapshots.json del repo. Devuelve (content_dict, sha)."""
    url = f"{BASE_GH}/repos/{GH_REPO}/contents/{GH_SNAPSHOTS}"
    try:
        res  = http_get(url, gh_headers())
        raw  = base64.b64decode(res["content"]).decode("utf-8")
        return json.loads(raw), res["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}, None   # archivo no existe aún
        raise

def gh_write_snapshots(history, sha, message):
    """Escribe post_snapshots.json en el repo via GitHub API."""
    url     = f"{BASE_GH}/repos/{GH_REPO}/contents/{GH_SNAPSHOTS}"
    content = base64.b64encode(
        json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    payload = {"message": message, "content": content}
    if sha:
        payload["sha"] = sha
    http_put(url, payload, gh_headers())

def gh_get_sha(path):
    """Obtiene el SHA actual de un archivo en el repo (None si no existe)."""
    url = f"{BASE_GH}/repos/{GH_REPO}/contents/{path}"
    try:
        res = http_get(url, gh_headers())
        return res.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def gh_write_file(path, content_str, sha, message):
    """Escribe cualquier archivo al repo via GitHub API."""
    url     = f"{BASE_GH}/repos/{GH_REPO}/contents/{path}"
    content = base64.b64encode(content_str.encode("utf-8")).decode("ascii")
    payload = {"message": message, "content": content}
    if sha:
        payload["sha"] = sha
    http_put(url, payload, gh_headers())

# ── Snapshot ──────────────────────────────────────────────────

def parse_ig_timestamp(ts):
    if not ts:
        return None
    ts = ts.replace("+0000", "+00:00")
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None

def take_snapshot(posts, history):
    colombia       = timezone(timedelta(hours=-5))
    now_col        = datetime.now(colombia)
    today          = now_col.strftime("%Y-%m-%d")
    snapshot_taken = datetime.now(timezone.utc).isoformat()

    if today in history:
        return history, today, False  # ya existe

    history[today] = {"_meta": {"taken_at": snapshot_taken}}
    for post in posts:
        pid = post["id"]
        history[today][pid] = {
            "published":    post.get("timestamp", "")[:10],
            "published_at": post.get("timestamp", ""),
            "caption":      (post.get("caption") or "")[:120].replace("\n", " "),
            "type":         post.get("media_type", ""),
            "permalink":    post.get("permalink", ""),
            "likes":        post.get("like_count", 0),
            "comments":     post.get("comments_count", 0),
            "reach":        post.get("metric_reach", 0),
            "saved":        post.get("metric_saved", 0),
            "shares":       post.get("metric_shares", 0),
        }
    return history, today, True

# ── Telegram ──────────────────────────────────────────────────

def tg_send(text):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("⚠️  Telegram no configurado — omitiendo notificación")
        return
    url  = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠️  Error Telegram: {e}")

# ── Main ──────────────────────────────────────────────────────

def main():
    colombia = timezone(timedelta(hours=-5))
    now_str  = datetime.now(colombia).strftime("%d/%m/%Y %I:%M %p")

    print(f"⏳ Iniciando snapshot — {now_str} Colombia")

    try:
        print("  → Leyendo snapshots desde GitHub...")
        history, sha = gh_read_snapshots()
        num_prev = len([k for k in history if not k.startswith("_")])

        print("  → Obteniendo posts de Instagram...")
        posts = get_posts(30, history)

        print("  → Guardando snapshot...")
        history, today, saved = take_snapshot(posts, history)

        if not saved:
            msg = (f"ℹ️ <b>Serrat Dashboard</b>\n"
                   f"Ya existía snapshot de {today}. No se guardó duplicado.")
            print(f"  ℹ️  Snapshot de {today} ya existía.")
            tg_send(msg)
            return

        print("  → Escribiendo snapshot en GitHub...")
        num_new = len([k for k in history if not k.startswith("_")])
        commit_msg = f"snapshot: {today} ({len(posts)} posts)"
        gh_write_snapshots(history, sha, commit_msg)

        print("  → Obteniendo datos adicionales para el dashboard...")
        perfil   = gd.get_perfil()
        insights = gd.get_all_insights()
        demo     = gd.get_demografia()

        print("  → Generando dashboard HTML...")
        html = gd.build_html(perfil, insights, posts, demo, history)

        print("  → Subiendo dashboard a GitHub Pages...")
        dash_sha = gh_get_sha(GH_DASHBOARD)
        gh_write_file(GH_DASHBOARD, html, dash_sha, f"dashboard: {today}")

        # Resumen para Telegram
        snap     = history[today]
        snap_meta = snap.get("_meta", {})
        taken_utc = snap_meta.get("taken_at", "")
        taken_col = ""
        if taken_utc:
            dt = datetime.fromisoformat(taken_utc).astimezone(colombia)
            taken_col = dt.strftime("%I:%M %p")

        # Top 3 por reach
        post_list = [(pid, d) for pid, d in snap.items() if pid != "_meta"]
        top3 = sorted(post_list, key=lambda x: x[1].get("reach", 0), reverse=True)[:3]
        top3_txt = "\n".join(
            f"  {i+1}. {d['caption'][:40]}… → {d['reach']:,} reach"
            for i, (_, d) in enumerate(top3)
        )

        msg = (
            f"✅ <b>Serrat Dashboard — Snapshot diario</b>\n"
            f"📅 {today}  🕐 {taken_col} Colombia\n"
            f"📸 {num_new} snapshots acumulados · {len(posts)} posts medidos\n\n"
            f"<b>Top 3 por reach hoy:</b>\n{top3_txt}\n\n"
            f"🔗 https://daserrato10-lang.github.io/serrat-dashboard/"
        )
        tg_send(msg)
        print(f"  ✅ Snapshot guardado: {today} — {len(posts)} posts")
        print(f"  📱 Notificación enviada a Telegram")

    except Exception as e:
        error_msg = (
            f"❌ <b>Serrat Dashboard — Error en snapshot</b>\n"
            f"📅 {now_str} Colombia\n\n"
            f"<code>{str(e)[:300]}</code>"
        )
        tg_send(error_msg)
        print(f"  ❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()

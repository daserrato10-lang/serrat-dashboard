#!/usr/bin/env python3
"""
Serrat Dashboard — Servidor web Railway
Sirve el dashboard y maneja guardado de etiquetas server-side.
"""

import os, json, base64, time
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

GH_TOKEN     = os.environ.get("GH_TOKEN", "")
GH_REPO      = os.environ.get("GH_REPO", "")
GH_TAGS_PATH = "post_tags.json"
GH_EXP_PATH  = "experiments.json"
GH_DASH_PATH = "docs/index.html"
BASE_GH      = "https://api.github.com"
PORT         = int(os.environ.get("PORT", 8080))

_cache = {"html": None, "ts": 0}
CACHE_TTL = 300  # 5 minutos

def gh_headers():
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def gh_read(path):
    url = f"{BASE_GH}/repos/{GH_REPO}/contents/{path}"
    req = urllib.request.Request(url, headers=gh_headers())
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]

def gh_write(path, content_str, sha, message):
    url = f"{BASE_GH}/repos/{GH_REPO}/contents/{path}"
    content = base64.b64encode(content_str.encode()).decode("ascii")
    payload = {"message": message, "content": content}
    if sha:
        payload["sha"] = sha
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="PUT",
                                 headers={"Content-Type": "application/json", **gh_headers()})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def get_dashboard_html():
    now = time.time()
    if _cache["html"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["html"]
    try:
        html, _ = gh_read(GH_DASH_PATH)
        _cache["html"] = html
        _cache["ts"] = now
        return html
    except Exception as e:
        if _cache["html"]:
            return _cache["html"]
        raise e


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} — {fmt % args}")

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            try:
                html = get_dashboard_html()
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode())
        elif self.path == "/tags":
            try:
                raw, _ = gh_read(GH_TAGS_PATH)
                tags = json.loads(raw)
            except Exception:
                tags = {}
            self.send_json(200, tags)
        elif self.path == "/experiments":
            try:
                raw, _ = gh_read(GH_EXP_PATH)
                exps = json.loads(raw)
            except Exception:
                exps = {}
            self.send_json(200, exps)
        elif self.path == "/health":
            self.send_json(200, {"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/save-experiment":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                payload  = json.loads(body)
                exp_id   = payload.get("id")
                exp_data = payload.get("data")
                if not exp_id or exp_data is None:
                    raise ValueError("Se requieren 'id' y 'data'")
                try:
                    existing_raw, sha = gh_read(GH_EXP_PATH)
                    experiments = json.loads(existing_raw)
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        experiments, sha = {}, None
                    else:
                        raise
                experiments[exp_id] = exp_data
                content = json.dumps(experiments, ensure_ascii=False, indent=2)
                gh_write(GH_EXP_PATH, content, sha, f"lab: update {exp_id}")
                self.send_json(200, {"ok": True})
            except Exception as e:
                self.send_json(500, {"error": str(e)})
        elif self.path == "/save-tags":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                tags = json.loads(body)
                if not isinstance(tags, dict):
                    raise ValueError("body debe ser un objeto JSON")

                try:
                    existing_raw, sha = gh_read(GH_TAGS_PATH)
                    existing = json.loads(existing_raw)
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        existing, sha = {}, None
                    else:
                        raise

                # Fusionar: existentes + nuevas (nuevas ganan en conflicto)
                # _pinned es lista — unir ambas
                existing_pinned = set(existing.pop("_pinned", []))
                new_pinned      = set(tags.pop("_pinned", []))
                # _insights es dict de dicts — deep merge a nivel de post_id
                existing_insights = existing.pop("_insights", {})
                new_insights      = tags.pop("_insights", {})
                merged = {**existing, **tags}
                merged["_pinned"]   = list(existing_pinned | new_pinned)
                merged["_insights"] = {**existing_insights, **new_insights}
                content = json.dumps(merged, ensure_ascii=False, indent=2)
                gh_write(GH_TAGS_PATH, content, sha, "tags: actualizar desde dashboard")
                _cache["ts"] = 0  # Invalidar caché para que el próximo GET regenere
                self.send_json(200, {"ok": True})
            except Exception as e:
                self.send_json(500, {"error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"🚀 Serrat Dashboard server — puerto {PORT}")
    server.serve_forever()

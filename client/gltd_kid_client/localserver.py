"""Servidor HTTP local do client (127.0.0.1:8877).

Serve para a extensão do Brave:
  - GET /lists     -> cache das listas de bloqueio (JSON, com CORS)
  - GET /blocked   -> página de bloqueio
  - POST /report   -> registra tentativa de acesso bloqueado
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LISTS_CACHE = "/run/gltd-kid-control/lists_cache.json"
ADMIN_HASH_FILE = "/run/gltd-kid-control/admin_hash"
PAUSED_FILE = "/run/gltd-kid-control/paused.json"

BLOCK_PAGE = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Conteúdo bloqueado</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0f1419;color:#e6edf3;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}}
.card{{text-align:center;background:#1b222b;border:1px solid #2a3440;border-radius:12px;padding:40px;max-width:420px}}
h1{{font-size:22px;margin:0 0 8px}}.icon{{font-size:48px}}.muted{{color:#9fb3c8;font-size:14px}}
</style></head><body><div class="card">
<div class="icon">&#128274;</div><h1>Conteúdo bloqueado</h1>
<p>Este site foi bloqueado pelo controle parental.</p>
<p class="muted" id="u"></p>
</div><script>var q=new URLSearchParams(location.search).get('url');if(q)document.getElementById('u').textContent=q;</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.startswith("/lists"):
            try:
                body = Path(LISTS_CACHE).read_bytes()
            except OSError:
                body = b"{}"
            # injeta estado de pausa no JSON do cache
            try:
                import json as _json
                data = _json.loads(body.decode("utf-8"))
                data["paused"] = self._paused()
                body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
            except Exception:  # noqa: BLE001
                pass
            self._send(body, "application/json; charset=utf-8")
        elif self.path.startswith("/blocked"):
            self._send(BLOCK_PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/health":
            self._send(b'{"ok":true}', "application/json")
        elif self.path == "/status":
            import json as _json
            self._send(_json.dumps({"paused": self._paused()}).encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def _paused(self) -> bool:
        import json as _json
        import time
        try:
            data = _json.loads(Path(PAUSED_FILE).read_text(encoding="utf-8"))
            return bool(data.get("paused")) and time.time() < float(data.get("until", 0))
        except Exception:  # noqa: BLE001
            return False

    def do_POST(self) -> None:
        import json as _json
        import time
        length = int(self.headers.get("Content-Length", 0) or 0)
        data = {}
        if length:
            try:
                data = _json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:  # noqa: BLE001
                data = {}
        if self.path.startswith("/pause"):
            from .auth import verify_password
            try:
                stored = Path(ADMIN_HASH_FILE).read_text(encoding="utf-8").strip()
            except OSError:
                stored = ""
            if not stored:
                self._send(b'{"ok":false,"error":"senha indisponivel no client"}', "application/json")
                return
            if verify_password(data.get("password", ""), stored):
                minutes = min(max(int(data.get("minutes", 30)), 1), 240)
                until = time.time() + minutes * 60
                Path(PAUSED_FILE).write_text(
                    _json.dumps({"paused": True, "until": until, "minutes": minutes}),
                    encoding="utf-8")
                self._send(b'{"ok":true}', "application/json")
            else:
                self._send(b'{"ok":false,"error":"senha incorreta"}', "application/json")
        elif self.path.startswith("/resume"):
            try:
                Path(PAUSED_FILE).unlink()
            except OSError:
                pass
            self._send(b'{"ok":true}', "application/json")
        elif self.path.startswith("/report"):
            try:
                with open("/run/gltd-kid-control/blocked_attempts.jsonl", "a", encoding="utf-8") as fh:
                    fh.write(_json.dumps(data, ensure_ascii=False) + "\n")
            except Exception:  # noqa: BLE001
                pass
            self._send(b'{"ok":true}', "application/json")
        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

    def log_message(self, fmt, *args):  # noqa: D102
        pass


def run_local_server(port: int = 8877) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

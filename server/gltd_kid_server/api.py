"""API HTTP (JSON) do server — http.server stdlib + autenticação por sessão."""
from __future__ import annotations

import json
import re
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .auth import SessionManager, hash_password, verify_password
from .config import ServerConfig, save_config
from .db import create_store
from .lists import load_all, load_csv, parse_csv_text
from .models import HistoryEntry, Profile

SESSION_COOKIE = "kid_sid"
PAGES = {
    "/": "dashboard.html",
    "/index.html": "dashboard.html",
    "/login": "login.html",
    "/setup": "setup.html",
    "/dashboard": "dashboard.html",
    "/profile": "profile.html",
    "/settings": "settings.html",
    "/style.css": "style.css",
}


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "perfil"


def normalize_channel(value: str) -> tuple[str, str]:
    """Normaliza um handle/URL de canal para (handle, url)."""
    v = value.strip()
    if not v:
        return "", ""
    if v.startswith("http"):
        parsed = urllib.parse.urlparse(v)
        seg = ""
        for part in parsed.path.rstrip("/").split("/"):
            if part.startswith("@"):
                seg = part
                break
        if not seg:
            seg = parsed.path.rstrip("/").split("/")[-1]
        handle = seg if seg.startswith("@") else "@" + seg
        return handle, "https://www.youtube.com/" + handle
    if not v.startswith("@"):
        v = "@" + v
    return v, "https://www.youtube.com/" + v


def _sanitize_csv(v: str) -> str:
    return v.replace(",", " ").replace("\n", " ").replace("\r", " ").strip()


class KidControlAPI(BaseHTTPRequestHandler):
    server: "KidControlServer"

    # ---------- helpers ----------

    def _json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _json_with_session(self, user: str, data, status: int = 200) -> None:
        token = self.server.sessions.create(user)
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cookie(self) -> str | None:
        for part in self.headers.get("Cookie", "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == SESSION_COOKIE:
                    return v
        return None

    def _current_user(self) -> str | None:
        return self.server.sessions.validate(self._cookie())

    def _require_auth(self) -> str | None:
        user = self._current_user()
        if not user:
            self._json({"error": "não autenticado"}, 401)
        return user

    def _serve_page(self, name: str) -> None:
        page = self.server.web_dir / name
        if not page.exists():
            self._json({"error": "página não encontrada"}, 404)
            return
        body = page.read_bytes()
        ctype = "text/css" if name.endswith(".css") else "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # noqa: D102
        pass

    # ---------- rotas ----------

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        app = self.server

        if path in PAGES:
            self._serve_page(PAGES[path])
        elif path == "/api/health":
            self._json({"status": "ok", "version": app.version})
        elif path == "/api/setup/status":
            self._json({"setup_done": app.cfg.setup_done})
        elif path == "/api/me":
            user = self._require_auth()
            if user:
                self._json({"username": user})
        elif path == "/api/profiles":
            if self._require_auth():
                self._json([p.to_dict() for p in app.profiles])
        elif path.startswith("/api/profiles/"):
            if self._require_auth():
                self._handle_profile_get(path, qs)
        elif path == "/api/lists":
            if self._require_auth():
                self._json(app.lists_summary())
        elif path == "/api/lists/files":
            if self._require_auth():
                self._json(app.lists_files())
        elif path.startswith("/api/lists/file/"):
            if self._require_auth():
                self._handle_list_file_get(path)
        elif path == "/api/history":
            if self._require_auth():
                pid = (qs.get("profile") or [None])[0]
                limit = int((qs.get("limit") or ["200"])[0])
                self._json(app.store.list_history(pid, limit))
        elif path == "/api/settings":
            if self._require_auth():
                self._json(app.store.get_settings())
        elif path == "/api/client/lists":
            self._handle_client_lists(qs)
        else:
            self._json({"error": "rota não encontrada"}, 404)

    def _handle_profile_get(self, path: str, qs: dict) -> None:
        app = self.server
        parts = path.split("/")
        pid = parts[3]
        profile = app.get_profile(pid)
        if len(parts) >= 5 and parts[4] == "summary":
            if profile is None:
                self._json({"error": "perfil não encontrado"}, 404)
                return
            self._json(app.profile_summary(pid))
        elif len(parts) >= 5 and parts[4] == "usage":
            self._json({"totals": app.store.app_usage_totals(pid),
                        "entries": app.store.app_usage_list(pid)})
        elif len(parts) >= 5 and parts[4] == "urls":
            items = app.store.url_list(pid)
            profile = app.get_profile(pid)
            for u in items:
                u["blocked"] = app.is_url_blocked(profile, u.get("url", "")) if profile else False
            self._json(items)
        elif len(parts) >= 5 and parts[4] == "youtube":
            self._json(app.store.list_history(pid))
        elif len(parts) >= 5 and parts[4] == "blocks":
            if profile is None:
                self._json({"error": "perfil não encontrado"}, 404)
                return
            self._json(app.profile_blocks(pid))
        elif profile is None:
            self._json({"error": "perfil não encontrado"}, 404)
        else:
            self._json(profile.to_dict())

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        app = self.server
        data = self._read_json()

        if path == "/api/setup":
            self._handle_setup(data)
        elif path == "/api/login":
            self._handle_login(data)
        elif path == "/api/admin/password":
            if self._require_auth():
                self._handle_change_password(data)
        elif path == "/api/logout":
            self.server.sessions.revoke(self._cookie())
            self._json({"ok": True})
        elif path == "/api/profiles":
            if self._require_auth():
                self._handle_profile_create(data)
        elif path.startswith("/api/profiles/") and path.endswith("/unblock"):
            if self._require_auth():
                self._handle_unblock(path.split("/")[3], data)
        elif path.startswith("/api/profiles/") and "/block-" in path:
            if self._require_auth():
                parts = path.split("/")
                self._handle_block(parts[3], parts[4].replace("block-", ""), data)
        elif path == "/api/lists/upload":
            if self._require_auth():
                self._handle_list_upload(data)
        elif path == "/api/history":
            if self._require_auth():
                entry = HistoryEntry(
                    profile_id=data.get("profile_id", ""),
                    channel_handle=data.get("channel_handle", ""),
                    channel_name=data.get("channel_name", ""),
                    video_title=data.get("video_title", ""),
                    video_url=data.get("video_url", ""),
                    thumb_url=data.get("thumb_url", ""),
                    description=data.get("description", ""),
                    watched_at=data.get("watched_at", ""),
                )
                self._json({"id": app.store.add_history(entry.to_dict())}, 201)
        elif path == "/api/usage":
            if self._require_auth():
                app.store.add_app_usage(
                    data.get("profile_id", ""), data.get("app_name", ""),
                    int(data.get("duration_seconds", 0)), data.get("started_at", ""),
                )
                self._json({"ok": True}, 201)
        elif path == "/api/urls":
            if self._require_auth():
                app.store.add_url(
                    data.get("profile_id", ""), data.get("url", ""),
                    data.get("title", ""), data.get("visited_at", ""),
                )
                self._json({"ok": True}, 201)
        elif path == "/api/filters":
            if self._require_auth():
                pid = data.get("profile_id", "")
                expr = data.get("expression", "")
                result = app.add_filter(pid, expr)
                self._json(result, 200 if result.get("ok") else 400)
        elif path == "/api/client/report":
            self._handle_client_report(data)
        elif path == "/api/client/heartbeat":
            self._handle_client_heartbeat(data)
        else:
            self._json({"error": "rota não encontrada"}, 404)

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        app = self.server
        data = self._read_json()
        if path == "/api/settings":
            if self._require_auth():
                app.store.set_settings(data)
                self._json({"ok": True, "settings": app.store.get_settings()})
        elif path.startswith("/api/profiles/"):
            if self._require_auth():
                self._handle_profile_update(path.rsplit("/", 1)[-1], data)
        elif path.startswith("/api/lists/file/"):
            if self._require_auth():
                self._handle_list_file_put(path, data)
        else:
            self._json({"error": "rota não encontrada"}, 404)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        app = self.server
        if path.startswith("/api/profiles/"):
            if self._require_auth():
                pid = path.rsplit("/", 1)[-1]
                if app.delete_profile(pid):
                    self._json({"ok": True})
                else:
                    self._json({"error": "perfil não encontrado"}, 404)
        else:
            self._json({"error": "rota não encontrada"}, 404)

    # ---------- handlers ----------

    def _handle_setup(self, data: dict) -> None:
        app = self.server
        if app.cfg.setup_done:
            self._json({"error": "já configurado"}, 400)
            return
        user = (data.get("admin_user") or "").strip()
        password = data.get("admin_password") or ""
        if not user or len(password) < 4:
            self._json({"error": "informe usuário e senha (mín. 4 caracteres)"}, 400)
            return
        app.cfg.admin_user = user
        app.cfg.admin_password_hash = hash_password(password)
        app.cfg.setup_done = True
        if data.get("listen_port"):
            app.cfg.listen_port = int(data["listen_port"])
        app.save()
        self._json_with_session(user, {"ok": True, "setup_done": True})

    def _handle_login(self, data: dict) -> None:
        app = self.server
        user = (data.get("admin_user") or "").strip()
        password = data.get("admin_password") or ""
        if user == app.cfg.admin_user and verify_password(password, app.cfg.admin_password_hash):
            self._json_with_session(user, {"ok": True, "username": user})
        else:
            self._json({"error": "usuário ou senha incorretos"}, 401)

    def _handle_change_password(self, data: dict) -> None:
        app = self.server
        current = data.get("current_password") or ""
        new = data.get("new_password") or ""
        if not verify_password(current, app.cfg.admin_password_hash):
            self._json({"error": "senha atual incorreta"}, 401)
            return
        if len(new) < 4:
            self._json({"error": "nova senha muito curta (mín. 4 caracteres)"}, 400)
            return
        app.cfg.admin_password_hash = hash_password(new)
        app.save()
        self._json({"ok": True})

    def _handle_profile_create(self, data: dict) -> None:
        app = self.server
        name = (data.get("name") or "").strip()
        if not name:
            self._json({"error": "informe o nome da criança"}, 400)
            return
        profile = Profile(
            id=data.get("id") or slugify(name),
            name=name,
            lan_ip=data.get("lan_ip", ""),
            linux_user=data.get("linux_user", ""),
            allowed_browsers=data.get("allowed_browsers") or ["brave-browser"],
            block_lists=data.get("block_lists") or [],
            allow_lists=data.get("allow_lists") or [],
            filters=data.get("filters") or [],
            client_token=data.get("client_token") or secrets.token_hex(24),
            daily_limit_minutes=int(data.get("daily_limit_minutes") or 0),
            youtube_limit_minutes=int(data.get("youtube_limit_minutes") or 0),
        )
        if app.get_profile(profile.id):
            self._json({"error": "já existe um perfil com esse id"}, 400)
            return
        app.profiles.append(profile)
        app.store.upsert_profile(profile.to_dict())
        self._json(profile.to_dict(), 201)

    def _handle_profile_update(self, pid: str, data: dict) -> None:
        app = self.server
        profile = app.get_profile(pid)
        if profile is None:
            self._json({"error": "perfil não encontrado"}, 404)
            return
        for key in ("name", "lan_ip", "linux_user"):
            if key in data:
                setattr(profile, key, data[key])
        for key in ("allowed_browsers", "block_lists", "allow_lists", "filters"):
            if key in data:
                setattr(profile, key, data[key])
        for key in ("daily_limit_minutes", "youtube_limit_minutes"):
            if key in data:
                try:
                    setattr(profile, key, int(data[key] or 0))
                except (TypeError, ValueError):
                    pass
        app.store.upsert_profile(profile.to_dict())
        self._json(profile.to_dict())

    def _handle_list_upload(self, data: dict) -> None:
        app = self.server
        filename = (data.get("filename") or "").strip()
        content = data.get("content") or ""
        if not filename or not content:
            self._json({"error": "informe filename e content"}, 400)
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"
        dest = Path(app.cfg.lists_dir) / filename
        try:
            kind, entries = parse_csv_text(content)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": f"CSV inválido: {exc}"}, 400)
            return
        dest.write_text(content, encoding="utf-8")
        app.reload_lists()
        self._json({"ok": True, "filename": filename, "kind": kind, "count": len(entries)}, 201)

    def _handle_block(self, pid: str, kind: str, data: dict) -> None:
        app = self.server
        profile = app.get_profile(pid)
        if profile is None:
            self._json({"error": "perfil não encontrado"}, 404)
            return

        if kind == "channel":
            handle, url = normalize_channel(data.get("handle", "") or data.get("url", ""))
            if not handle:
                self._json({"error": "informe o canal (handle ou URL)"}, 400)
                return
            name = _sanitize_csv((data.get("name") or "").strip()) or handle
            categoria = "canal"
        elif kind == "video":
            url = _sanitize_csv((data.get("url") or "").strip())
            if not url:
                self._json({"error": "informe a URL do vídeo"}, 400)
                return
            name = _sanitize_csv((data.get("name") or "").strip())
            handle = _sanitize_csv((data.get("handle") or "").strip())
            categoria = "video"
        elif kind in ("url", "domain"):
            url = _sanitize_csv((data.get("url") or "").strip())
            name = _sanitize_csv((data.get("name") or "").strip())
            if not url:
                self._json({"error": "informe a URL"}, 400)
                return
            host = ""
            try:
                host = urllib.parse.urlparse(url if "://" in url else "http://" + url).hostname or ""
            except Exception:  # noqa: BLE001
                pass
            if kind == "domain":
                handle = host or url
                url = host or url
                name = name or host
            else:
                handle = host
                if not name:
                    name = url
            categoria = "dominio" if kind == "domain" else "url"
        else:
            self._json({"error": "tipo de bloqueio inválido"}, 400)
            return

        filename = f"block_manual_{pid}.csv"
        path = Path(app.cfg.lists_dir) / filename
        header = "handle,nome_canal,url,categoria,motivo_bloqueio,nivel_risco,alternativa_saudavel\n"
        if not path.exists():
            path.write_text(header, encoding="utf-8")
        else:
            existing = path.read_text(encoding="utf-8")
            for line in existing.splitlines():
                cells = line.split(",")
                if cells and cells[0] and cells[0] == handle and (len(cells) > 2 and cells[2] == url):
                    self._json({"ok": True, "handle": handle, "already": True,
                                "block_lists": profile.block_lists})
                    return
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{handle},{name},{url},{categoria},bloqueio manual,alto,\n")
        if filename not in profile.block_lists:
            profile.block_lists.append(filename)
        app.store.upsert_profile(profile.to_dict())
        app.reload_lists()
        self._json({"ok": True, "handle": handle, "filename": filename,
                    "categoria": categoria, "block_lists": profile.block_lists}, 201)

    def _handle_unblock(self, pid: str, data: dict) -> None:
        app = self.server
        profile = app.get_profile(pid)
        if profile is None:
            self._json({"error": "perfil não encontrado"}, 404)
            return
        filename = (data.get("file") or "").strip()
        handle = (data.get("handle") or "").strip()
        url = (data.get("url") or "").strip()
        if not filename or not (handle or url):
            self._json({"error": "informe file e handle/url"}, 400)
            return
        path = Path(app.cfg.lists_dir) / filename
        if not path.exists():
            self._json({"error": "arquivo de lista não encontrado"}, 404)
            return
        removed = False
        lines = path.read_text(encoding="utf-8").splitlines()
        keep: list[str] = []
        for line in lines:
            cells = [c.strip() for c in line.split(",")]
            if len(cells) >= 3:
                match = (cells[0] == handle) if handle else (cells[2] == url)
                if match:
                    removed = True
                    continue
            keep.append(line)
        if not removed:
            self._json({"ok": False, "error": "entrada não encontrada"})
            return
        text = "\n".join(keep)
        if text and not text.endswith("\n"):
            text += "\n"
        path.write_text(text, encoding="utf-8")
        app.reload_lists()
        self._json({"ok": True, "filename": filename})

    def _handle_list_file_get(self, path: str) -> None:
        app = self.server
        filename = urllib.parse.unquote(path.rsplit("/", 1)[-1])
        fpath = Path(app.cfg.lists_dir) / filename
        if not fpath.exists():
            self._json({"error": "lista não encontrada"}, 404)
            return
        try:
            kind, entries = load_csv(fpath)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": f"CSV inválido: {exc}"}, 400)
            return
        self._json({"filename": filename, "kind": kind, "count": len(entries),
                    "content": fpath.read_text(encoding="utf-8")})

    def _handle_list_file_put(self, path: str, data: dict) -> None:
        app = self.server
        filename = urllib.parse.unquote(path.rsplit("/", 1)[-1]).strip()
        content = data.get("content")
        if content is None:
            self._json({"error": "informe content"}, 400)
            return
        try:
            kind, entries = parse_csv_text(content)
        except Exception as exc:  # noqa: BLE001
            self._json({"error": f"CSV inválido: {exc}"}, 400)
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"
        text = content if content.endswith("\n") else content + "\n"
        dest = Path(app.cfg.lists_dir) / filename
        dest.write_text(text, encoding="utf-8")
        app.reload_lists()
        self._json({"ok": True, "filename": filename, "kind": kind, "count": len(entries)})

    def _handle_client_lists(self, qs: dict) -> None:
        token = (qs.get("token") or [""])[0]
        profile = self.server.get_profile_by_token(token)
        if profile is None:
            self._json({"error": "token inválido"}, 401)
            return
        block = {fname: [e.to_dict() for e in self.server.lists.get("block", {}).get(fname, [])]
                 for fname in profile.block_lists}
        allow = {fname: [e.to_dict() for e in self.server.lists.get("allow", {}).get(fname, [])]
                 for fname in profile.allow_lists}
        self._json({
            "profile_id": profile.id,
            "name": profile.name,
            "linux_user": profile.linux_user,
            "allowed_browsers": profile.allowed_browsers,
            "filters": profile.filters,
            "block_lists": block,
            "allow_lists": allow,
            "admin_password_hash": self.server.cfg.admin_password_hash,
        })

    def _handle_client_report(self, data: dict) -> None:
        token = data.get("token", "")
        profile = self.server.get_profile_by_token(token)
        if profile is None:
            self._json({"error": "token inválido"}, 401)
            return
        pid = profile.id
        store = self.server.store
        n_usage = n_urls = n_hist = 0
        for u in data.get("usage", []):
            store.add_app_usage(pid, u.get("app_name", ""), int(u.get("duration_seconds", 0)), u.get("started_at", ""))
            n_usage += 1
        for u in data.get("urls", []):
            store.add_url(pid, u.get("url", ""), u.get("title", ""), u.get("visited_at", ""))
            n_urls += 1
        for h in data.get("history", []):
            h["profile_id"] = pid
            store.add_history(h)
            n_hist += 1
        self._json({"ok": True, "usage": n_usage, "urls": n_urls, "history": n_hist})

    def _handle_client_heartbeat(self, data: dict) -> None:
        token = data.get("token", "")
        profile = self.server.get_profile_by_token(token)
        if profile is None:
            self._json({"error": "token inválido"}, 401)
            return
        self.server.store.heartbeat(
            profile.id, data.get("mode", ""),
            bool(data.get("active", False)), bool(data.get("server_ok", False)),
        )
        self._json({"ok": True})


class KidControlServer(ThreadingHTTPServer):
    def __init__(self, cfg: ServerConfig, config_path: str | Path | None = None) -> None:
        super().__init__((cfg.listen_host, cfg.listen_port), KidControlAPI)
        self.cfg = cfg
        self.config_path = Path(config_path) if config_path else None
        self.version = __import__("gltd_kid_server._version", fromlist=["__version__"]).__version__
        self.sessions = SessionManager()
        self.store = create_store(cfg)
        self.profiles = [Profile(**p) for p in self.store.list_profiles()]
        self.lists = load_all(cfg.lists_dir)
        self.web_dir = Path(__file__).parent / "web"

    def save(self) -> None:
        # salva apenas o config do servidor (admin/env/db); perfis vivem no store
        if self.config_path is None:
            return
        self.cfg.profiles = []
        save_config(self.cfg, self.config_path)

    def reload_lists(self) -> None:
        self.lists = load_all(self.cfg.lists_dir)

    def get_profile(self, pid: str) -> Profile | None:
        for p in self.profiles:
            if p.id == pid:
                return p
        return None

    def get_profile_by_token(self, token: str) -> Profile | None:
        if not token:
            return None
        for p in self.profiles:
            if p.client_token == token:
                return p
        return None

    def delete_profile(self, pid: str) -> bool:
        for i, p in enumerate(self.profiles):
            if p.id == pid:
                del self.profiles[i]
                self.store.delete_profile(pid)
                return True
        return False

    def lists_summary(self) -> dict:
        summary: dict[str, dict[str, int]] = {"block": {}, "allow": {}}
        for kind, files in self.lists.items():
            for name, entries in files.items():
                summary[kind][name] = len(entries)
        return summary

    def lists_files(self) -> list[dict]:
        result: list[dict] = []
        for kind, files in self.lists.items():
            for name, entries in files.items():
                result.append({"filename": name, "kind": kind, "count": len(entries)})
        return result

    def profile_summary(self, pid: str) -> dict:
        profile = self.get_profile(pid)
        usage = self.store.app_usage_list(pid, limit=100000)
        today = time.strftime("%Y-%m-%d")
        today_seconds = sum(int(e.get("duration_seconds", 0)) for e in usage
                            if str(e.get("started_at", "")).startswith(today))
        return {
            "profile": profile.to_dict() if profile else None,
            "youtube_count": len(self.store.list_history(pid, limit=100000)),
            "app_totals": self.store.app_usage_totals(pid),
            "url_count": len(self.store.url_list(pid, limit=100000)),
            "client": self.store.client_status(pid),
            "today_usage_seconds": today_seconds,
        }

    def profile_blocks(self, pid: str) -> dict:
        """Canais/vídeos/urls bloqueados aplicáveis ao perfil, com o arquivo de origem."""
        profile = self.get_profile(pid)
        if profile is None:
            return {"channels": [], "videos": [], "urls": []}
        channels, videos, urls = [], [], []
        for fname in profile.block_lists:
            for e in self.lists.get("block", {}).get(fname, []):
                cat = (e.categoria or "").lower()
                d = e.to_dict()
                d["file"] = fname
                if cat == "video":
                    videos.append(d)
                elif cat in ("url", "dominio"):
                    urls.append(d)
                else:
                    channels.append(d)
        return {"channels": channels, "videos": videos, "urls": urls}

    def add_filter(self, profile_id: str, expression: str) -> dict:
        profile = self.get_profile(profile_id)
        if profile is None:
            return {"ok": False, "error": "perfil não encontrado"}
        if not expression.strip():
            return {"ok": False, "error": "expressão vazia"}
        profile.filters.append(expression.strip())
        self.store.upsert_profile(profile.to_dict())
        return {"ok": True, "filters": profile.filters}

    def is_url_blocked(self, profile: Profile | None, url: str) -> bool:
        if not profile or not url:
            return False
        ul = url.lower()
        for f in profile.filters:
            if f.strip() and f.strip().lower() in ul:
                return True
        host = ""
        try:
            host = (urllib.parse.urlparse(url).hostname or "").lower()
        except Exception:  # noqa: BLE001
            pass
        for fname in profile.block_lists:
            for e in self.lists.get("block", {}).get(fname, []):
                cat = (e.categoria or "").lower()
                handle = (e.handle or "").lower()
                eurl = (e.url or "").lower()
                if cat in ("dominio", "url"):
                    if handle and host and handle in host:
                        return True
                    if eurl and eurl == ul:
                        return True
                if cat == "video" and eurl and eurl == ul:
                    return True
        return False


def run(cfg: ServerConfig, config_path: str | Path | None = None) -> None:
    from .config import ensure_dirs
    ensure_dirs(cfg)
    server = KidControlServer(cfg, config_path)
    print(f"GLTD Kid Control server em http://{cfg.listen_host}:{cfg.listen_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
        server.store.close()

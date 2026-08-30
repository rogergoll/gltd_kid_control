"""Persistência do GLTD Kid Control.

Dois backends com a mesma interface (Store):
  - MariaDBStore: MariaDB/MySQL local (padrão recomendado).
  - JsonStore: arquivos JSON no diretório de dados (fallback sem MariaDB).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

try:
    import pymysql  # type: ignore
except ImportError:  # permite rodar com o pacote vendored (dev, sem pip/sudo)
    import sys
    _vendor = str(Path(__file__).resolve().parents[2] / "vendor" / "usr" / "lib" / "python3" / "dist-packages")
    if _vendor not in sys.path:
        sys.path.insert(0, _vendor)
    import pymysql  # type: ignore

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS profiles (
        id VARCHAR(64) NOT NULL,
        name VARCHAR(128) NOT NULL,
        lan_ip VARCHAR(64) NOT NULL DEFAULT '',
        linux_user VARCHAR(64) NOT NULL DEFAULT '',
        allowed_browsers TEXT NOT NULL,
        block_lists TEXT NOT NULL,
        allow_lists TEXT NOT NULL,
        filters TEXT NOT NULL,
        client_token VARCHAR(128) NOT NULL DEFAULT '',
        daily_limit_minutes INT NOT NULL DEFAULT 0,
        youtube_limit_minutes INT NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS history (
        id BIGINT NOT NULL AUTO_INCREMENT,
        profile_id VARCHAR(64) NOT NULL,
        channel_handle VARCHAR(128) NOT NULL DEFAULT '',
        channel_name VARCHAR(255) NOT NULL DEFAULT '',
        video_title TEXT,
        video_url TEXT,
        thumb_url TEXT,
        description TEXT,
        watched_at VARCHAR(64) NOT NULL DEFAULT '',
        PRIMARY KEY (id), KEY idx_history_profile (profile_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS app_usage (
        id BIGINT NOT NULL AUTO_INCREMENT,
        profile_id VARCHAR(64) NOT NULL,
        app_name VARCHAR(128) NOT NULL,
        duration_seconds INT NOT NULL DEFAULT 0,
        started_at VARCHAR(64) NOT NULL DEFAULT '',
        PRIMARY KEY (id), KEY idx_usage_profile (profile_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS url_log (
        id BIGINT NOT NULL AUTO_INCREMENT,
        profile_id VARCHAR(64) NOT NULL,
        url TEXT,
        title TEXT,
        visited_at VARCHAR(64) NOT NULL DEFAULT '',
        PRIMARY KEY (id), KEY idx_url_profile (profile_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS settings (
        k VARCHAR(64) NOT NULL,
        v TEXT,
        PRIMARY KEY (k)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS client_heartbeat (
        profile_id VARCHAR(64) NOT NULL,
        mode VARCHAR(32) NOT NULL DEFAULT '',
        active TINYINT NOT NULL DEFAULT 0,
        server_ok TINYINT NOT NULL DEFAULT 0,
        last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (profile_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

DEFAULT_SETTINGS = {
    "admin_name": "",
    "lan_ip_range": "192.168.1.0/24",
    "ssh_user": "",
    "ssh_port": "22",
    "ssh_key_path": "",
    "sync_method": "rsync",
}


class MariaDBStore:
    """Backend MariaDB/MySQL (cada operação usa sua própria conexão)."""

    def __init__(self, host: str, port: int, user: str, password: str, database: str) -> None:
        self._params = dict(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4", autocommit=True,
        )
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self):
        return pymysql.connect(**self._params)

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    for stmt in _SCHEMA:
                        cur.execute(stmt)
                    self._migrate(cur)
            finally:
                conn.close()

    def _migrate(self, cur) -> None:
        """Adiciona colunas novas a tabelas existentes (instalações antigas)."""
        cur.execute("SHOW COLUMNS FROM profiles")
        cols = {r[0] for r in cur.fetchall()}
        for name, ddl in (
            ("daily_limit_minutes", "INT NOT NULL DEFAULT 0"),
            ("youtube_limit_minutes", "INT NOT NULL DEFAULT 0"),
        ):
            if name not in cols:
                cur.execute(f"ALTER TABLE profiles ADD COLUMN {name} {ddl}")

    # ---- perfis ----

    def list_profiles(self) -> list[dict]:
        sql = ("SELECT id,name,lan_ip,linux_user,allowed_browsers,block_lists,allow_lists,filters,client_token,"
               "daily_limit_minutes,youtube_limit_minutes "
               "FROM profiles ORDER BY name")
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [{
            "id": r[0], "name": r[1], "lan_ip": r[2] or "", "linux_user": r[3] or "",
            "allowed_browsers": json.loads(r[4] or "[]"),
            "block_lists": json.loads(r[5] or "[]"),
            "allow_lists": json.loads(r[6] or "[]"),
            "filters": json.loads(r[7] or "[]"),
            "client_token": r[8] or "",
            "daily_limit_minutes": int(r[9] or 0),
            "youtube_limit_minutes": int(r[10] or 0),
        } for r in rows]

    def upsert_profile(self, p: dict) -> None:
        sql = ("INSERT INTO profiles (id,name,lan_ip,linux_user,allowed_browsers,block_lists,allow_lists,filters,client_token,"
               "daily_limit_minutes,youtube_limit_minutes) "
               "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
               "ON DUPLICATE KEY UPDATE name=VALUES(name), lan_ip=VALUES(lan_ip), linux_user=VALUES(linux_user), "
               "allowed_browsers=VALUES(allowed_browsers), block_lists=VALUES(block_lists), "
               "allow_lists=VALUES(allow_lists), filters=VALUES(filters), client_token=VALUES(client_token), "
               "daily_limit_minutes=VALUES(daily_limit_minutes), youtube_limit_minutes=VALUES(youtube_limit_minutes)")
        args = (p["id"], p["name"], p.get("lan_ip", ""), p.get("linux_user", ""),
                json.dumps(p.get("allowed_browsers") or []), json.dumps(p.get("block_lists") or []),
                json.dumps(p.get("allow_lists") or []), json.dumps(p.get("filters") or []),
                p.get("client_token", ""),
                int(p.get("daily_limit_minutes", 0) or 0), int(p.get("youtube_limit_minutes", 0) or 0))
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
            finally:
                conn.close()

    def delete_profile(self, profile_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM profiles WHERE id=%s", (profile_id,))
            finally:
                conn.close()

    # ---- histórico (youtube) ----

    def add_history(self, e: dict) -> int:
        sql = ("INSERT INTO history (profile_id,channel_handle,channel_name,video_title,video_url,thumb_url,description,watched_at) "
               "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)")
        args = (e["profile_id"], e.get("channel_handle", ""), e.get("channel_name", ""),
                e.get("video_title", ""), e.get("video_url", ""), e.get("thumb_url", ""),
                e.get("description", ""), e.get("watched_at", ""))
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, args)
                    return int(cur.lastrowid)
            finally:
                conn.close()

    def list_history(self, profile_id: str | None = None, limit: int = 200) -> list[dict]:
        where, args = ("", ()) if profile_id is None else ("WHERE profile_id=%s", (profile_id,))
        sql = ("SELECT id,profile_id,channel_handle,channel_name,video_title,video_url,thumb_url,description,watched_at "
               f"FROM history {where} ORDER BY watched_at DESC, id DESC LIMIT %s")
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, args + (limit,))
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [self._hist(r) for r in rows]

    def _hist(self, r) -> dict:
        return {"id": r[0], "profile_id": r[1], "channel_handle": r[2], "channel_name": r[3],
                "video_title": r[4], "video_url": r[5], "thumb_url": r[6], "description": r[7],
                "watched_at": r[8]}

    # ---- uso de aplicativos ----

    def add_app_usage(self, profile_id: str, app_name: str, duration_seconds: int, started_at: str) -> int:
        sql = "INSERT INTO app_usage (profile_id,app_name,duration_seconds,started_at) VALUES (%s,%s,%s,%s)"
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (profile_id, app_name, duration_seconds, started_at))
                    return int(cur.lastrowid)
            finally:
                conn.close()

    def app_usage_list(self, profile_id: str, limit: int = 200) -> list[dict]:
        sql = ("SELECT app_name,duration_seconds,started_at FROM app_usage "
               "WHERE profile_id=%s ORDER BY id DESC LIMIT %s")
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (profile_id, limit))
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [{"app_name": r[0], "duration_seconds": r[1], "started_at": r[2]} for r in rows]

    def app_usage_totals(self, profile_id: str) -> list[dict]:
        sql = ("SELECT app_name,SUM(duration_seconds) AS total,COUNT(*) AS sessions "
               "FROM app_usage WHERE profile_id=%s GROUP BY app_name ORDER BY total DESC")
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (profile_id,))
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [{"app_name": r[0], "total_seconds": int(r[1] or 0), "sessions": r[2]} for r in rows]

    # ---- urls ----

    def add_url(self, profile_id: str, url: str, title: str, visited_at: str) -> int:
        sql = "INSERT INTO url_log (profile_id,url,title,visited_at) VALUES (%s,%s,%s,%s)"
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (profile_id, url, title, visited_at))
                    return int(cur.lastrowid)
            finally:
                conn.close()

    def url_list(self, profile_id: str, limit: int = 200) -> list[dict]:
        sql = "SELECT url,title,visited_at FROM url_log WHERE profile_id=%s ORDER BY id DESC LIMIT %s"
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (profile_id, limit))
                    rows = cur.fetchall()
            finally:
                conn.close()
        return [{"url": r[0], "title": r[1], "visited_at": r[2]} for r in rows]

    # ---- configurações do sistema / acesso ----

    def get_settings(self) -> dict:
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT k,v FROM settings")
                    rows = cur.fetchall()
            finally:
                conn.close()
        data = dict(DEFAULT_SETTINGS)
        data.update({r[0]: r[1] for r in rows})
        return data

    def set_settings(self, d: dict) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    for k, v in d.items():
                        cur.execute(
                            "INSERT INTO settings (k,v) VALUES (%s,%s) "
                            "ON DUPLICATE KEY UPDATE v=VALUES(v)", (k, str(v)))
            finally:
                conn.close()

    # ---- heartbeat do client ----

    def heartbeat(self, profile_id: str, mode: str, active: bool, server_ok: bool) -> None:
        sql = ("INSERT INTO client_heartbeat (profile_id, mode, active, server_ok) "
               "VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE mode=VALUES(mode), "
               "active=VALUES(active), server_ok=VALUES(server_ok), last_seen=CURRENT_TIMESTAMP")
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (profile_id, mode, int(active), int(server_ok)))
            finally:
                conn.close()

    def client_status(self, profile_id: str) -> dict | None:
        with self._lock:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT mode, active, server_ok, last_seen FROM client_heartbeat WHERE profile_id=%s",
                                (profile_id,))
                    r = cur.fetchone()
            finally:
                conn.close()
        if not r:
            return None
        return {"mode": r[0], "active": bool(r[1]), "server_ok": bool(r[2]),
                "last_seen": str(r[3])}

    def close(self) -> None:
        pass


class JsonStore:
    """Backend em arquivos JSON (fallback, no diretório de dados).

    - profiles.json                     -> tabela de perfis
    - history/<YYYY-MM-DD>.json         -> histórico/log por data
    - usage/<YYYY-MM-DD>.json           -> uso de aplicativos por data
    - urls/<YYYY-MM-DD>.json            -> urls navegadas por data
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)
        self._profiles = self._dir / "profiles.json"
        self._lock = threading.Lock()
        for sub in ("history", "usage", "urls"):
            (self._dir / sub).mkdir(parents=True, exist_ok=True)

    def _read(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return default

    def _write(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _log_path(self, sub: str, day: str) -> Path:
        return self._dir / sub / f"{day}.json"

    def _append_log(self, sub: str, entry: dict) -> int:
        entry = dict(entry)
        entry["id"] = int(time.time() * 1000)
        path = self._log_path(sub, self._today())
        items = self._read(path, [])
        items.append(entry)
        self._write(path, items)
        return entry["id"]

    def _read_log(self, sub: str, profile_id: str | None, limit: int) -> list[dict]:
        out: list[dict] = []
        for path in sorted((self._dir / sub).glob("*.json")):
            for e in self._read(path, []):
                if profile_id is None or e.get("profile_id") == profile_id:
                    out.append(e)
        out.sort(key=lambda e: e.get("id", 0), reverse=True)
        return out[:limit]

    # ---- perfis ----

    def list_profiles(self) -> list[dict]:
        with self._lock:
            return self._read(self._profiles, [])

    def upsert_profile(self, p: dict) -> None:
        with self._lock:
            profiles = self._read(self._profiles, [])
            profiles = [x for x in profiles if x.get("id") != p["id"]]
            profiles.append(p)
            self._write(self._profiles, profiles)

    def delete_profile(self, profile_id: str) -> None:
        with self._lock:
            profiles = self._read(self._profiles, [])
            self._write(self._profiles, [x for x in profiles if x.get("id") != profile_id])

    # ---- histórico / uso / urls ----

    def add_history(self, e: dict) -> int:
        with self._lock:
            return self._append_log("history", e)

    def list_history(self, profile_id: str | None = None, limit: int = 200) -> list[dict]:
        with self._lock:
            return self._read_log("history", profile_id, limit)

    def add_app_usage(self, profile_id: str, app_name: str, duration_seconds: int, started_at: str) -> int:
        with self._lock:
            return self._append_log("usage", {"profile_id": profile_id, "app_name": app_name,
                                              "duration_seconds": duration_seconds, "started_at": started_at})

    def app_usage_list(self, profile_id: str, limit: int = 200) -> list[dict]:
        with self._lock:
            return self._read_log("usage", profile_id, limit)

    def app_usage_totals(self, profile_id: str) -> list[dict]:
        with self._lock:
            totals: dict[str, dict] = {}
            for e in self._read_log("usage", profile_id, 10_000):
                t = totals.setdefault(e["app_name"], {"total_seconds": 0, "sessions": 0})
                t["total_seconds"] += int(e.get("duration_seconds", 0))
                t["sessions"] += 1
            return [{"app_name": k, **v} for k, v in
                    sorted(totals.items(), key=lambda kv: -kv[1]["total_seconds"])]

    def add_url(self, profile_id: str, url: str, title: str, visited_at: str) -> int:
        with self._lock:
            return self._append_log("urls", {"profile_id": profile_id, "url": url,
                                             "title": title, "visited_at": visited_at})

    def url_list(self, profile_id: str, limit: int = 200) -> list[dict]:
        with self._lock:
            return self._read_log("urls", profile_id, limit)

    # ---- configurações do sistema / acesso ----

    def get_settings(self) -> dict:
        with self._lock:
            data = dict(DEFAULT_SETTINGS)
            data.update(self._read(self._dir / "settings.json", {}))
            return data

    def set_settings(self, d: dict) -> None:
        with self._lock:
            data = self._read(self._dir / "settings.json", {})
            data.update({k: str(v) for k, v in d.items()})
            self._write(self._dir / "settings.json", data)

    # ---- heartbeat do client ----

    def heartbeat(self, profile_id: str, mode: str, active: bool, server_ok: bool) -> None:
        import datetime
        with self._lock:
            data = self._read(self._dir / "heartbeats.json", {})
            data[profile_id] = {"mode": mode, "active": active, "server_ok": server_ok,
                                "last_seen": datetime.datetime.now().isoformat()}
            self._write(self._dir / "heartbeats.json", data)

    def client_status(self, profile_id: str) -> dict | None:
        with self._lock:
            data = self._read(self._dir / "heartbeats.json", {})
            return data.get(profile_id)

    def close(self) -> None:
        pass


def create_store(cfg) -> "MariaDBStore | JsonStore":
    if getattr(cfg, "db_backend", "json") == "mariadb":
        return MariaDBStore(
            host=cfg.db_host, port=cfg.db_port, user=cfg.db_user,
            password=cfg.db_password, database=cfg.db_name,
        )
    return JsonStore(cfg.data_dir)

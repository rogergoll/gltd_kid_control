"""Núcleo do client: loop do daemon (enforcement + reporte + status)."""
from __future__ import annotations

import json
import os
import pwd
import re
import subprocess
import time

from .config import ClientConfig, RUN_DIR, ensure_run_dir
from .reporter import Reporter
from . import brave_history, enforce

STATUS_FILE = RUN_DIR + "/status.json"
STATE_FILE = "/var/lib/gltd-kid-control/client_state.json"


def _load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:  # noqa: BLE001
        pass


_dns = None


def _get_dns():
    global _dns
    if _dns is None:
        from .dns import LocalDNS
        _dns = LocalDNS()
        try:
            _dns.start()
        except Exception:  # noqa: BLE001
            pass
    return _dns


def _update_dns(domains: list[str]) -> None:
    try:
        _get_dns().update_domains(set(domains))
    except Exception:  # noqa: BLE001
        pass


def _is_paused() -> bool:
    try:
        with open("/run/gltd-kid-control/paused.json", encoding="utf-8") as fh:
            data = json.load(fh)
        return bool(data.get("paused")) and time.time() < float(data.get("until", 0))
    except Exception:  # noqa: BLE001
        return False


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def write_status(status: dict) -> None:
    ensure_run_dir()
    status = dict(status)
    status["updated_at"] = _now_iso()
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as fh:
            json.dump(status, fh, ensure_ascii=False)
    except OSError:
        pass


def _session_env(linux_user: str) -> dict:
    """Variáveis de ambiente (DISPLAY/XAUTHORITY/DBUS) da sessão gráfica do usuário."""
    try:
        uid = pwd.getpwnam(linux_user).pw_uid
    except KeyError:
        return {}

    # 1) via loginctl (Leader da sessão)
    try:
        out = subprocess.check_output(["loginctl", "list-sessions", "--no-legend"], text=True)
    except Exception:  # noqa: BLE001
        out = ""
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        sid = parts[0]
        try:
            info = subprocess.check_output(
                ["loginctl", "show-session", sid, "-p", "Name", "-p", "Leader"], text=True)
        except Exception:  # noqa: BLE001
            continue
        d = {}
        for l in info.splitlines():
            if "=" in l:
                k, v = l.split("=", 1)
                d[k.strip()] = v.strip()
        if d.get("Name") == linux_user and d.get("Leader"):
            env = _proc_env(d["Leader"])
            if env.get("DISPLAY"):
                return env

    # 2) fallback: varre os processos do usuário atrás de DISPLAY/XAUTHORITY/DBUS
    env: dict[str, str] = {}
    try:
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except Exception:  # noqa: BLE001
        return env
    for pid in pids:
        try:
            with open(f"/proc/{pid}/status") as fh:
                p_uid = None
                for line in fh:
                    if line.startswith("Uid:"):
                        p_uid = int(line.split()[1])
                        break
            if p_uid != uid:
                continue
        except (OSError, ValueError):
            continue
        pe = _proc_env(pid)
        for key in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS"):
            if key not in env and pe.get(key):
                env[key] = pe[key]
        if all(k in env for k in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")):
            break
    return env


def _proc_env(pid: str) -> dict:
    env: dict[str, str] = {}
    try:
        with open(f"/proc/{pid}/environ", "rb") as fh:
            for item in fh.read().split(b"\0"):
                if b"=" in item:
                    k, v = item.split(b"=", 1)
                    env[k.decode()] = v.decode()
    except Exception:  # noqa: BLE001
        pass
    return env


def spawn_tray(cfg: ClientConfig) -> None:
    """(Re)inicia o ícone de status na sessão gráfica da criança, se necessário."""
    if not cfg.linux_user:
        return
    try:
        out = subprocess.check_output(
            ["pgrep", "-u", cfg.linux_user, "-f", "gltd_kid_client.tray"], text=True)
        if out.strip():
            return
    except Exception:  # noqa: BLE001
        pass
    env = _session_env(cfg.linux_user)
    if not env.get("DISPLAY"):
        return
    cmd = ["runuser", "-u", cfg.linux_user, "--", "env",
           f"DISPLAY={env.get('DISPLAY', ':0')}",
           f"XAUTHORITY={env.get('XAUTHORITY', '/home/' + cfg.linux_user + '/.Xauthority')}",
           f"DBUS_SESSION_BUS_ADDRESS={env.get('DBUS_SESSION_BUS_ADDRESS', '')}",
           "python3", "-m", "gltd_kid_client.tray"]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception:  # noqa: BLE001
        pass


def _network_connected_pids() -> set[int]:
    """PIDs com conexões de rede estabelecidas (via ss -tunp)."""
    try:
        out = subprocess.check_output(["ss", "-tunp"], text=True, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        return set()
    pids: set[int] = set()
    for line in out.splitlines():
        m = re.search(r"pid=(\d+)", line)
        if m:
            pids.add(int(m.group(1)))
    return pids


def collect_usage(linux_user: str, interval: int) -> list[dict]:
    """Apps com conexão de rede (navegadores, jogos online etc.) do usuário."""
    try:
        uid = pwd.getpwnam(linux_user).pw_uid
    except KeyError:
        return []
    connected = _network_connected_pids()
    apps: set[str] = set()
    for pid in connected:
        try:
            p_uid = None
            with open(f"/proc/{pid}/status") as fh:
                for line in fh:
                    if line.startswith("Uid:"):
                        p_uid = int(line.split()[1])
                        break
            if p_uid != uid:
                continue
            with open(f"/proc/{pid}/comm") as fh:
                comm = fh.read().strip()
        except (OSError, ValueError):
            continue
        if comm and not comm.startswith(("(", ")", "kworker", "dbus", "systemd")):
            apps.add(comm)
    now = _now_iso()
    return [{"app_name": a, "duration_seconds": interval, "started_at": now} for a in sorted(apps)]


def build_block_cache(lists_data: dict) -> dict:
    """Transforma a resposta de /api/client/lists em um cache simples p/ a extensão."""
    channels: list[dict] = []
    videos: list[str] = []
    domains: set[str] = set()
    for fname, entries in (lists_data.get("block_lists") or {}).items():
        for e in entries:
            handle = (e.get("handle") or "").strip()
            cat = (e.get("categoria") or "").lower()
            url = (e.get("url") or "").strip()
            name = (e.get("nome_canal") or "").strip()
            if cat == "video":
                if url:
                    videos.append(url)
            elif cat in ("url", "dominio"):
                if handle and not handle.startswith("@"):
                    domains.add(handle)
                if url and not url.startswith("http"):
                    domains.add(url)
            elif handle.startswith("@"):
                channels.append({"handle": handle.lstrip("@").lower(), "name": name.lower()})
    return {
        "channels": channels,
        "videos": videos,
        "domains": sorted(domains),
        "filters": [f.lower() for f in (lists_data.get("filters") or [])],
    }


def run_once(cfg: ClientConfig) -> None:
    status: dict = {"active": False, "server_ok": False, "killed": 0, "mode": "inativo"}

    if not cfg.linux_user:
        write_status(status)
        return

    if enforce.active_user() != cfg.linux_user:
        status["mode"] = "inativo"
        status["reason"] = "usuário diferente logado"
        write_status(status)
        return

    status["active"] = True
    reporter = Reporter(cfg)

    # contato com o servidor
    ok = reporter.health()
    status["server_ok"] = ok

    # busca e cacheia as listas de bloqueio (para a extensão e o DNS local)
    if ok:
        try:
            lists_data = reporter.fetch_lists()
            cache = build_block_cache(lists_data)
            with open("/run/gltd-kid-control/lists_cache.json", "w", encoding="utf-8") as fh:
                json.dump(cache, fh, ensure_ascii=False)
            # atualiza domínios bloqueados no DNS local
            _update_dns(cache.get("domains", []))
            # cacheia o hash da senha do admin (para pausa offline)
            h = lists_data.get("admin_password_hash", "")
            if h:
                with open("/run/gltd-kid-control/admin_hash", "w", encoding="utf-8") as fh:
                    fh.write(h)
        except Exception:  # noqa: BLE001
            pass

    # verifica se a filtragem está pausada
    paused = _is_paused()
    status["paused"] = paused

    if paused:
        # remove redirecionamento de DNS e não bloqueia navegadores
        enforce.remove_dns_redirect(cfg.linux_user)
        status["mode"] = "pausado"
        write_status(status)
        spawn_tray(cfg)
        return

    # bloqueio de navegadores não autorizados
    if cfg.enforce_browsers:
        status["killed"] = enforce.kill_forbidden_browsers(cfg.linux_user, cfg.allowed_browsers)

    # redireciona DNS do usuário para o DNS local (bloqueio de domínios)
    try:
        enforce.apply_dns_redirect(cfg.linux_user, cfg.dns_port)
    except Exception:  # noqa: BLE001
        pass

    # coleta de dados
    usage = collect_usage(cfg.linux_user, cfg.report_interval)
    urls: list[dict] = []
    history: list[dict] = []
    try:
        home = pwd.getpwnam(cfg.linux_user).pw_dir
        db = brave_history.find_history_db(home)
        if db:
            state = _load_state()
            since_us = int(state.get("last_chrome_us", 0))
            entries = brave_history.recent_entries(db, since_us=since_us)
            urls = [{"url": e["url"], "title": e["title"], "visited_at": e["visited_at"]} for e in entries]
            history = brave_history.youtube_entries(entries)
            if entries:
                state["last_chrome_us"] = max(e["chrome_us"] for e in entries)
                _save_state(state)
    except Exception:  # noqa: BLE001
        pass

    # reporte ao servidor
    if ok:
        try:
            reporter.report({"usage": usage, "urls": urls, "history": history})
        except Exception:  # noqa: BLE001
            pass

    status["mode"] = "ativo" if ok else "bloqueado"
    status["reported"] = {"usage": len(usage), "urls": len(urls), "history": len(history)}

    # heartbeat (status do client no servidor)
    if ok:
        try:
            reporter.heartbeat(status["mode"], status["active"], ok)
        except Exception:  # noqa: BLE001
            pass

    write_status(status)

    # garante que o ícone de status esteja rodando na sessão da criança
    spawn_tray(cfg)


def run_daemon(cfg: ClientConfig) -> None:
    # servidor HTTP local (página de bloqueio + listas para a extensão)
    from . import localserver
    try:
        server = localserver.run_local_server()
        import threading
        threading.Thread(target=server.serve_forever, daemon=True).start()
    except Exception:  # noqa: BLE001
        pass

    # servidor DNS local (bloqueio de domínios)
    _get_dns()

    while True:
        try:
            run_once(cfg)
        except Exception:  # noqa: BLE001
            write_status({"active": False, "server_ok": False, "mode": "erro"})
        time.sleep(max(5, cfg.report_interval))

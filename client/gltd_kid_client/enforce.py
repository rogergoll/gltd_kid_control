"""Bloqueio de navegadores e detecção do usuário ativo (stdlib)."""
from __future__ import annotations

import os
import pwd
import signal
import subprocess

BROWSER_NAMES = (
    "firefox", "chrome", "chromium", "opera", "vivaldi", "edge",
    "epiphany", "webkit", "librewolf", "waterfox", "brave", "safari",
)


def active_user() -> str:
    """Usuário dono da sessão gráfica ativa ('' se ninguém logado)."""
    # 1) loginctl (mais confiável)
    try:
        out = subprocess.check_output(["loginctl", "list-sessions", "--no-legend"], text=True)
        for line in out.splitlines():
            parts = line.split()
            if not parts:
                continue
            sid = parts[0]
            info = subprocess.check_output(
                ["loginctl", "show-session", sid, "-p", "Name", "-p", "Active", "-p", "Type"],
                text=True,
            )
            d = {}
            for l in info.splitlines():
                if "=" in l:
                    k, v = l.split("=", 1)
                    d[k.strip()] = v.strip()
            if d.get("Active") == "yes" and d.get("Type") in ("wayland", "x11"):
                return d.get("Name", "")
    except Exception:  # noqa: BLE001
        pass

    # 2) who (fallback): preferir sessão gráfica (tty*, :0), ignorar SSH (pts/)
    try:
        out = subprocess.check_output(["who"], text=True).strip()
    except Exception:  # noqa: BLE001
        return ""
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            user, tty = parts[0], parts[1]
            if tty.startswith("tty") or tty == ":0" or "(:0)" in line:
                return user
    for line in out.splitlines():
        parts = line.split()
        if parts:
            return parts[0]
    return ""


def _is_browser(comm: str) -> bool:
    return any(b in comm for b in BROWSER_NAMES)


def _is_allowed(comm: str, allowed: list[str]) -> bool:
    for a in allowed:
        a = a.lower()
        if a in comm or a.split("-")[0] in comm:
            return True
    return False


def kill_forbidden_browsers(linux_user: str, allowed: list[str]) -> int:
    """Mata processos de navegadores não autorizados pertencentes ao usuário."""
    if not linux_user:
        return 0
    try:
        target_uid = pwd.getpwnam(linux_user).pw_uid
    except KeyError:
        return 0
    killed = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/comm") as fh:
                comm = fh.read().strip().lower()
            uid = None
            with open(f"/proc/{pid}/status") as fh:
                for line in fh:
                    if line.startswith("Uid:"):
                        uid = int(line.split()[1])
                        break
            if uid != target_uid:
                continue
        except (OSError, ValueError):
            continue
        if _is_browser(comm) and not _is_allowed(comm, allowed):
            try:
                os.kill(int(pid), signal.SIGKILL)
                killed += 1
            except OSError:
                pass
    return killed


def apply_dns_redirect(linux_user: str, dns_port: int = 5300) -> None:
    """Redireciona as consultas DNS do usuário para o DNS local (via iptables REDIRECT)."""
    if not linux_user:
        return
    for proto in ("udp", "tcp"):
        rule = ["iptables", "-t", "nat", "-C", "OUTPUT",
                "-m", "owner", "--uid-owner", linux_user,
                "-p", proto, "--dport", "53", "-j", "REDIRECT", "--to-ports", str(dns_port)]
        add = ["iptables", "-t", "nat", "-A", "OUTPUT",
               "-m", "owner", "--uid-owner", linux_user,
               "-p", proto, "--dport", "53", "-j", "REDIRECT", "--to-ports", str(dns_port)]
        r = subprocess.run(rule, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            subprocess.run(add, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def remove_dns_redirect(linux_user: str) -> None:
    """Remove o redirecionamento de DNS do usuário (para pausar a filtragem)."""
    if not linux_user:
        return
    for proto in ("udp", "tcp"):
        rule = ["iptables", "-t", "nat", "-C", "OUTPUT",
                "-m", "owner", "--uid-owner", linux_user,
                "-p", proto, "--dport", "53", "-j", "REDIRECT", "--to-ports", "5300"]
        remove = ["iptables", "-t", "nat", "-D", "OUTPUT",
                  "-m", "owner", "--uid-owner", linux_user,
                  "-p", proto, "--dport", "53", "-j", "REDIRECT", "--to-ports", "5300"]
        r = subprocess.run(rule, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            subprocess.run(remove, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

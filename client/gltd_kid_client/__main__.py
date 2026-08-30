"""CLI do client: setup | daemon | once | status."""
from __future__ import annotations

import argparse
import sys

from . import __version__


def cmd_setup(args) -> int:
    from .config import load_config, save_config
    cfg = load_config()
    print("GLTD Kid Control — configuração do client")
    cfg.server_url = input(f"URL do servidor [{cfg.server_url or 'http://servidor.local:8123'}]: ").strip() or cfg.server_url or "http://servidor.local:8123"
    cfg.profile_id = input(f"ID do perfil [{cfg.profile_id or 'child'}]: ").strip() or cfg.profile_id or "child"
    cfg.client_token = input("Token do client (copie do painel do servidor): ").strip() or cfg.client_token
    cfg.linux_user = input(f"Usuário Linux da criança [{cfg.linux_user or 'child'}]: ").strip() or cfg.linux_user or "child"
    browsers = input("Navegadores permitidos (vírgula) [brave-browser]: ").strip()
    if browsers:
        cfg.allowed_browsers = [b.strip() for b in browsers.split(",") if b.strip()]
    save_config(cfg)

    # autostart do ícone de status na home da criança
    _write_autostart(cfg.linux_user)

    # reinicia o daemon
    _restart_daemon()

    print("Config salva em /etc/gltd-kid-control/client.json")
    print("Daemon reiniciado.")
    return 0


def _write_autostart(linux_user: str) -> None:
    import pwd
    import shutil
    import os
    try:
        home = pwd.getpwnam(linux_user).pw_dir
    except KeyError:
        return
    src = "/usr/share/gltd-kid-control/autostart.desktop"
    if not os.path.exists(src):
        return
    dst_dir = os.path.join(home, ".config", "autostart")
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy(src, os.path.join(dst_dir, "gltd-kid-control-client.desktop"))


def _restart_daemon() -> None:
    import subprocess
    subprocess.run(["systemctl", "restart", "gltd-kid-client.service"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cmd_once(args) -> int:
    from .config import load_config
    from .core import run_once
    cfg = load_config()
    if not cfg.server_url or not cfg.client_token:
        print("Client não configurado. Rode: gltd-kid-client --setup")
        return 1
    run_once(cfg)
    print("Executado uma vez.")
    return 0


def cmd_daemon(args) -> int:
    from .config import load_config
    from .core import run_daemon
    cfg = load_config()
    if not cfg.server_url or not cfg.client_token:
        print("Client não configurado. Rode: gltd-kid-client --setup")
        return 1
    run_daemon(cfg)
    return 0


def cmd_status(args) -> int:
    import os
    p = "/run/gltd-kid-control/status.json"
    if os.path.exists(p):
        print(open(p, encoding="utf-8").read())
    else:
        print('{"active": false, "mode": "desconhecido"}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gltd-kid-client", description="GLTD Kid Control Client")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="configurar o client (servidor, token, usuário)")
    sub.add_parser("daemon", help="rodar o daemon em primeiro plano")
    sub.add_parser("once", help="executar um ciclo (enforce + report)")
    sub.add_parser("status", help="mostrar o status atual")

    args = parser.parse_args(argv)
    handlers = {"setup": cmd_setup, "daemon": cmd_daemon, "once": cmd_once, "status": cmd_status}
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())

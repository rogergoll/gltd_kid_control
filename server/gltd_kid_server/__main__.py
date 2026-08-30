"""Entrypoint CLI: python3 -m gltd_kid_server [opções]."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import ServerConfig, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gltd-kid-server", description="GLTD Kid Control Server")
    parser.add_argument("--config", "-c", default=None, help="caminho do config.json")
    parser.add_argument("--port", "-p", type=int, default=None, help="porta HTTP (sobrescreve config)")
    parser.add_argument("--host", type=str, default=None, help="endereço de escuta")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    cfg = load_config(args.config) if args.config else ServerConfig()
    if args.port:
        cfg.listen_port = args.port
    if args.host:
        cfg.listen_host = args.host

    from .api import run
    run(cfg, args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Assistente de primeira execução (esboço).

Na instalação do .deb, a primeira execução:
  1. pede a senha de root da máquina (via sudo);
  2. pergunta se funciona como SERVER ou CLIENT;
  3. se CLIENT: pergunta IP do server, user/senha e o usuário Linux local.

Este script implementa o fluxo SERVER; o fluxo CLIENT será adicionado
junto com o desenvolvimento do client/ (escopo futuro).
"""
from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
from pathlib import Path


def sudo_ok() -> bool:
    r = subprocess.run(
        ["sudo", "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def ask(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer or default


def setup_server(config_path: Path) -> None:
    print("== Configurando como SERVER ==")
    host = ask("Endereço de escuta", "0.0.0.0")
    port = ask("Porta HTTP", "8123")
    data_dir = ask("Diretório de dados", "/var/lib/gltd-kid-control")
    lists_dir = ask("Diretório das listas CSV", "/var/PROGRAMAS/gltd_kid_control/lists")

    backend = ask("Banco de dados: [M]ariaDB ou [J]SON local?", "M").lower()
    cfg = {
        "listen_host": host,
        "listen_port": int(port),
        "data_dir": data_dir,
        "lists_dir": lists_dir,
        "profiles": [],
        "admin_user": "",
        "admin_password_hash": "",
        "setup_done": False,
        "db_backend": "mariadb" if backend.startswith("m") else "json",
        "db_host": "127.0.0.1",
        "db_port": 3306,
        "db_user": "gltd_kcontrol_app",
        "db_password": "",
        "db_name": "gltd_kcontrol",
    }
    if cfg["db_backend"] == "mariadb":
        cfg["db_host"] = ask("Host do MariaDB", "127.0.0.1")
        cfg["db_port"] = int(ask("Porta do MariaDB", "3306"))
        cfg["db_user"] = ask("Usuário do MariaDB", "gltd_kcontrol_app")
        cfg["db_password"] = getpass.getpass("Senha do MariaDB: ")
        cfg["db_name"] = ask("Banco de dados", "gltd_kcontrol")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Config salva em {config_path}")
    print("Adicione os perfis das crianças editando o arquivo ou pela Web UI.")


def main() -> int:
    print("GLTD Kid Control — primeira execução")

    if not sudo_ok():
        print("Senha de root necessária para instalar serviços do sistema.")
        password = getpass.getpass("Senha do sudo: ")
        r = subprocess.run(
            ["sudo", "-S", "-v"], input=(password + "\n").encode(),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            print("Senha incorreta. Abortando.")
            return 1

    mode = ask("Funcionar como [S]erver ou [C]lient?", "S").lower()
    config_path = Path("/etc/gltd-kid-control/config.json")

    if mode.startswith("c"):
        print("Fluxo CLIENT será implementado junto com o client/ (escopo futuro).")
        return 0

    setup_server(config_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

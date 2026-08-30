"""Configuração do server: carrega/salva JSON e define caminhos padrão."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

APP_DIR = Path("/var/lib/gltd-kid-control")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LISTS_DIR = PROJECT_ROOT / "lists"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "server.example.json"


@dataclass
class ServerConfig:
    listen_host: str = "0.0.0.0"
    listen_port: int = 8123
    data_dir: str = str(APP_DIR)
    lists_dir: str = str(DEFAULT_LISTS_DIR)
    history_db: str = str(APP_DIR / "history.sqlite3")
    profiles: list[dict] = field(default_factory=list)
    admin_user: str = ""
    admin_password_hash: str = ""
    setup_done: bool = False
    db_backend: str = "json"      # "mariadb" | "json"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = ""
    db_password: str = ""
    db_name: str = "gltd_kcontrol"

    def to_dict(self) -> dict:
        return asdict(self)


def default_config() -> ServerConfig:
    return ServerConfig()


def load_config(path: str | Path) -> ServerConfig:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    cfg = ServerConfig()
    for key in cfg.to_dict():
        if key in raw:
            setattr(cfg, key, raw[key])
    return cfg


def save_config(cfg: ServerConfig, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg.to_dict(), fh, ensure_ascii=False, indent=2)


def ensure_dirs(cfg: ServerConfig) -> None:
    for d in (cfg.data_dir, cfg.lists_dir):
        os.makedirs(d, exist_ok=True)

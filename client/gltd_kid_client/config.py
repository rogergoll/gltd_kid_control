"""Configuração do client (arquivo JSON em /etc, root-only)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_PATH = "/etc/gltd-kid-control/client.json"
RUN_DIR = "/run/gltd-kid-control"


@dataclass
class ClientConfig:
    server_url: str = ""                      # ex.: http://servidor.local:8123
    profile_id: str = ""                      # id do perfil no servidor
    client_token: str = ""                    # token de autenticação do client
    linux_user: str = ""                      # usuário Linux da criança
    allowed_browsers: list[str] = field(default_factory=lambda: ["brave-browser"])
    report_interval: int = 30                 # segundos entre reportes
    block_threshold: int = 120                # segundos sem contato antes de "modo bloqueado"
    enforce_browsers: bool = True             # matar navegadores não autorizados
    extension_enabled: bool = True            # extensão do Brave para remodelar o YouTube
    dns_port: int = 5300                      # porta do DNS local do servidor

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: str | Path = CONFIG_PATH) -> ClientConfig:
    cfg = ClientConfig()
    p = Path(path)
    if not p.exists():
        return cfg
    raw = json.loads(p.read_text(encoding="utf-8"))
    for key in cfg.to_dict():
        if key in raw:
            setattr(cfg, key, raw[key])
    return cfg


def save_config(cfg: ClientConfig, path: str | Path = CONFIG_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(p, 0o600)


def ensure_run_dir() -> None:
    os.makedirs(RUN_DIR, mode=0o755, exist_ok=True)

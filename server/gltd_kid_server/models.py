"""Modelos de dados (dataclasses) do server."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ChannelEntry:
    """Uma linha de qualquer lista CSV (block ou allow)."""
    handle: str
    nome_canal: str
    url: str
    categoria: str
    info: str          # motivo_bloqueio OU beneficio, dependendo da lista
    extra: str = ""    # nivel_risco (block) ou idioma (allow)
    extra2: str = ""   # alternativa_saudavel (block) — vazio no allow

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Profile:
    """Perfil de uma criança."""
    id: str
    name: str
    lan_ip: str
    linux_user: str
    allowed_browsers: list[str] = field(default_factory=lambda: ["brave-browser"])
    block_lists: list[str] = field(default_factory=list)
    allow_lists: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)  # expressões/frases de bloqueio
    client_token: str = ""  # token de autenticação do client (máquina da criança)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HistoryEntry:
    """Vídeo/canal assistido no YouTube (coletado pelos clients)."""
    id: int = 0
    profile_id: str = ""
    channel_handle: str = ""
    channel_name: str = ""
    video_title: str = ""
    video_url: str = ""
    thumb_url: str = ""
    description: str = ""
    watched_at: str = ""  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

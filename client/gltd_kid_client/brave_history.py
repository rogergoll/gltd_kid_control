"""Leitura do histórico do Brave (SQLite, somente leitura) + enriquecimento."""
from __future__ import annotations

import datetime
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

# microssegundos entre 01/01/1601 (epoch Chrome) e 01/01/1970
_CHROME_EPOCH_US = 11644473600000000


def find_history_db(user_home: str | Path) -> str | None:
    base = Path(user_home) / ".config" / "BraveSoftware" / "Brave-Browser"
    if not base.exists():
        return None
    candidates = [base / "Default" / "History"] + sorted(base.glob("Profile */History"))
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _to_iso(chrome_us: int) -> str:
    try:
        return datetime.datetime.fromtimestamp((chrome_us - _CHROME_EPOCH_US) / 1e6).isoformat()
    except Exception:  # noqa: BLE001
        return ""


def recent_entries(db_path: str, since_us: int = 0, limit: int = 500) -> list[dict]:
    """Últimas URLs visitadas após `since_us` (epoch Chrome): [{url, title, visited_at, chrome_us}]."""
    cutoff_us = max(since_us, int((time.time() - 24 * 3600) * 1e6) + _CHROME_EPOCH_US)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True, timeout=3)
    except Exception:  # noqa: BLE001
        return []
    try:
        cur = conn.execute(
            "SELECT url, title, last_visit_time FROM urls "
            "WHERE last_visit_time > ? ORDER BY last_visit_time ASC LIMIT ?",
            (cutoff_us, limit),
        )
        rows = cur.fetchall()
    except Exception:  # noqa: BLE001
        return []
    finally:
        conn.close()
    out = []
    for url, title, lvt in rows:
        out.append({
            "url": url or "", "title": title or "",
            "visited_at": _to_iso(int(lvt)), "chrome_us": int(lvt),
        })
    return out


def extract_video_id(url: str) -> str:
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return (q.get("v") or [""])[0]
    except Exception:  # noqa: BLE001
        return ""


def _oembed(video_id: str) -> dict:
    url = (f"https://www.youtube.com/oembed?url="
           f"{urllib.parse.quote('https://www.youtube.com/watch?v=' + video_id)}&format=json")
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def enrich_video(video_id: str, title: str) -> dict:
    """Retorna {channel_name, video_title, thumb_url} enriquecidos via oEmbed."""
    clean_title = title[:-len(" - YouTube")].strip() if title.endswith(" - YouTube") else title
    data = _oembed(video_id)
    if data:
        return {
            "channel_name": data.get("author_name", ""),
            "channel_handle": data.get("author_url", ""),
            "video_title": data.get("title", clean_title),
            "thumb_url": data.get("thumbnail_url", ""),
        }
    return {
        "channel_name": "",
        "channel_handle": "",
        "video_title": clean_title,
        "thumb_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
    }


def youtube_entries(entries: list[dict]) -> list[dict]:
    """Filtra e enriquece as entradas do YouTube para o histórico do servidor."""
    out = []
    for e in entries:
        url = e["url"]
        if "youtube.com/watch" not in url:
            continue
        video_id = extract_video_id(url)
        if not video_id:
            continue
        info = enrich_video(video_id, e["title"])
        out.append({
            "channel_handle": info.get("channel_handle", ""),
            "channel_name": info.get("channel_name", ""),
            "video_title": info.get("video_title", e["title"]),
            "video_url": url,
            "thumb_url": info.get("thumb_url", ""),
            "description": "",
            "watched_at": e["visited_at"],
        })
    return out

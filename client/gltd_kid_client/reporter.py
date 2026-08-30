"""Comunicação HTTP com o servidor (stdlib urllib)."""
from __future__ import annotations

import json
import urllib.request
import urllib.parse

from .config import ClientConfig


class Reporter:
    def __init__(self, cfg: ClientConfig) -> None:
        self.cfg = cfg
        self.server = cfg.server_url.rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = self.server + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, data: dict) -> dict:
        url = self.server + path
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def health(self) -> bool:
        try:
            self._get("/api/health")
            return True
        except Exception:  # noqa: BLE001
            return False

    def fetch_lists(self) -> dict:
        return self._get("/api/client/lists", {"token": self.cfg.client_token})

    def report(self, payload: dict) -> dict:
        payload = dict(payload)
        payload["token"] = self.cfg.client_token
        return self._post("/api/client/report", payload)

    def heartbeat(self, mode: str, active: bool, server_ok: bool) -> dict:
        return self._post("/api/client/heartbeat", {
            "token": self.cfg.client_token,
            "mode": mode,
            "active": active,
            "server_ok": server_ok,
        })

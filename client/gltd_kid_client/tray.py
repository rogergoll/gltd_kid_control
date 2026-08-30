#!/usr/bin/env python3
"""Ícone de status do GLTD Kid Control na bandeja (máquina da criança).

Somente informativo: mostra o estado do client e envia notificações.
Sem opção de encerrar (a proteção não pode ser desligada pelo usuário criança).
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request

STATUS_FILE = "/run/gltd-kid-control/status.json"
ICON_DIR = "/usr/share/gltd-kid-control/icons"
ICON_OK_NAME = "gltd-kid-control"
ICON_BLOCKED_NAME = "gltd-kid-control-blocked"


def read_status() -> dict:
    try:
        with open(STATUS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def notify(summary: str, body: str) -> None:
    try:
        subprocess.Popen(["notify-send", "-i", "gltd-kid-control", summary, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass


def _post(action: str, payload: dict) -> dict:
    import urllib.request
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:8877/{action}", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def prompt_password(Gtk, parent) -> str | None:
    dlg = Gtk.Dialog(title="Pausar filtragem", transient_for=parent, modal=True)
    dlg.add_button("Cancelar", Gtk.ResponseType.CANCEL)
    dlg.add_button("Pausar", Gtk.ResponseType.OK)
    box = dlg.get_content_area()
    lbl = Gtk.Label(label="Digite a senha do admin do servidor:")
    lbl.show()
    box.add(lbl)
    entry = Gtk.Entry()
    entry.set_visibility(False)
    entry.set_activates_default(True)
    entry.show()
    box.add(entry)
    dlg.set_default_response(Gtk.ResponseType.OK)
    resp = dlg.run()
    value = entry.get_text() if resp == Gtk.ResponseType.OK else None
    dlg.destroy()
    return value


def pause_action(Gtk) -> None:
    pw = prompt_password(Gtk, None)
    if pw is None:
        return
    result = _post("pause", {"password": pw, "minutes": 30})
    if result.get("ok"):
        notify("GLTD Kid Control", "Filtragem pausada por 30 minutos.")
    else:
        notify("GLTD Kid Control", "Não foi possível pausar: " + (result.get("error") or "erro"))


def resume_action() -> None:
    _post("resume", {})
    notify("GLTD Kid Control", "Filtragem retomada.")


def main() -> int:
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator3
        except (ValueError, ImportError):
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3  # type: ignore
        from gi.repository import Gtk, GLib
    except Exception as exc:  # noqa: BLE001
        print(f"[tray] ambiente gráfico indisponível: {exc}")
        return 1

    if os.path.isdir(ICON_DIR):
        try:
            indicator = AppIndicator3.Indicator.new_with_path(
                "gltd-kid-control-client", ICON_OK_NAME,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS, ICON_DIR)
        except Exception:  # noqa: BLE001
            indicator = AppIndicator3.Indicator.new(
                "gltd-kid-control-client", "security-high",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
    else:
        indicator = AppIndicator3.Indicator.new(
            "gltd-kid-control-client", "security-high",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()
    status_item = Gtk.MenuItem(label="GLTD Kid Control")
    status_item.set_sensitive(False)
    status_item.show()
    menu.append(status_item)

    sep = Gtk.SeparatorMenuItem(); sep.show(); menu.append(sep)

    pause_item = Gtk.MenuItem(label="Pausar filtragem (30 min)")
    pause_item.connect("activate", lambda *_: pause_action(Gtk))
    pause_item.show()
    menu.append(pause_item)

    resume_item = Gtk.MenuItem(label="Retomar filtragem")
    resume_item.connect("activate", lambda *_: resume_action())
    resume_item.show()
    menu.append(resume_item)

    menu.show_all()
    indicator.set_menu(menu)

    last_mode: str | None = None

    def update() -> bool:
        nonlocal last_mode
        s = read_status()
        mode = s.get("mode", "desconhecido")
        active = s.get("active", False)
        server_ok = s.get("server_ok", False)

        if mode == "ativo" and server_ok:
            label = "GLTD Kid Control — protegido"
            tooltip = "Proteção ativa e conectada ao servidor"
            icon_name = ICON_OK_NAME
        elif mode == "bloqueado":
            label = "GLTD Kid Control — bloqueado"
            tooltip = "Sem contato com o servidor"
            icon_name = ICON_BLOCKED_NAME
        elif active:
            label = "GLTD Kid Control — ativo"
            tooltip = "Proteção ativa"
            icon_name = ICON_OK_NAME
        else:
            label = "GLTD Kid Control — inativo"
            tooltip = "Proteção inativa (nenhum usuário do perfil logado)"
            icon_name = ICON_BLOCKED_NAME

        status_item.set_label(label)
        indicator.set_title(label)
        try:
            indicator.set_icon(icon_name)
        except Exception:  # noqa: BLE001
            pass

        if mode != last_mode and last_mode is not None:
            notify(label, tooltip)
        last_mode = mode
        return True

    GLib.timeout_add_seconds(5, update)
    update()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

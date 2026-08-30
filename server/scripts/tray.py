#!/usr/bin/env python3
"""Ícone de status do GLTD Kid Control na bandeja do sistema (Cinnamon).

Mostra se o servidor está ativo/parado e permite iniciar/parar e abrir o painel.
"""
from __future__ import annotations

import os
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # project root
PORT = 8123
URL = f"http://localhost:{PORT}"
ICON = os.path.join(ROOT, "icons", "gltd-kid-control.png")
START_SH = os.path.join(ROOT, "server", "scripts", "server_start.sh")
STOP_SH = os.path.join(ROOT, "server", "scripts", "server_stop.sh")


def health() -> bool:
    try:
        urllib.request.urlopen(URL + "/api/health", timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def open_panel() -> None:
    browser = "brave-browser"
    cmd = [browser, URL + "/dashboard"] if shutil_which(browser) else ["xdg-open", URL + "/dashboard"]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shutil_which(name: str) -> bool:
    from shutil import which
    return which(name) is not None


def start_server() -> None:
    subprocess.Popen(["bash", START_SH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_server() -> None:
    subprocess.Popen(["bash", STOP_SH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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

    indicator = AppIndicator3.Indicator.new(
        "gltd-kid-control", ICON if os.path.exists(ICON) else "security-high",
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    status_item = Gtk.MenuItem(label="Servidor: verificando...")
    status_item.set_sensitive(False)
    status_item.show()
    menu.append(status_item)

    def sep():
        s = Gtk.SeparatorMenuItem(); s.show(); menu.append(s)

    def item(label, cb):
        it = Gtk.MenuItem(label=label)
        it.connect("activate", lambda *_: cb())
        it.show()
        menu.append(it)

    sep()
    item("Abrir painel", open_panel)
    item("Iniciar servidor", start_server)
    item("Parar servidor", stop_server)
    sep()
    item("Sair", Gtk.main_quit)

    menu.show_all()
    indicator.set_menu(menu)

    def update() -> bool:
        ok = health()
        status_item.set_label("Servidor: ativo" if ok else "Servidor: parado")
        indicator.set_title("GLTD Kid Control — ativo" if ok else "GLTD Kid Control — parado")
        return True

    GLib.timeout_add_seconds(5, update)
    update()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

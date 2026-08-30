"""Carrega e valida as listas CSV de canais (block/allow)."""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

from .models import ChannelEntry

# Cabeçalhos esperados para cada tipo de lista.
BLOCK_HEADER = [
    "handle", "nome_canal", "url", "categoria",
    "motivo_bloqueio", "nivel_risco", "alternativa_saudavel",
]
ALLOW_HEADER = [
    "handle", "nome_canal", "url", "categoria", "beneficio", "idioma",
]


def _detect_kind(header: list[str]) -> str:
    header = [h.lstrip("\ufeff").strip() for h in header]
    if header[:6] == ALLOW_HEADER:
        return "allow"
    if header[:5] == BLOCK_HEADER[:5]:
        return "block"
    raise ValueError(f"Cabeçalho de lista não reconhecido: {header}")


def _rows_to_entries(kind: str, rows: list[list[str]]) -> list[ChannelEntry]:
    entries: list[ChannelEntry] = []
    for row in rows:
        if kind == "block":
            e = ChannelEntry(
                handle=row[0], nome_canal=row[1], url=row[2],
                categoria=row[3], info=row[4],
                extra=row[5] if len(row) > 5 else "",
                extra2=row[6] if len(row) > 6 else "",
            )
        else:
            e = ChannelEntry(
                handle=row[0], nome_canal=row[1], url=row[2],
                categoria=row[3], info=row[4],
                extra=row[5] if len(row) > 5 else "",
            )
        entries.append(e)
    return entries


def parse_csv_text(text: str) -> tuple[str, list[ChannelEntry]]:
    """Retorna (kind, [ChannelEntry]) a partir do conteúdo CSV em texto."""
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    rows = [r for r in reader if r and any(cell.strip() for cell in r)]
    if not rows:
        return "unknown", []
    kind = _detect_kind(rows[0])
    return kind, _rows_to_entries(kind, rows[1:])


def load_csv(path: str | Path) -> tuple[str, list[ChannelEntry]]:
    """Retorna (kind, [ChannelEntry]) para um arquivo CSV."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return parse_csv_text(fh.read())


def load_all(lists_dir: str | Path) -> dict[str, dict[str, list[ChannelEntry]]]:
    """Carrega todos os CSVs do diretório, separando block/allow por arquivo."""
    result: dict[str, dict[str, list[ChannelEntry]]] = {"block": {}, "allow": {}}
    for path in sorted(Path(lists_dir).glob("*.csv")):
        kind, entries = load_csv(path)
        result[kind][path.name] = entries
    return result


def check_lists(lists_dir: str | Path) -> int:
    """Valida todos os CSVs; imprime um resumo e retorna 0 se tudo ok."""
    problems = 0
    total = 0
    for path in sorted(Path(lists_dir).glob("*.csv")):
        try:
            kind, entries = load_csv(path)
            total += len(entries)
            print(f"[ok] {path.name:32s} {kind:6s} {len(entries)} canais")
        except Exception as exc:  # noqa: BLE001
            problems += 1
            print(f"[ERRO] {path.name}: {exc}")
    print(f"--- {total} canais no total, {problems} problema(s) ---")
    return 1 if problems else 0


if __name__ == "__main__":
    import sys
    from .config import DEFAULT_LISTS_DIR
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LISTS_DIR
    sys.exit(check_lists(target))

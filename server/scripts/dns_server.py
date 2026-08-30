#!/usr/bin/env python3
"""Servidor DNS local do GLTD Kid Control (para bloqueio de domínios).

Roda no servidor, em porta alta (padrão 5353). O client redireciona as consultas
DNS do usuário-criança para cá via iptables. Domínios bloqueados respondem
NXDOMAIN; o restante é encaminhado ao DNS padrão.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import socket
import struct
import threading
import time


def parse_qname(data: bytes, off: int) -> tuple[str, int]:
    labels = []
    while True:
        ln = data[off]
        if ln == 0:
            off += 1
            break
        if ln & 0xC0:
            off += 2
            break
        off += 1
        labels.append(data[off:off + ln].decode("ascii", "ignore"))
        off += ln
    return ".".join(labels).lower(), off


def load_blocked_domains(lists_dir: str) -> set[str]:
    domains: set[str] = set()
    for path in glob.glob(os.path.join(lists_dir, "*.csv")):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                rows = list(csv.reader(fh))
        except Exception:  # noqa: BLE001
            continue
        if not rows:
            continue
        header = [h.strip() for h in rows[0]]
        idx = {name: i for i, name in enumerate(header)}
        if "categoria" not in idx:
            continue
        for row in rows[1:]:
            if len(row) <= idx["categoria"]:
                continue
            cat = (row[idx["categoria"]] or "").strip().lower()
            if cat not in ("dominio", "url"):
                continue
            for col in ("handle", "url"):
                if col not in idx:
                    continue
                if len(row) <= idx[col]:
                    continue
                val = (row[idx[col]] or "").strip()
                if not val:
                    continue
                host = val
                if "://" in val:
                    try:
                        host = val.split("://")[1].split("/")[0].split(":")[0]
                    except Exception:  # noqa: BLE001
                        host = val
                host = host.strip().strip(".").lower()
                if host and not host.startswith("@") and "." in host:
                    domains.add(host)
    return domains


def is_blocked(qname: str, domains: set[str]) -> bool:
    if not qname:
        return False
    for d in domains:
        if qname == d or qname.endswith("." + d):
            return True
    return False


def upstream_server() -> str:
    try:
        with open("/etc/resolv.conf") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1]
    except Exception:  # noqa: BLE001
        pass
    return "8.8.8.8"


def nxdomain_response(query: bytes) -> bytes:
    if len(query) < 12:
        return b""
    tid = query[:2]
    flags = struct.unpack(">H", query[2:4])[0]
    # copia qdcount e seção de pergunta
    qd = query[4:6]
    question = query[12:]
    resp_flags = 0x8183  # resposta + recursion available + NXDOMAIN(3)
    header = tid + struct.pack(">H", resp_flags) + qd + b"\x00\x00\x00\x00\x00\x00"
    return header + question


def handle_query(data: bytes, domains: set[str], upstream: str) -> bytes | None:
    if len(data) < 12:
        return None
    qname, _ = parse_qname(data, 12)
    if is_blocked(qname, domains):
        return nxdomain_response(data)
    fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fwd.settimeout(3)
    try:
        fwd.sendto(data, (upstream, 53))
        resp, _ = fwd.recvfrom(4096)
        return resp
    except Exception:  # noqa: BLE001
        return None
    finally:
        fwd.close()


def tcp_worker(conn: socket.socket, domains_cb, upstream: str) -> None:
    try:
        conn.settimeout(5)
        hdr = conn.recv(2)
        if len(hdr) < 2:
            return
        (length,) = struct.unpack(">H", hdr)
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                return
            data += chunk
        resp = handle_query(data, domains_cb(), upstream)
        if resp:
            conn.sendall(struct.pack(">H", len(resp)) + resp)
    except Exception:  # noqa: BLE001
        pass
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="gltd-kid-dns")
    parser.add_argument("--lists", default="/var/PROGRAMAS/gltd_kid_control/lists")
    parser.add_argument("--port", type=int, default=5353)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()

    upstream = upstream_server()
    print(f"DNS GLTD em {args.bind}:{args.port} -> upstream {upstream}")

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind((args.bind, args.port))
    udp.settimeout(0.5)

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind((args.bind, args.port))
    tcp.listen(16)

    domains: set[str] = set()
    last_load = 0.0

    def current_domains() -> set[str]:
        return domains

    def tcp_accept() -> None:
        while True:
            try:
                conn, _ = tcp.accept()
                threading.Thread(target=tcp_worker, args=(conn, current_domains, upstream), daemon=True).start()
            except Exception:  # noqa: BLE001
                return

    threading.Thread(target=tcp_accept, daemon=True).start()

    while True:
        if time.time() - last_load > 15:
            domains = load_blocked_domains(args.lists)
            last_load = time.time()
        try:
            data, addr = udp.recvfrom(4096)
        except socket.timeout:
            continue
        if len(data) < 12:
            continue
        resp = handle_query(data, domains, upstream)
        if resp:
            udp.sendto(resp, addr)


if __name__ == "__main__":
    raise SystemExit(main())

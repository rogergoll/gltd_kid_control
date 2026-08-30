"""Servidor DNS local do client (127.0.0.1:5300).

Bloqueia domínios da lista e encaminha o restante ao DNS padrão da máquina.
Roda como parte do daemon (root). Sem dependência do servidor para resolver.
"""
from __future__ import annotations

import socket
import struct
import threading


def _parse_qname(data: bytes, off: int) -> tuple[str, int]:
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


def _is_blocked(qname: str, domains: set[str]) -> bool:
    if not qname:
        return False
    for d in domains:
        if qname == d or qname.endswith("." + d):
            return True
    return False


def _nxdomain(query: bytes) -> bytes:
    if len(query) < 12:
        return b""
    header = query[:2] + struct.pack(">H", 0x8183) + query[4:6] + b"\x00\x00\x00\x00\x00\x00"
    return header + query[12:]


def _upstream() -> str:
    try:
        with open("/etc/resolv.conf") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1]
    except Exception:  # noqa: BLE001
        pass
    return "8.8.8.8"


class LocalDNS:
    """Servidor DNS (UDP + TCP) com conjunto de domínios bloqueados atualizável."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5300) -> None:
        self.host = host
        self.port = port
        self.upstream = _upstream()
        self._domains: set[str] = set()
        self._lock = threading.Lock()
        self._running = False

    def update_domains(self, domains: set[str]) -> None:
        with self._lock:
            self._domains = set(domains)

    def _domains_snapshot(self) -> set[str]:
        with self._lock:
            return set(self._domains)

    def _handle(self, data: bytes) -> bytes | None:
        if len(data) < 12:
            return None
        qname, _ = _parse_qname(data, 12)
        if _is_blocked(qname, self._domains_snapshot()):
            return _nxdomain(data)
        fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        fwd.settimeout(3)
        try:
            fwd.sendto(data, (self.upstream, 53))
            resp, _ = fwd.recvfrom(4096)
            return resp
        except Exception:  # noqa: BLE001
            return None
        finally:
            fwd.close()

    def _udp_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(0.5)
        while self._running:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            resp = self._handle(data)
            if resp:
                sock.sendto(resp, addr)

    def _tcp_worker(self, conn: socket.socket) -> None:
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
            resp = self._handle(data)
            if resp:
                conn.sendall(struct.pack(">H", len(resp)) + resp)
        except Exception:  # noqa: BLE001
            pass
        finally:
            conn.close()

    def _tcp_accept(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(16)
        sock.settimeout(0.5)
        while self._running:
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._tcp_worker, args=(conn,), daemon=True).start()

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._udp_loop, daemon=True).start()
        threading.Thread(target=self._tcp_accept, daemon=True).start()

    def stop(self) -> None:
        self._running = False

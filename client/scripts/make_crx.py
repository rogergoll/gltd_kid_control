#!/usr/bin/env python3
"""Empacota a extensão em CRX3 e imprime o extension id + chave pública.

Uso: make_crx.py <diretório_da_extensão> <saída.crx> [chave_privada.pem]
"""
from __future__ import annotations

import base64
import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import zipfile


def varint(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            out += bytes([b])
            return out


def field_bytes(num: int, payload: bytes) -> bytes:
    return varint((num << 3) | 2) + varint(len(payload)) + payload


def main() -> int:
    ext_dir = sys.argv[1]
    out_path = sys.argv[2]
    key_path = sys.argv[3] if len(sys.argv) > 3 else None

    tmp = tempfile.mkdtemp()
    if key_path is None:
        key_path = os.path.join(tmp, "key.pem")
        subprocess.check_call(
            ["openssl", "genpkey", "-algorithm", "RSA",
             "-pkeyopt", "rsa_keygen_bits:2048", "-out", key_path])

    pub_der = subprocess.check_output(
        ["openssl", "rsa", "-pubout", "-in", key_path, "-outform", "DER"])

    h = hashlib.sha256(pub_der).digest()
    crx_id = h[:16]
    id_letters = "".join(chr(ord("a") + int(c, 16)) for c in h[:16].hex())

    zip_path = os.path.join(tmp, "ext.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(ext_dir):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, ext_dir)
                if f.endswith((".crx", ".pem", ".key")):
                    continue
                z.write(full, arc)

    with open(zip_path, "rb") as fh:
        zip_bytes = fh.read()

    sig_path = os.path.join(tmp, "sig.bin")
    subprocess.check_call(
        ["openssl", "dgst", "-sha256", "-sign", key_path, "-out", sig_path, zip_path])
    with open(sig_path, "rb") as fh:
        sig = fh.read()

    proof = field_bytes(1, pub_der) + field_bytes(2, sig)
    sha256_with_rsa = field_bytes(2, proof)
    signed_data = field_bytes(1, crx_id)
    signed_header_data = field_bytes(10000, signed_data)
    header = sha256_with_rsa + signed_header_data

    crx = b"Cr24" + struct.pack("<II", 3, len(header)) + header + zip_bytes
    with open(out_path, "wb") as fh:
        fh.write(crx)

    print(f"extension_id: {id_letters}")
    print(f"public_key:   {base64.b64encode(pub_der).decode()}")
    print(f"crx:          {out_path}")
    print(f"private_key:  {key_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

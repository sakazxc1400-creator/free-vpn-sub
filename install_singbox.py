#!/usr/bin/env python3
"""Install the tested sing-box release with pinned archive SHA-256 hashes."""

import hashlib
import io
import os
import platform
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.14.4"
ARCHIVES = {
    "Windows": ("windows-amd64.zip", "99185d75d314a07dbba4a130c8ad986cbeb629a07927975636b341ca61f991df"),
    "Linux": ("linux-amd64.tar.gz", "699a1b510aa4396b2176d32d1181920399ebf1e267835da6f3b598d0f7c24968"),
}
ROOT = Path(__file__).resolve().parent


def main():
    system = platform.system()
    if system not in ARCHIVES or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Automatic installation supports Windows/Linux x86-64. Install sing-box manually on other platforms.")
    suffix, expected = ARCHIVES[system]
    archive = f"sing-box-{VERSION}-{suffix}"
    url = f"https://github.com/SagerNet/sing-box/releases/download/v{VERSION}/{archive}"
    print(f"Downloading {archive}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit("Archive checksum mismatch; the existing binary was not modified.")
    name = "sing-box.exe" if system == "Windows" else "sing-box"
    member = f"sing-box-{VERSION}-{suffix.split('.')[0]}/{name}"
    if system == "Windows":
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            binary = bundle.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
            source = bundle.extractfile(member)
            if source is None:
                raise SystemExit("The archive does not contain the expected executable.")
            with source:
                binary = source.read()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=ROOT, delete=False) as output:
            temporary = Path(output.name)
            output.write(binary)
        temporary.chmod(0o755)
        os.replace(temporary, ROOT / name)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Installed sing-box {VERSION} at {ROOT / name}")


if __name__ == "__main__":
    main()

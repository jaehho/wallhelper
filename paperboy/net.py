"""Fetching bytes off the internet, with the two manners that matter: a User-
Agent that does not get us blocked, and a download that never leaves a
half-written file where a photograph should be."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

# Plain token on purpose: wallhaven's WAF 403s any User-Agent carrying a
# parenthesized URL, which silently kills that source.
UA = "paperboy/1.0"


def fetch_url(url: str, timeout: int = 30,
              headers: dict | None = None) -> bytes:
    sent = {"User-Agent": UA}
    if isinstance(headers, dict):
        sent.update({str(k): str(v) for k, v in headers.items()})
    req = urllib.request.Request(url, headers=sent)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def download(url: str, dest: Path) -> bool:
    """Via a tempfile, so a truncated transfer never lands in the folder."""
    tmp = dest.with_name(f".fetch-{os.getpid()}")
    try:
        data = fetch_url(url, timeout=120)
        if not data:
            return False
        tmp.write_bytes(data)
        # Trust the bytes, not the extension.
        if data[:2] not in (b"\xff\xd8", b"\x89P", b"RI", b"BM"):
            return False
        tmp.chmod(0o644)           # mktemp-style 0600 would be odd here
        tmp.replace(dest)
        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    finally:
        tmp.unlink(missing_ok=True)

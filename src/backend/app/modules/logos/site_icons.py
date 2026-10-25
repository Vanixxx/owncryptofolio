"""Website icons of exchanges the icon set lacks, fetched by each installation itself
(Vanixxx, 2026-10-23): the project ships no third-party logo; like a browser showing a
site's favicon, the app asks the exchange's own website once and keeps the icon in the data
folder (`<data_dir>/site-icons/`).

* The website comes from ccxt (`urls.www`), never from user input: only known exchanges.
* From the start page the `<link rel="apple-touch-icon">` or the largest `rel="icon"`, else
  `/favicon.ico`. At most 300 KB, only real images (PNG, JPEG, GIF, WebP, ICO, SVG).
* No icon to be had (site down, Cloudflare): a marker for a week, then one more try; the
  interface shows the first letter meanwhile.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from app.core.config import get_settings

log = logging.getLogger(__name__)

MAX_BYTES = 300_000
RETRY_AFTER = 7 * 86_400
TIMEOUT = 8
HEADERS = {"User-Agent": "Mozilla/5.0 (owncryptofolio; site icon)", "Accept": "*/*"}
KINDS = {  # magic bytes → (extension, media type)
    b"\x89PNG": ("png", "image/png"),
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"GIF8": ("gif", "image/gif"),
    b"\x00\x00\x01\x00": ("ico", "image/x-icon"),
}
MEDIA = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "ico": "image/x-icon",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}
LINK = re.compile(r"<link\b[^>]*>", re.I)


def folder() -> Path:
    return get_settings().data_dir / "site-icons"


def website(provider: str) -> str | None:
    import ccxt

    if provider not in ccxt.exchanges:
        return None
    www = getattr(ccxt, provider)().urls.get("www")
    if isinstance(www, list):
        www = www[0] if www else None
    return www if isinstance(www, str) and www.startswith("http") else None


def kind_of(data: bytes) -> tuple[str, str] | None:
    for magic, found in KINDS.items():
        if data.startswith(magic):
            return found
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    head = data[:500].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "svg", "image/svg+xml"
    return None


def _public(url: str) -> None:
    """Only http(s) to a public address: the icon links come from a third-party page and
    must not reach the home network or local files (review 2026-10-24)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("not a web address")
    for info in socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("not a public address")


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _public(newurl)  # a redirect is checked like the first address
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# http(s) only: no file://, no ftp://
_OPENER = urllib.request.OpenerDirector()
for _handler in (
    urllib.request.HTTPHandler(),
    urllib.request.HTTPSHandler(),
    _Redirect(),
    urllib.request.HTTPErrorProcessor(),
):
    _OPENER.add_handler(_handler)


def _get(url: str) -> bytes:
    _public(url)
    req = urllib.request.Request(url, headers=HEADERS)
    with _OPENER.open(req, timeout=TIMEOUT) as resp:
        return resp.read(MAX_BYTES + 1)


def candidates(page_url: str, html: str) -> list[str]:
    """Icon URLs from the start page, best first; the root favicon last."""
    found: list[tuple[int, str]] = []
    for tag in LINK.findall(html):
        rel = (re.search(r'rel=["\']([^"\']+)', tag, re.I) or [None, ""])[1].lower()
        href = (re.search(r'href=["\']([^"\']+)', tag, re.I) or [None, ""])[1]
        if not href or "icon" not in rel or "mask" in rel:
            continue
        size = max((int(n) for n in re.findall(r"(\d+)x\d+", tag)), default=0)
        score = size + (1000 if "apple-touch" in rel else 0)
        found.append((score, urllib.parse.urljoin(page_url, href)))
    urls = [u for _, u in sorted(found, key=lambda x: -x[0])]
    urls.append(urllib.parse.urljoin(page_url, "/favicon.ico"))
    return list(dict.fromkeys(urls))


def fetch(provider: str) -> Path | None:
    """The stored icon, fetched now if it is not there yet; None when there is none."""
    base = folder()
    for p in base.glob(f"{provider}.*"):
        if p.suffix != ".none":
            return p
    marker = base / f"{provider}.none"
    if marker.exists() and time.time() - marker.stat().st_mtime < RETRY_AFTER:
        return None
    site = website(provider)
    if not site:
        return None
    base.mkdir(parents=True, exist_ok=True)
    try:
        html = _get(site).decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        html = ""
    for url in candidates(site, html):
        try:
            data = _get(url)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            continue
        if len(data) > MAX_BYTES:
            continue
        found = kind_of(data)
        if found:
            path = base / f"{provider}.{found[0]}"
            path.write_bytes(data)
            marker.unlink(missing_ok=True)
            log.info("Site icon of %s stored (%s, %d bytes)", provider, found[0], len(data))
            return path
    marker.touch()
    log.info("No site icon for %s", provider)
    return None


def media_type(path: Path) -> str:
    return MEDIA.get(path.suffix.lstrip("."), "application/octet-stream")

"""Own logos: checked by their first bytes, not by the name the browser sends."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.logos.models import CustomLogo

KINDS = ("wallet", "source", "coin")
MAX_BYTES = 512 * 1024


def sniff(data: bytes) -> str | None:
    """The real type of an image, or None: PNG, JPEG, WebP, SVG."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    # SVG from drawing programs often starts with a byte order mark, an XML declaration,
    # a comment or a doctype before <svg>: text that opens with "<" and has <svg early on
    head = data[:4096].removeprefix(b"\xef\xbb\xbf").lstrip().lower()
    if head.startswith(b"<") and b"<svg" in head:
        return "image/svg+xml"
    return None


def key_of(kind: str, key: str) -> str:
    if kind not in KINDS:
        raise AppError("logos.invalid_kind", 400)
    key = key.strip()
    if kind == "coin":
        key = key.upper()
    if not key or len(key) > 60:
        raise AppError("logos.invalid_key", 400)
    return key


def store(session: Session, kind: str, key: str, data: bytes) -> None:
    key = key_of(kind, key)
    if len(data) > MAX_BYTES:
        raise AppError("logos.too_large", 400, max_kb=MAX_BYTES // 1024)
    mime = sniff(data)
    if mime is None:
        raise AppError("logos.not_an_image", 400)
    session.merge(CustomLogo(kind=kind, key=key, mime=mime, data=data))
    session.commit()


def remove(session: Session, kind: str, key: str) -> None:
    row = session.get(CustomLogo, (kind, key_of(kind, key)))
    if row is not None:
        session.delete(row)
        session.commit()


def get(session: Session, kind: str, key: str) -> CustomLogo:
    row = session.get(CustomLogo, (kind, key_of(kind, key)))
    if row is None:
        raise AppError("logos.not_found", 404)
    return row


def listing(session: Session) -> list[dict]:
    """Which logos exist, with a version for the browser cache."""
    return [
        {"kind": k, "key": key, "v": int(at.timestamp())}
        for k, key, at in session.execute(
            select(CustomLogo.kind, CustomLogo.key, CustomLogo.updated_at)
        )
    ]

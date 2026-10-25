"""Stateless sessions: a Fernet token that carries its own expiry (ADR 0023) and a stamp of
the password it was issued under: a new password (web or command line) ends every older
session (review 2026-10-24)."""

import hashlib

from cryptography.fernet import Fernet, InvalidToken

COOKIE_NAME = "ocf_session"
TTL_SECONDS = 30 * 24 * 3600
_PAYLOAD = b"ocf-session-v2:"


def stamp(password_hash: str | None) -> str:
    """Short and one-way: the token never carries the hash itself."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def issue(session_key: str, password_stamp: str) -> str:
    return Fernet(session_key).encrypt(_PAYLOAD + password_stamp.encode()).decode()


def is_valid(session_key: str, token: str | None, password_stamp: str | None) -> bool:
    if not token or not password_stamp:
        return False
    try:
        body = Fernet(session_key).decrypt(token.encode(), ttl=TTL_SECONDS)
    except InvalidToken:
        return False
    return body == _PAYLOAD + password_stamp.encode()

"""Blockchain services whose free API key several networks share (ADR 0035)."""

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.keys import get_keys
from app.modules.sources.models import ServiceKey

SERVICES = {
    "etherscan": {
        "name": "Etherscan",
        "url": "https://etherscan.io/myapikey",
        # The free key covers Sonic but NOT BNB Smart Chain (measured 2026-08-27).
    },
    "cronos": {"name": "Cronos Explorer", "url": "https://explorer.cronos.org/"},
    # BscScan's successor that BNB Chain points to; free tier (BSCTrace / MegaNode).
    "nodereal": {"name": "NodeReal MegaNode", "url": "https://dashboard.nodereal.io/"},
    # optional: these work without a key, one only raises the limits (2026-10-23)
    "trongrid": {"name": "TronGrid", "url": "https://www.trongrid.io/register"},
    "toncenter": {"name": "toncenter", "url": "https://t.me/tonapibot"},
}


def _fernet() -> Fernet:
    return Fernet(get_keys().credentials_key)


def overview(session: Session) -> list[dict]:
    from app.modules.plugins.registry import registry

    stored = set(session.scalars(select(ServiceKey.service)))
    used: dict[str, list[str]] = {}
    for p in registry().plugins.values():
        chain = p.manifest.chain
        if chain and chain.service:
            used.setdefault(chain.service, []).append(p.manifest.source.provider_name)
    return [
        {"service": k, **v, "stored": k in stored, "used_by": sorted(used.get(k, []))}
        for k, v in SERVICES.items()
    ]


def store(session: Session, service: str, key: str) -> None:
    if service not in SERVICES:
        raise AppError("services.unknown", 404)
    key = key.strip()
    if not key:
        raise AppError("services.key_required", 400)
    row = session.get(ServiceKey, service)
    token = _fernet().encrypt(key.encode()).decode()
    if row is None:
        session.add(ServiceKey(service=service, ciphertext=token))
    else:
        row.ciphertext = token
    session.commit()


def remove(session: Session, service: str) -> None:
    row = session.get(ServiceKey, service)
    if row is not None:
        session.delete(row)
        session.commit()


def read(session: Session, service: str) -> str | None:
    row = session.get(ServiceKey, service)
    if row is None:
        return None
    try:
        return _fernet().decrypt(row.ciphertext.encode()).decode()
    except InvalidToken as exc:
        # the credentials key changed: named like the exchange keys (review 2026-10-24)
        raise AppError("sources.credentials_unreadable", 409) from exc

"""Credentials encrypted at rest with their own key (one key, one purpose — ADR 0023).

Nothing here ever returns a value it does not have to: `field_names()` lists
which fields exist, never their content.
"""

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.keys import get_keys
from app.modules.sources.models import SourceCredential


def _fernet() -> Fernet:
    return Fernet(get_keys().credentials_key)


def store(session: Session, source_id: int, values: dict[str, str]) -> None:
    session.execute(delete(SourceCredential).where(SourceCredential.source_id == source_id))
    f = _fernet()
    for field, value in values.items():
        session.add(
            SourceCredential(
                source_id=source_id, field=field, ciphertext=f.encrypt(value.encode()).decode()
            )
        )


def read(session: Session, source_id: int) -> dict[str, str]:
    rows = session.scalars(
        select(SourceCredential).where(SourceCredential.source_id == source_id)
    ).all()
    f = _fernet()
    try:
        return {r.field: f.decrypt(r.ciphertext.encode()).decode() for r in rows}
    except InvalidToken as exc:
        # The credentials key changed: the stored secrets are lost, not the data.
        raise AppError("sources.credentials_unreadable", 409) from exc


def field_names(session: Session, source_id: int) -> list[str]:
    return sorted(
        session.scalars(
            select(SourceCredential.field).where(SourceCredential.source_id == source_id)
        )
    )


def remove(session: Session, source_id: int) -> None:
    session.execute(delete(SourceCredential).where(SourceCredential.source_id == source_id))


def scrub(message: str, secrets: dict[str, str]) -> str:
    """Removes every stored value from an error text before it is shown or logged.
    Libraries sometimes echo request parameters; never trust them not to."""
    for value in secrets.values():
        if value and len(value) >= 4:
            message = message.replace(value, "***")
    return message

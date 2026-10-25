from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import AuthCredential
from app.modules.auth.passwords import MIN_LENGTH, hash_password, verify_password


def is_set_up(session: Session) -> bool:
    return session.scalar(select(AuthCredential.id)) is not None


def check_policy(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise AppError("auth.password_too_short", 400, min=MIN_LENGTH)


def set_password(session: Session, password: str) -> None:
    check_policy(password)
    row = session.get(AuthCredential, 1)
    if row is None:
        session.add(AuthCredential(id=1, password_hash=hash_password(password)))
    else:
        row.password_hash = hash_password(password)
    session.commit()


def password_stamp(session: Session) -> str | None:
    """The stamp sessions carry (see `sessions.stamp`); None before setup."""
    from app.modules.auth import sessions

    row = session.get(AuthCredential, 1)
    return None if row is None else sessions.stamp(row.password_hash)


def password_matches(session: Session, password: str) -> bool:
    row = session.get(AuthCredential, 1)
    return row is not None and verify_password(password, row.password_hash)

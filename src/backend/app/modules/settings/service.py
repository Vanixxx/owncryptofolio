from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import logs
from app.core.errors import AppError
from app.modules.settings.models import Setting
from app.modules.settings.registry import SETTINGS


def all_settings(session: Session) -> dict[str, Any]:
    stored = {s.key: s.value for s in session.scalars(select(Setting))}
    return {key: stored.get(key, d.default) for key, d in SETTINGS.items()}


def update(session: Session, changes: dict[str, Any]) -> dict[str, Any]:
    for key, value in changes.items():
        definition = SETTINGS.get(key)
        if definition is None:
            raise AppError("settings.unknown_key", 400, key=key)
        if not definition.valid(value):
            raise AppError("settings.invalid_value", 400, key=key)
    for key, value in changes.items():
        row = session.get(Setting, key)
        if value == SETTINGS[key].default:
            if row is not None:
                session.delete(row)
        elif row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    session.commit()
    if "system.log_level" in changes:
        logs.set_level(changes["system.log_level"])
    return all_settings(session)


def schema() -> dict[str, dict[str, Any]]:
    return {
        key: {"default": d.default, "choices": list(d.choices) if d.choices else None}
        for key, d in SETTINGS.items()
    }

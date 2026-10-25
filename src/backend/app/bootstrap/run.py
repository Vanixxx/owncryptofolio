"""The first-start chain (ADR 0030). Every step checks first, so every start is safe."""

import logging
import secrets
from dataclasses import dataclass

from app.bootstrap.database import ensure_database
from app.bootstrap.keys import Keys, load_or_create_keys
from app.bootstrap.migrate import upgrade
from app.core.config import Settings
from app.core.keys import set_keys

log = logging.getLogger(__name__)


@dataclass
class BootState:
    keys: Keys
    database_created: bool
    # only until a password is set, and only when the server already had keys (a lost
    # database, a restore): a brand-new install has nothing to guard (Vanixxx, 2026-10-22)
    setup_code: str | None


def new_setup_code() -> str:
    n = secrets.randbelow(1_000_000)
    return f"{n // 1000:03d}-{n % 1000:03d}"


def run_bootstrap(settings: Settings, wait_seconds: float | None = None) -> BootState:
    created = ensure_database(
        settings.database_url, settings.db_wait_seconds if wait_seconds is None else wait_seconds
    )
    upgrade(settings.database_url)
    keys = load_or_create_keys(
        settings.data_dir,
        {n: getattr(settings, n) for n in ("credentials_key", "session_key", "backup_key")},
    )
    set_keys(keys)
    code = None if keys.fresh else new_setup_code()
    return BootState(keys=keys, database_created=created, setup_code=code)

"""First-start step 4: encryption keys. One key, one purpose (ADR 0023, ADR 0030).

Environment values win; otherwise keys are generated once and stored in
<data_dir>/secrets/keys.json with mode 600. Keys never go into the database, so a
database dump cannot decrypt itself.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet

log = logging.getLogger(__name__)

KEY_NAMES = ("credentials_key", "session_key", "backup_key")


@dataclass(frozen=True)
class Keys:
    credentials_key: str
    session_key: str
    backup_key: str
    sources: dict[str, str]  # key name -> "env" | "file"
    # every key was made just now: a brand-new install, nothing on this server to guard yet
    fresh: bool = False


def load_or_create_keys(data_dir: Path, overrides: dict[str, str | None]) -> Keys:
    secrets_dir = data_dir / "secrets"
    path = secrets_dir / "keys.json"
    stored: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}

    missing = [n for n in KEY_NAMES if not overrides.get(n) and n not in stored]
    fresh = len(missing) == len(KEY_NAMES)
    if missing:
        for name in missing:
            stored[name] = Fernet.generate_key().decode()
        _write_private(secrets_dir, path, stored)
        log.warning("Generated keys %s in %s", ", ".join(missing), path)

    values, sources = {}, {}
    for name in KEY_NAMES:
        if overrides.get(name):
            values[name], sources[name] = overrides[name], "env"
        else:
            values[name], sources[name] = stored[name], "file"
        Fernet(values[name])  # fail loudly on a malformed key
    return Keys(**values, sources=sources, fresh=fresh)


def save_keys(data_dir: Path, keys: "Keys") -> None:
    """Write the keys after a restore (keys from the environment stay where they are)."""
    secrets_dir = data_dir / "secrets"
    path = secrets_dir / "keys.json"
    stored: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    for name in KEY_NAMES:
        if keys.sources.get(name) != "env":
            stored[name] = getattr(keys, name)
    _write_private(secrets_dir, path, stored)


def _write_private(secrets_dir: Path, path: Path, data: dict[str, str]) -> None:
    secrets_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(secrets_dir, 0o700)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)

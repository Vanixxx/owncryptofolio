import secrets
import stat

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.bootstrap.database import BootstrapError, ensure_database
from app.bootstrap.keys import load_or_create_keys
from app.bootstrap.migrate import upgrade
from tests.conftest import TEST_DATABASE_URL


def _admin_conninfo() -> str:
    url = make_url(TEST_DATABASE_URL).set(drivername="postgresql", database="postgres")
    return url.render_as_string(hide_password=False)


def _exists(name: str) -> bool:
    with psycopg.connect(_admin_conninfo()) as conn:
        return (
            conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
            is not None
        )


@pytest.fixture
def missing_db():
    name = f"ocf_bootstrap_{secrets.token_hex(4)}"
    url = make_url(TEST_DATABASE_URL).set(database=name).render_as_string(hide_password=False)
    yield name, url
    with psycopg.connect(_admin_conninfo(), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def test_first_start_creates_and_migrates_missing_database(missing_db):
    name, url = missing_db
    assert not _exists(name)

    assert ensure_database(url, wait_seconds=5) is True
    upgrade(url)
    assert _exists(name)

    # second start: nothing to do
    assert ensure_database(url, wait_seconds=5) is False
    upgrade(url)
    with psycopg.connect(url.replace("+psycopg", "")) as conn:
        tables = {
            r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        }
    assert {"alembic_version", "auth_credential", "setting"} <= tables


def test_unreachable_server_fails_loudly_after_waiting():
    url = make_url(TEST_DATABASE_URL).set(port=1).render_as_string(hide_password=False)
    with pytest.raises(BootstrapError, match="not reachable"):
        ensure_database(url, wait_seconds=0.5)


def test_keys_are_generated_once_and_kept_private(tmp_path):
    first = load_or_create_keys(tmp_path, {})
    path = tmp_path / "secrets" / "keys.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert set(first.sources.values()) == {"file"}

    second = load_or_create_keys(tmp_path, {})
    assert second.session_key == first.session_key
    assert len({first.credentials_key, first.session_key, first.backup_key}) == 3
    # only the very first start is "fresh": then no setup code is needed
    assert first.fresh and not second.fresh


def test_environment_key_overrides_file(tmp_path):
    from cryptography.fernet import Fernet

    env_key = Fernet.generate_key().decode()
    keys = load_or_create_keys(tmp_path, {"backup_key": env_key})
    assert keys.backup_key == env_key
    assert keys.sources["backup_key"] == "env"


def test_malformed_key_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        load_or_create_keys(tmp_path, {"session_key": "not-a-key"})

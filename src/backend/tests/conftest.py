"""Tests run against a real PostgreSQL database (TEST_DATABASE_URL), never a mock:
whether the connection and the first-start chain work is exactly what is tested."""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

_env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or _env.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is not set (src/backend/.env or environment)")

PASSWORD = "correct horse battery"


def _clear_caches() -> None:
    from app.core import config, db

    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db._session_factory.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _fresh_schema():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    engine.dispose()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "no-frontend"))
    monkeypatch.setenv("DB_WAIT_SECONDS", "3")
    monkeypatch.setenv("BACKGROUND_WORKERS", "false")
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    for key in ("CREDENTIALS_KEY", "SESSION_KEY", "BACKUP_KEY"):
        monkeypatch.delenv(key, raising=False)
    _clear_caches()
    yield tmp_path
    from app.core import db

    db.get_engine().dispose()
    _clear_caches()


def _truncate() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        tables = (
            conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        if tables:
            conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE"))
    engine.dispose()


@pytest.fixture
def client(env):
    from app.main import create_app

    app = create_app()
    app.state.failure_delay = 0
    with TestClient(app) as c:
        _truncate()
        app.state.setup_done = False
        yield c


@pytest.fixture
def authed(client):
    code = client.app.state.boot.setup_code
    r = client.post("/api/auth/setup", json={"code": code, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def db(client):
    """A session on the test database, for service-level tests."""
    from app.core.db import _session_factory

    with _session_factory()() as session:
        yield session


def make_source(db, provider="bitget", label="Bitget", address=None):
    from app.modules.sources.service import create

    return create(db, provider, label, address)

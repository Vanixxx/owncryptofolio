import pytest

from app.core import config


def test_missing_database_url_stops_loudly(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        config.Settings, "model_config", {**config.Settings.model_config, "env_file": None}
    )
    config.get_settings.cache_clear()
    with pytest.raises(config.ConfigError, match="DATABASE_URL"):
        config.get_settings()
    config.get_settings.cache_clear()


def test_empty_database_url_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    config.get_settings.cache_clear()
    with pytest.raises(config.ConfigError):
        config.get_settings()
    config.get_settings.cache_clear()


def test_database_from_its_parts(monkeypatch):
    """The Unraid template asks host, port, database, user and password one by one
    (Vanixxx, 2026-10-12); a password with special characters must survive."""
    monkeypatch.setenv("DATABASE_URL", "")
    for k, v in {
        "DB_HOST": "192.168.1.20",
        "DB_PORT": "5434",
        "DB_NAME": "owncryptofolio",
        "DB_USER": "postgres",
        "DB_PASSWORD": "p@ss:/word",
    }.items():
        monkeypatch.setenv(k, v)
    config.get_settings.cache_clear()
    url = config.get_settings().database_url
    config.get_settings.cache_clear()
    assert url == "postgresql+psycopg://postgres:p%40ss%3A%2Fword@192.168.1.20:5434/owncryptofolio"
    from sqlalchemy.engine import make_url

    assert make_url(url).password == "p@ss:/word"

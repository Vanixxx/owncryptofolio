"""Without a database the app starts anyway and says so; it boots once the database is
there (power cut, the database container comes up later — Vanixxx, 2026-10-15)."""

from fastapi.testclient import TestClient


def test_no_database_answers_503_then_boots_when_it_is_back(env, monkeypatch):
    import app.main as main
    from tests.conftest import TEST_DATABASE_URL, _clear_caches

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@127.0.0.1:9/nodb")
    monkeypatch.setattr(main, "BOOT_FIRST_WAIT", 0.2)
    monkeypatch.setattr(main, "BOOT_RETRY_SECONDS", 0.2)
    _clear_caches()
    app = main.create_app()
    with TestClient(app) as c:
        r = c.get("/api/auth/status")
        assert r.status_code == 503 and r.json()["error"]["code"] == "db.unavailable"
        # the database "comes back"
        monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
        _clear_caches()
        import time

        for _ in range(100):
            if app.state.ready:
                break
            time.sleep(0.1)
        assert app.state.ready
        assert c.get("/api/auth/status").status_code == 200

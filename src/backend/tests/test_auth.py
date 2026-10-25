from tests.conftest import PASSWORD


def test_everything_is_locked_until_setup(client):
    assert client.get("/api/auth/status").json() == {
        "setup_required": True,
        "code_required": False,
        "authenticated": False,
    }
    r = client.get("/api/settings")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.setup_required"
    assert client.get("/openapi.json").status_code == 401


def test_health_stays_open(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "connected"}


def test_brand_new_install_needs_no_code(client):
    # every key was made at this start: nothing on the server to guard yet (Vanixxx, 2026-10-22)
    assert client.app.state.boot.setup_code is None
    r = client.post("/api/auth/setup", json={"password": PASSWORD})
    assert r.status_code == 200


def test_wrong_setup_code_is_refused(client):
    # the server had keys before (a lost database, a restore): the code from the log counts
    client.app.state.boot.setup_code = "123-456"
    assert client.get("/api/auth/status").json()["code_required"] is True
    r = client.post("/api/auth/setup/verify", json={"code": "000-000x"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "auth.setup_code_invalid"
    r = client.post("/api/auth/setup", json={"code": "nope", "password": PASSWORD})
    assert r.status_code == 400


def test_setup_with_code_sets_password_logs_in_and_returns_backup_key(client):
    code = client.app.state.boot.setup_code = "123-456"
    assert client.post("/api/auth/setup/verify", json={"code": code}).status_code == 204
    r = client.post("/api/auth/setup", json={"code": code, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["backup_key"] == client.app.state.boot.keys.backup_key
    assert client.get("/api/auth/status").json() == {
        "setup_required": False,
        "code_required": False,
        "authenticated": True,
    }
    assert client.get("/api/settings").status_code == 200


def test_setup_runs_only_once(authed):
    code = authed.app.state.boot.setup_code
    r = authed.post("/api/auth/setup", json={"code": code, "password": "another password"})
    assert r.status_code == 409


def test_short_password_is_refused(client):
    code = client.app.state.boot.setup_code
    r = client.post("/api/auth/setup", json={"code": code, "password": "short"})
    assert r.status_code == 400
    assert r.json()["error"] == {"code": "auth.password_too_short", "params": {"min": 10}}
    assert client.get("/api/auth/status").json()["setup_required"] is True


def test_login_logout_cycle(authed):
    authed.post("/api/auth/logout")
    authed.cookies.clear()
    r = authed.get("/api/settings")
    assert r.status_code == 401 and r.json()["error"]["code"] == "auth.required"

    r = authed.post("/api/auth/login", json={"password": "wrong password"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "auth.invalid_password"

    assert authed.post("/api/auth/login", json={"password": PASSWORD}).status_code == 204
    assert authed.get("/api/settings").status_code == 200


def test_forged_cookie_is_refused(authed):
    authed.cookies.clear()
    authed.cookies.set("ocf_session", "gAAAAAforged")
    assert authed.get("/api/settings").status_code == 401


def test_password_change(authed):
    r = authed.post("/api/auth/password", json={"current": "wrong", "new": "new password 123"})
    assert r.status_code == 400
    assert (
        authed.post(
            "/api/auth/password", json={"current": PASSWORD, "new": "new password 123"}
        ).status_code
        == 204
    )
    authed.cookies.clear()
    assert authed.post("/api/auth/login", json={"password": "new password 123"}).status_code == 204


def test_cookie_is_secure_behind_tls_proxy(client):
    code = client.app.state.boot.setup_code
    r = client.post(
        "/api/auth/setup",
        json={"code": code, "password": PASSWORD},
        headers={"x-forwarded-proto": "https"},
    )
    assert "secure" in r.headers["set-cookie"].lower()


def test_setup_survives_restart(env):
    """A restarted app must know it is already set up (state comes from the database)."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    app.state.failure_delay = 0
    with TestClient(app) as c:
        if not app.state.setup_done:
            c.post(
                "/api/auth/setup", json={"code": app.state.boot.setup_code, "password": PASSWORD}
            )
    app2 = create_app()
    with TestClient(app2):
        assert app2.state.setup_done is True


def test_forgotten_password_is_reset_on_the_command_line(authed):
    from app.modules.auth.__main__ import main

    answers = iter(["short", "short"])
    assert main(["reset-password"], ask=lambda _: next(answers)) == 1  # policy holds
    answers = iter(["new password 123", "other one 1234"])
    assert main(["reset-password"], ask=lambda _: next(answers)) == 1  # must match
    answers = iter(["new password 123", "new password 123"])
    assert main(["reset-password"], ask=lambda _: next(answers)) == 0
    authed.post("/api/auth/logout")
    assert authed.post("/api/auth/login", json={"password": PASSWORD}).status_code == 401
    assert authed.post("/api/auth/login", json={"password": "new password 123"}).status_code == 204


def test_a_new_password_ends_every_other_session(authed, monkeypatch):
    """A leaked password, changed: the old sessions stop at once, this one goes on
    (review 2026-10-24); a reset on the command line ends them too."""
    from app.modules.auth import middleware
    from app.modules.auth.__main__ import main

    old = dict(authed.cookies)
    assert (
        authed.post(
            "/api/auth/password", json={"current": PASSWORD, "new": "new password 123"}
        ).status_code
        == 204
    )
    assert authed.get("/api/settings").status_code == 200  # this browser: new cookie
    new = dict(authed.cookies)
    authed.cookies.clear()
    authed.cookies.update(old)
    assert authed.get("/api/settings").status_code == 401  # the other one: ended

    authed.cookies.clear()
    authed.cookies.update(new)
    monkeypatch.setattr(middleware, "STAMP_TTL", 0)  # no waiting for the cache
    answers = iter(["third password 1", "third password 1"])
    assert main(["reset-password"], ask=lambda _: next(answers)) == 0
    assert authed.get("/api/settings").status_code == 401


def test_a_setup_upload_needs_the_code_before_the_file_is_taken(client):
    """The code is a header, checked before the body is read (review 2026-10-24)."""
    client.app.state.boot.setup_code = "123-456"
    files = {"files": ("x.dump.enc", b"data")}
    r = client.post("/api/auth/setup/backup-upload", files=files)
    assert r.json()["error"]["code"] == "auth.setup_code_invalid"
    r = client.post(
        "/api/auth/setup/backup-upload", files=files, headers={"X-Setup-Code": "123-456"}
    )
    assert r.json().get("error", {}).get("code") != "auth.setup_code_invalid"

import logging

from app.core import logs


def test_mask_hides_secrets_and_shortens_addresses():
    line = logs.mask(
        "GET /api?apiKey=abc123&x=1 sign=deadbeef Bearer ey.J0 "
        "0x52908400098527886E0F7030069857D2E4169EE7 "
        "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq "
        '{"secret": "s3cr3t"} done'
    )
    assert "abc123" not in line and "deadbeef" not in line and "ey.J0" not in line
    assert "s3cr3t" not in line
    assert "0x5290…9EE7" in line and "bc1qar…5mdq" in line
    assert line.endswith("done") and "x=1" in line


def test_ring_keeps_new_lines_in_order():
    ring = logs.Ring(size=3)
    lg = logging.getLogger("test.ring")
    lg.addHandler(ring)
    lg.setLevel(logging.DEBUG)
    try:
        for i in range(5):
            lg.info("line %d", i)
    finally:
        lg.removeHandler(ring)
    assert [x["message"] for x in ring.since()] == ["line 2", "line 3", "line 4"]
    assert [x["message"] for x in ring.since(4)] == ["line 4"]
    assert ring.since(0, limit=1)[0]["seq"] == 5


def _app(lines):
    """Without the test client's own request lines."""
    return [x for x in lines if not x["logger"].startswith("httpx")]


def test_live_lines_and_level(authed):
    logging.getLogger("app.test").warning("hello from the backend")
    first = authed.get("/api/system/logs").json()
    assert any(x["message"] == "hello from the backend" for x in first["lines"])
    later = authed.get("/api/system/logs", params={"after": first["last"]}).json()["lines"]
    assert _app(later) == []
    # the browser's errors land in the same log, marked as frontend
    r = authed.post(
        "/api/system/logs/client", json=[{"level": "ERROR", "message": "boom", "page": "/x"}]
    )
    assert r.status_code == 204
    new = _app(authed.get("/api/system/logs", params={"after": first["last"]}).json()["lines"])
    assert [(x["origin"], x["level"], x["message"]) for x in new] == [
        ("frontend", "ERROR", "boom (/x)")
    ]
    # the level applies at once and is kept as a setting
    try:
        authed.patch("/api/settings", json={"system.log_level": "DEBUG"})
        assert authed.get("/api/system/logs").json()["level"] == "DEBUG"
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert authed.patch("/api/settings", json={"system.log_level": "LOUD"}).status_code == 400
    finally:
        authed.patch("/api/settings", json={"system.log_level": "INFO"})
    assert logging.getLogger().level == logging.INFO


def test_logs_need_a_session(client):
    assert client.get("/api/system/logs").status_code == 401
    assert client.post("/api/system/logs/client", json=[]).status_code == 401

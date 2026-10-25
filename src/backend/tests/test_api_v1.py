"""The read-only JSON API (ADR 0050): same tokens and functions as MCP, own switch."""

import logging

import pytest


@pytest.fixture
def token(authed):
    t = authed.post("/api/mcp/tokens", json={"name": "Widget", "kind": "api"}).json()["token"]
    authed.patch("/api/settings", json={"api.enabled": True})
    return t


def get(client, path, token=None, **params):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # without the web login: the API stands on its token alone
    client.cookies.clear()
    return client.get(path, headers=headers, params=params)


def test_needs_a_token_and_the_switch(authed, token):
    mcp = authed.post("/api/mcp/tokens", json={"name": "Claude"}).json()["token"]
    assert get(authed, "/api/v1/portfolio").status_code == 401
    assert get(authed, "/api/v1/portfolio", "ocf_api_wrong").status_code == 401
    # a Claude token does not open the API
    assert get(authed, "/api/v1/portfolio", mcp).status_code == 401
    assert get(authed, "/api/v1/portfolio", token).status_code == 200
    from app.core.db import _session_factory
    from app.modules.settings import service

    with _session_factory()() as db:
        service.update(db, {"api.enabled": False})
    r = get(authed, "/api/v1/portfolio", token)
    assert r.status_code == 403 and r.json()["error"]["code"] == "api.off"


def test_index_lists_the_reading_functions(authed, token):
    eps = {e["path"]: e for e in get(authed, "/api/v1", token).json()["endpoints"]}
    assert "/api/v1/portfolio" in eps and "/api/v1/tax_free_soon" in eps
    assert not any("plan_" in p or "apply" in p for p in eps)  # nothing that writes
    assert "days" in eps["/api/v1/tax_free_soon"]["params"]


def test_calls_with_parameters_and_logs(authed, token, caplog):
    with caplog.at_level(logging.INFO, logger="api"):
        r = get(authed, "/api/v1/tax_free_soon", token, days="30")
    assert r.status_code == 200 and r.json()["upcoming"] == []
    assert any("api=tax_free_soon client=Widget" in x.getMessage() for x in caplog.records)
    assert get(authed, "/api/v1/tax_free_soon", token, days="abc").status_code == 400
    assert get(authed, "/api/v1/tax_free_soon", token, days="9999").status_code == 400
    assert get(authed, "/api/v1/nope", token).status_code == 404
    assert get(authed, "/api/v1/search_transactions", token, limit="5").json()["total"] == 0

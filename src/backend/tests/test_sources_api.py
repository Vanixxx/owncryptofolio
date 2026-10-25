from app.modules.plugins import registry as reg

ETH = "0x" + "ab" * 20


def test_plugins_listed(authed):
    data = authed.get("/api/plugins").json()
    providers = {p["provider"]: p for p in data["providers"]}
    assert {c["channel"] for c in providers["bitget"]["channels"]} == {"api", "file"}
    assert providers["bitget"]["credentials"]["secret"] == ["api_secret", "api_passphrase"]
    assert providers["ethereum"]["kind"] == "wallet"


def test_create_and_list(authed):
    assert (
        authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"}).status_code
        == 201
    )
    r = authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "Ledger", "address": ETH, "wallet_id": _w(authed)},
    )
    assert r.status_code == 201
    labels = {s["label"]: s for s in authed.get("/api/sources").json()}
    assert labels["Ledger"]["address"] == ETH and labels["Bitget"]["address"] is None


def test_wallet_address_is_checked(authed):
    r = authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "x", "address": "0x12", "wallet_id": _w(authed)},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "sources.invalid_address"
    authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "a", "address": ETH, "wallet_id": _w(authed)},
    )
    r = authed.post(
        "/api/sources",
        json={
            "provider": "ethereum",
            "label": "b",
            "wallet_id": _w(authed),
            "address": ETH.upper().replace("0X", "0x"),
        },
    )
    assert r.status_code == 409


def test_unknown_provider(authed):
    r = authed.post("/api/sources", json={"provider": "nope", "label": "x"})
    assert r.json()["error"]["code"] == "sources.unknown_provider"


def _bitget(authed) -> int:
    authed.post("/api/sources", json={"provider": "bitget", "label": "Bitget"})
    return authed.get("/api/sources").json()[0]["id"]


SECRETS = {
    "api_key": "key-1234567",
    "api_secret": "very-secret-value",
    "api_passphrase": "pass-phrase-xyz",
}


def test_credentials_are_never_returned(authed):
    sid = _bitget(authed)
    assert authed.put(f"/api/sources/{sid}/credentials", json=SECRETS).status_code == 204
    text = authed.get("/api/sources").text
    for value in SECRETS.values():
        assert value not in text
    assert authed.get("/api/sources").json()[0]["credentials"] == sorted(SECRETS)


def test_incomplete_credentials(authed):
    sid = _bitget(authed)
    r = authed.put(f"/api/sources/{sid}/credentials", json={"api_key": "k"})
    assert r.json()["error"] == {
        "code": "sources.credentials_incomplete",
        "params": {"fields": ["api_secret", "api_passphrase"]},
    }


def test_check_scrubs_secrets_from_the_error(authed, monkeypatch):
    sid = _bitget(authed)
    authed.put(f"/api/sources/{sid}/credentials", json=SECRETS)
    module = reg.registry().plugins["bitget_api"].module

    def failing(creds):
        raise RuntimeError(f"bitget 40012 apikey/password is incorrect: {creds['api_secret']}")

    monkeypatch.setattr(module, "check", failing)
    r = authed.post(f"/api/sources/{sid}/check").json()
    assert r["ok"] is False and "very-secret-value" not in r["message"] and "***" in r["message"]
    monkeypatch.setattr(module, "check", lambda creds: None)
    assert authed.post(f"/api/sources/{sid}/check").json() == {"ok": True, "message": None}
    assert authed.get("/api/sources").json()[0]["last_check"]["ok"] is True


def test_delete_source(authed):
    sid = _bitget(authed)
    assert authed.delete(f"/api/sources/{sid}").status_code == 204
    assert authed.get("/api/sources").json() == []


def _w(authed) -> int:
    existing = authed.get("/api/wallets").json()
    if existing:
        return existing[0]["id"]
    return authed.post("/api/wallets", json={"name": "W"}).json()["id"]

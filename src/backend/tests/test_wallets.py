ETH = "0x" + "ab" * 20


def _wallet(authed, name="Tangem Cold Wallet") -> int:
    r = authed.post("/api/wallets", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_wallet_with_networks(authed):
    wid = _wallet(authed)
    r = authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "Ethereum", "address": ETH, "wallet_id": wid},
    )
    assert r.status_code == 201
    (src,) = authed.get("/api/sources").json()
    assert src["wallet_id"] == wid and src["address"] == ETH
    assert authed.get("/api/wallets").json() == [{"id": wid, "name": "Tangem Cold Wallet"}]


def test_network_needs_a_wallet(authed):
    r = authed.post("/api/sources", json={"provider": "ethereum", "label": "x", "address": ETH})
    assert r.json()["error"]["code"] == "wallets.required"
    r = authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "x", "address": ETH, "wallet_id": 999},
    )
    assert r.json()["error"]["code"] == "wallets.required"


def test_exchange_ignores_wallet(authed):
    wid = _wallet(authed)
    authed.post("/api/sources", json={"provider": "bitget", "label": "B", "wallet_id": wid})
    assert authed.get("/api/sources").json()[0]["wallet_id"] is None


def test_same_address_cannot_be_in_two_wallets(authed):
    a, b = _wallet(authed, "A"), _wallet(authed, "B")
    authed.post(
        "/api/sources", json={"provider": "ethereum", "label": "E", "address": ETH, "wallet_id": a}
    )
    r = authed.post(
        "/api/sources", json={"provider": "ethereum", "label": "E", "address": ETH, "wallet_id": b}
    )
    assert r.status_code == 409


def test_names_rename_and_delete(authed):
    wid = _wallet(authed)
    assert authed.post("/api/wallets", json={"name": "tangem cold wallet"}).status_code == 409
    assert (
        authed.post("/api/wallets", json={"name": "  "}).json()["error"]["code"]
        == "wallets.name_required"
    )
    assert authed.patch(f"/api/wallets/{wid}", json={"name": "Tangem"}).json()["name"] == "Tangem"
    authed.post(
        "/api/sources",
        json={"provider": "ethereum", "label": "E", "address": ETH, "wallet_id": wid},
    )
    r = authed.delete(f"/api/wallets/{wid}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "wallets.has_networks"
    sid = authed.get("/api/sources").json()[0]["id"]
    authed.delete(f"/api/sources/{sid}")
    assert authed.delete(f"/api/wallets/{wid}").status_code == 204


def test_evm_family_is_announced(authed):
    providers = {p["provider"]: p for p in authed.get("/api/plugins").json()["providers"]}
    assert providers["ethereum"]["family"] == "evm"
    assert providers["bitget"]["family"] is None

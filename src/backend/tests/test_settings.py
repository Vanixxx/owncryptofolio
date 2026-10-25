def test_defaults(authed):
    s = authed.get("/api/settings").json()
    assert s == {
        "appearance.style": "night",
        "appearance.theme": "system",
        "appearance.accents": {},
        "appearance.icon": "E5",
        "general.language": "de",
        "general.currency": "EUR",
        "general.timezone": "Europe/Berlin",
        "backup.enabled": True,
        "fetch.enabled": True,
        "fetch.time": "04:00",
        "backup.time": "03:00",
        "prices.enabled": True,
        "prices.time": "04:30",
        "prices.latest_minutes": 5,
        "prices.source_order": ["yahoo", "bitget", "binance"],
        "backup.keep_daily": 14,
        "backup.keep_monthly": 12,
        "tax.method": "fifo",
        "tax.airdrop_taxable": False,
        "report.name": "",
        "report.address": "",
        "report.tax_number": "",
        "system.log_level": "INFO",
        "mcp.enabled": False,
        "api.enabled": False,
    }


def test_backup_settings_are_validated(authed):
    for bad in (
        {"backup.time": "25:00"},
        {"backup.time": "3:00"},
        {"backup.keep_daily": 0},
        {"backup.keep_daily": True},
        {"backup.enabled": 1},
    ):
        assert authed.patch("/api/settings", json=bad).status_code == 400, bad
    assert authed.patch("/api/settings", json={"backup.time": "04:30"}).status_code == 200


def test_update_and_persist(authed):
    r = authed.patch("/api/settings", json={"appearance.style": "neon", "general.language": "en"})
    assert r.status_code == 200
    s = authed.get("/api/settings").json()
    assert s["appearance.style"] == "neon" and s["general.language"] == "en"


def test_reset_to_default_removes_row(authed):
    authed.patch("/api/settings", json={"appearance.style": "terminal"})
    authed.patch("/api/settings", json={"appearance.style": "night"})
    assert authed.get("/api/settings").json()["appearance.style"] == "night"


def test_invalid_value_and_unknown_key(authed):
    r = authed.patch("/api/settings", json={"appearance.style": "pink"})
    assert r.status_code == 400
    assert r.json()["error"] == {
        "code": "settings.invalid_value",
        "params": {"key": "appearance.style"},
    }
    r = authed.patch("/api/settings", json={"nope": 1})
    assert r.json()["error"]["code"] == "settings.unknown_key"
    r = authed.patch("/api/settings", json={"general.timezone": "Mars/Base"})
    assert r.status_code == 400


def test_invalid_batch_changes_nothing(authed):
    authed.patch("/api/settings", json={"appearance.style": "neon", "general.language": "xx"})
    assert authed.get("/api/settings").json()["appearance.style"] == "night"


def test_schema_lists_choices(authed):
    schema = authed.get("/api/settings/schema").json()
    assert schema["appearance.style"]["choices"] == [
        "night",
        "neon",
        "terminal",
        "graphite",
        "rose",
        "contrast",
        "amethyst",
        "sand",
        "ios",
    ]
    assert schema["general.language"]["choices"] == ["de", "en"]

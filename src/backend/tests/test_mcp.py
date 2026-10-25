"""Claude through MCP (ADR 0049): token, mode, tools — over HTTP like Claude Code."""

import json
import logging

import pytest

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client, token, method, params=None, id_=1):
    headers = HEADERS | ({"Authorization": f"Bearer {token}"} if token else {})
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    return client.post("/mcp", headers=headers, content=json.dumps(body))


def init(client, token):
    return rpc(client, token, "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    })  # fmt: skip


@pytest.fixture
def token(authed):
    r = authed.post("/api/mcp/tokens", json={"name": "Claude Code Laptop"})
    assert r.status_code == 201
    assert authed.patch("/api/settings", json={"mcp.enabled": True}).status_code == 200
    return r.json()["token"]


def call(client, token, tool, args=None):
    r = rpc(client, token, "tools/call", {"name": tool, "arguments": args or {}})
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_token_is_shown_once_and_kept_as_hash(authed, token, db):
    from app.modules.mcp.models import McpToken

    row = db.query(McpToken).one()
    assert row.name == "Claude Code Laptop" and token not in row.token_hash
    status = authed.get("/api/mcp").json()
    assert status["enabled"] is True and "token" not in status["tokens"][0]
    assert status["tokens"][0]["kind"] == "mcp" and status["tokens"][0]["level"] == "read"


def test_no_token_wrong_token_or_off_is_refused(authed, token):
    assert init(authed, None).status_code == 401
    assert init(authed, "ocf_mcp_nope").status_code == 401
    # the web login cookie does not open MCP
    assert init(authed, None).json()["error"] == "mcp.token_invalid"
    authed.patch("/api/settings", json={"mcp.enabled": False})
    assert init(authed, token).status_code == 403
    assert authed.patch("/api/settings", json={"mcp.enabled": "loud"}).status_code == 400


def test_revoked_token_stops_working(authed, token):
    assert init(authed, token).status_code == 200
    tid = authed.get("/api/mcp").json()["tokens"][0]["id"]
    assert authed.delete(f"/api/mcp/tokens/{tid}").status_code == 204
    assert init(authed, token).status_code == 401


def test_tools_are_listed_read_only(authed, token):
    r = init(authed, token)
    assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "owncryptofolio"
    tools = {t["name"]: t for t in rpc(authed, token, "tools/list").json()["result"]["tools"]}
    assert {
        "portfolio", "sources", "balance_check", "holdings_by_source", "search_transactions",
        "transaction", "open_transfers", "prices", "tax_year", "loss_carry", "tax_free_soon",
        "origin", "origin_candidates", "system_status", "log_excerpt",
    } <= set(tools)  # fmt: skip
    readers = {
        n: t
        for n, t in tools.items()
        if not (n.startswith("plan_") or n in ("apply_plan", "start_fetch"))
    }
    assert len(readers) == 15 and all(t["annotations"]["readOnlyHint"] for t in readers.values())
    # the session parameter stays inside
    assert "db" not in tools["search_transactions"]["inputSchema"]["properties"]


def test_tools_answer_and_every_call_is_logged(authed, token, caplog):
    authed.post("/api/sources", json={"provider": "manual", "label": "Bitpanda"})
    with caplog.at_level(logging.INFO, logger="mcp"):
        assert call(authed, token, "sources")["sources"][0]["label"] == "Bitpanda"
    assert any("tool=sources client=Claude Code Laptop" in r.getMessage() for r in caplog.records)
    assert call(authed, token, "portfolio")["coins"] == []
    found = call(authed, token, "search_transactions", {"limit": 5})
    assert found == {"total": 0, "shown": 0, "more": False, "items": []}
    assert "operations" in call(authed, token, "system_status")
    assert call(authed, token, "tax_free_soon")["upcoming"] == []
    assert "rows" in call(authed, token, "loss_carry")
    assert authed.get("/api/mcp").json()["last_call"]["tool"] == "loss_carry"


def test_errors_come_back_as_tool_errors(authed, token):
    r = rpc(authed, token, "tools/call", {"name": "transaction", "arguments": {"row_id": 999999}})
    assert r.json()["result"]["isError"] is True


def test_log_excerpt_masks_and_leaves_out_its_own_lines(authed, token):
    logging.getLogger("app.test").warning("withdraw to 0x52908400098527886E0F7030069857D2E4169EE7")
    lines = call(authed, token, "log_excerpt", {"level": "WARNING"})["lines"]
    text = " ".join(x["message"] for x in lines)
    assert "0x5290…9EE7" in text and "0x52908400098527886E0F7030069857D2E4169EE7" not in text
    assert all(x["logger"] != "mcp" for x in lines)


# --- stage 2: plans the user confirms as a whole ------------------------------------------

BUY = {"kind": "trade", "time": "2024-01-02T10:00", "incoming_asset": "BTC",
       "incoming_amount": "0.1", "outgoing_asset": "EUR", "outgoing_amount": "3000"}  # fmt: skip


def _edit(client) -> None:
    """Claude may edit with this token: set per token (Vanixxx, 2026-10-20)."""
    tid = client.get("/api/mcp").json()["tokens"][0]["id"]
    assert client.patch(f"/api/mcp/tokens/{tid}", json={"level": "edit"}).status_code == 204


def _source(client) -> int:
    client.post("/api/sources", json={"provider": "manual", "label": "Bitpanda"})
    return client.get("/api/sources").json()[0]["id"]


def _rows(db) -> int:
    from sqlalchemy import func, select

    from app.modules.raw.models import RawTransaction

    db.expire_all()
    return db.scalar(select(func.count()).select_from(RawTransaction))


def test_write_tools_need_the_mode_edit(authed, token):
    sid = _source(authed)
    r = rpc(authed, token, "tools/call", {"name": "plan_add_entries",
            "arguments": {"items": [{"source_id": sid, "entry": BUY}]}})  # fmt: skip
    assert r.json()["result"]["isError"] is True
    assert "mcp.edit_off" in r.json()["result"]["content"][0]["text"]
    tools = {t["name"]: t for t in rpc(authed, token, "tools/list").json()["result"]["tools"]}
    assert tools["apply_plan"]["annotations"]["readOnlyHint"] is False
    assert "complete list" in tools["plan_notes"]["description"].lower()


def test_plan_previews_without_changing_then_applies_exactly_once(authed, token, db):
    _edit(authed)
    sid = _source(authed)
    bad = BUY | {"incoming_amount": "-1"}
    plan = call(authed, token, "plan_add_entries", {"items": [
        {"source_id": sid, "entry": BUY}, {"source_id": sid, "entry": bad}]})  # fmt: skip
    # the whole list, the broken item named, the effect on holdings — and nothing written
    assert (plan["will_apply"], plan["skipped"]) == (1, 1)
    assert plan["items"][0]["after"]["incoming"] == "0.1 BTC"
    assert (
        plan["items"][1]["status"] == "skipped"
        and "manual.invalid_amount" in plan["items"][1]["reason"]
    )
    assert plan["holdings_effect"] == {"BTC": "+0.1"}  # fiat is no holding of its own
    assert _rows(db) == 0
    # a number outside the list is refused, the plan stays
    r = rpc(
        authed,
        token,
        "tools/call",
        {"name": "apply_plan", "arguments": {"plan_id": plan["plan_id"], "only": [3]}},
    )
    assert (
        r.json()["result"]["isError"] is True
        and "mcp.plan_items_unknown" in r.json()["result"]["content"][0]["text"]
    )
    done = call(authed, token, "apply_plan", {"plan_id": plan["plan_id"]})
    assert done["done"] == 1 and [r["status"] for r in done["results"]] == ["done", "skipped"]
    assert _rows(db) == 1
    # one use per plan: the list cannot be applied twice or changed afterwards
    r = rpc(
        authed,
        token,
        "tools/call",
        {"name": "apply_plan", "arguments": {"plan_id": plan["plan_id"]}},
    )
    assert r.json()["result"]["isError"] is True
    # what Claude changed shows in the transactions list
    listed = authed.get("/api/merged", params={"show": "mcp"}).json()
    assert listed["total"] == 1


def test_corrections_keep_the_original_and_notes_are_set(authed, token, db):
    _edit(authed)
    sid = _source(authed)
    row = authed.post(f"/api/sources/{sid}/manual", json=BUY).json()["id"]
    plan = call(authed, token, "plan_correct_rows", {"items": [
        {"row_id": row, "entry": BUY | {"incoming_amount": "0.2"}}]})  # fmt: skip
    assert plan["items"][0]["now"]["incoming"] == "0.1 BTC"
    assert plan["items"][0]["after"]["incoming"] == "0.2 BTC"
    assert plan["holdings_effect"] == {"BTC": "+0.1"}
    call(authed, token, "apply_plan", {"plan_id": plan["plan_id"]})
    assert _rows(db) == 2  # the original stays stored
    note = call(authed, token, "plan_notes", {"items": [{"row_id": row, "text": "von Claude"}]})
    assert call(authed, token, "apply_plan", {"plan_id": note["plan_id"]})["done"] == 1
    from app.modules.mcp.models import McpChange

    db.expire_all()
    assert [c.action for c in db.query(McpChange).order_by(McpChange.id)] == [
        "correct_rows",
        "notes",
    ]
    assert {c.token for c in db.query(McpChange)} == {"Claude Code Laptop"}


def test_only_the_chosen_items_of_a_plan(authed, token, db):
    """ "1-14, not 44": the user picks a part of the list, nothing outside it."""
    _edit(authed)
    sid = _source(authed)
    rows = [authed.post(f"/api/sources/{sid}/manual", json=BUY | {"time": f"2024-01-0{d}T10:00"}).json()["id"]
            for d in (2, 3, 4)]  # fmt: skip
    plan = call(
        authed, token, "plan_notes", {"items": [{"row_id": r, "text": f"n{r}"} for r in rows]}
    )
    done = call(authed, token, "apply_plan", {"plan_id": plan["plan_id"], "only": [1, 3]})
    assert [r["status"] for r in done["results"]] == ["done", "left out", "done"]
    noted = authed.get("/api/merged", params={"show": "noted"}).json()
    assert noted["total"] == 2


def test_a_token_opens_only_its_own_door(authed, token):
    api = authed.post("/api/mcp/tokens", json={"name": "Sheet", "kind": "api"}).json()["token"]
    assert api.startswith("ocf_api_") and token.startswith("ocf_mcp_")
    assert init(authed, api).status_code == 401  # an API token is no MCP token
    # an API token has no level "edit"
    r = authed.post("/api/mcp/tokens", json={"name": "x", "kind": "api", "level": "edit"})
    assert r.status_code == 400


def test_a_plan_is_carried_out_only_with_the_token_that_made_it():
    """Review 2026-10-24: another token's plan is as unknown as none."""
    import pytest

    from app.core.errors import AppError
    from app.modules.mcp import edit

    edit.plans["p1"] = edit.Plan(id="p1", action="note", items=[], ok=[], token="A")
    with pytest.raises(AppError) as err:
        edit.apply("p1", "B", lambda: None)
    assert err.value.code == "mcp.plan_unknown"
    assert edit.apply("p1", "A", lambda: None)["done"] == 0

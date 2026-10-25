"""Merged view (ADR 0005, 0039): transfers, ambiguity, decisions, spam, dust."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.merged import detect
from app.modules.plugins.contract import IncomeKind, Kind, Movement

T = datetime(2025, 1, 22, 12, tzinfo=UTC)


def h(fp, minutes, amount, asset="ETH", tx=None, source=1):
    return detect.Half(fp, T + timedelta(minutes=minutes), asset, Decimal(amount), tx, source)


def test_tx_id_first_then_amount_and_time_never_guess():
    sends = [h("s1", 0, "1.0", tx="0xabc"), h("s2", 0, "2.0"), h("s3", 0, "5.0")]
    receives = [
        h(
            "r1", 30, "0.9", tx="ABC", source=2
        ),  # same hash (Coinbase drops "0x"): amount no longer matters
        h("r2", 3, "1.9937", source=2),  # 0.3 % network fee, 3 minutes
        h("r3", 5, "5.0", source=2),
        h("r4", 6, "4.99", source=3),
    ]  # two candidates
    pairs, ambiguous = detect.find_pairs(sends, receives)
    assert {(p.send, p.receive, p.reason) for p in pairs} == {
        ("s1", "r1", "tx"),
        ("s2", "r2", "match"),
    }
    assert ambiguous == ["s3"]


def test_tolerances_and_split_forbids_only_that_pair():
    sends = [h("s", 0, "1.0")]
    assert detect.find_pairs(sends, [h("r", 61, "1.0", source=2)])[0] == []  # over an hour
    assert detect.find_pairs(sends, [h("r", 5, "0.98", source=2)])[0] == []  # 2 % off
    assert detect.find_pairs(sends, [h("r", 5, "1.0", source=1)])[0] == []  # same source
    pairs, _ = detect.find_pairs(
        sends, [h("r", 5, "1.0", source=2), h("r2", 20, "1.0", source=2)], forbidden={("s", "r")}
    )
    assert [(p.send, p.receive) for p in pairs] == [("s", "r2")]
    cands = detect.candidates(h("s", 0, "1.0"), [h("r", 600, "0.97", source=2)], set(), set())
    assert len(cands) == 1 and not cands[0].sharp  # 3 % network fee: suggested, never linked


@pytest.fixture
def two_sources(authed, db):
    from app.modules.raw import service as raw
    from app.modules.sources.models import Source

    authed.post("/api/sources", json={"provider": "manual", "label": "Bitget-ish"})
    authed.post("/api/sources", json={"provider": "manual", "label": "Wallet-ish"})
    a, b = db.query(Source).order_by(Source.id).all()
    raw.import_movements(
        db,
        a,
        "file",
        "a",
        [
            Movement(
                timestamp=T,
                kind=Kind.SEND,
                outgoing_asset="ETH",
                outgoing_amount=Decimal("1.0"),
                fee_asset="ETH",
                fee_amount=Decimal("0.001"),
            ),
            Movement(
                timestamp=T + timedelta(days=3),
                kind=Kind.SEND,
                outgoing_asset="ETH",
                outgoing_amount=Decimal("0.5"),
            ),
            Movement(
                timestamp=T,
                kind=Kind.INCOME,
                income_kind=IncomeKind.STAKING,
                incoming_asset="DOT",
                incoming_amount=Decimal("0.00001"),
            ),
        ],
    )
    raw.import_movements(
        db,
        b,
        "file",
        "b",
        [
            Movement(
                timestamp=T + timedelta(minutes=4),
                kind=Kind.RECEIVE,
                incoming_asset="ETH",
                incoming_amount=Decimal("0.9937"),
            ),
            Movement(
                timestamp=T + timedelta(days=3, hours=10),
                kind=Kind.RECEIVE,
                incoming_asset="ETH",
                incoming_amount=Decimal("0.49"),
            ),
            Movement(
                timestamp=T,
                kind=Kind.RECEIVE,
                incoming_asset="HBAR",
                incoming_amount=Decimal("7302"),
            ),
            Movement(
                timestamp=T + timedelta(hours=1),
                kind=Kind.RECEIVE,
                incoming_asset="HBAR",
                incoming_amount=Decimal("0.00000001"),
            ),
        ],
    )
    return a, b


def _items(authed, **params):
    return authed.get("/api/merged", params=params).json()


def test_transfer_is_one_line_with_network_fee(two_sources, authed):
    body = _items(authed)
    transfers = [i for i in body["items"] if i["type"] == "transfer"]
    assert len(transfers) == 1
    t = transfers[0]
    assert t["send"]["outgoing"] == ["ETH", "1"] and t["receive"]["incoming"] == ["ETH", "0.9937"]
    assert t["network_fee"] == ["ETH", "0.0063"] and t["reason"] == "match"
    # one send and two receives without counterpart (receives count since 2026-10-11)
    assert body["summary"]["transfers"] == 1 and body["summary"]["open"] == 3


def test_notice_counts_follow_the_other_filters(two_sources, authed):
    # the notice filter itself does not narrow its counts, every other filter does
    assert _items(authed, show="spam")["summary"]["open"] == 3
    assert _items(authed, date_to="2020-01-01")["summary"]["open"] == 0
    assert _items(authed, asset="BTC")["summary"]["transfers"] == 0


def test_link_suggestion_split_and_open_mark(two_sources, authed):
    open_send = next(i for i in _items(authed, show="open")["items"] if i["row"]["kind"] == "send")[
        "row"
    ]
    cands = authed.get(f"/api/merged/candidates/{open_send['id']}").json()
    assert len(cands) == 1 and cands[0]["sharp"] is False and cands[0]["minutes"] == 600
    receive = cands[0]["receive"]["id"]
    assert (
        authed.post(
            "/api/merged/link", json={"send_id": open_send["id"], "receive_id": receive}
        ).status_code
        == 204
    )
    body = _items(authed)
    assert body["summary"]["transfers"] == 2 and body["summary"]["open"] == 1  # the other receive
    manual = next(i for i in body["items"] if i["type"] == "transfer" and i["reason"] == "manual")
    # split it again: the pair is forbidden, the send is open again
    assert (
        authed.post(
            "/api/merged/split", json={"send_id": open_send["id"], "receive_id": receive}
        ).status_code
        == 204
    )
    assert _items(authed)["summary"]["open"] == 3
    assert manual["send"]["id"] == open_send["id"]
    again = authed.get(f"/api/merged/candidates/{open_send['id']}").json()
    assert again[0]["split_before"] is True  # offered, so the split can be undone
    assert (
        authed.post(
            "/api/merged/open-mark",
            json={"send_id": open_send["id"], "mark": "external", "note": "Zahlung"},
        ).status_code
        == 204
    )
    row = next(
        i
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["id"] == open_send["id"]
    )
    assert row["open"] is False and row["open_mark"] == "external"
    bad = authed.post("/api/merged/open-mark", json={"send_id": open_send["id"], "mark": "nope"})
    assert bad.json()["error"]["code"] == "merged.invalid_mark"


def test_dust_is_suggested_only_for_receives_and_spam_hides(two_sources, authed, db):
    from app.modules.prices.models import PriceAsset

    dust = _items(authed, show="dust")["items"]
    assert [i["row"]["incoming"] for i in dust] == [
        ["HBAR", "0.00000001"]
    ]  # staking income is never dust
    assert authed.post(
        "/api/merged/spam", json={"raw_ids": [dust[0]["row"]["id"]], "spam": True}
    ).json() == {"rows": 1}
    body = _items(authed)
    assert body["summary"]["dust"] == 0 and body["summary"]["spam"] == 1
    assert all(
        not (i["type"] == "row" and i["row"]["id"] == dust[0]["row"]["id"]) for i in body["items"]
    )
    assert len(_items(authed, show="spam")["items"]) == 1
    db.add(
        PriceAsset(asset="DOT", ignored=True)
    )  # a coin ignored on the prices page is spam everywhere
    db.commit()
    assert _items(authed)["summary"]["spam"] == 2


def test_filters_by_kind_coin_and_period_in_the_users_zone(two_sources, authed):
    transfers = _items(authed, kind="transfer")["items"]
    assert len(transfers) == 1 and transfers[0]["type"] == "transfer"
    receives = _items(authed, kind="receive")["items"]
    assert receives and all(i["type"] == "row" and i["row"]["kind"] == "receive" for i in receives)
    hbar = _items(authed, asset="hbar")["items"]
    assert hbar and all(i["row"]["incoming"][0] == "HBAR" for i in hbar)
    # 2025-01-22 12:00 UTC is 13:00 in Berlin: inside the 22nd, outside the 23rd
    day = _items(authed, date_from="2025-01-22", date_to="2025-01-22", tz="Europe/Berlin")["items"]
    assert any(i["type"] == "transfer" for i in day)
    later = _items(authed, date_from="2025-01-23", tz="Europe/Berlin")["items"]
    assert all(i["at"] > "2025-01-23" for i in later)


def test_raw_list_filters_by_wallet_and_alias(authed, db):
    from app.modules.prices.models import AssetAlias
    from app.modules.raw import service as raw

    authed.post("/api/wallets", json={"name": "Tangem"})
    wallet = authed.get("/api/wallets").json()[0]
    authed.post("/api/sources", json={"provider": "manual", "label": "Elsewhere"})
    from app.modules.sources.models import Source

    src = db.query(Source).one()
    raw.import_movements(
        db,
        src,
        "file",
        "a",
        [
            Movement(
                timestamp=T, kind=Kind.RECEIVE, incoming_asset="NTGL", incoming_amount=Decimal(1)
            )
        ],
    )
    db.add(AssetAlias(alias="NTGL", asset="NGL"))
    db.commit()
    assert authed.get("/api/raw", params={"asset": "NGL"}).json()["total"] == 1
    assert authed.get("/api/raw", params={"wallet_id": wallet["id"]}).json()["total"] == 0


def test_sort_by_time_either_way_and_by_value(two_sources, authed, db):
    from app.modules.prices.models import PriceDaily

    for i in range(10):
        day = T.date() + timedelta(days=i)
        db.add(PriceDaily(asset="ETH", day=day, quote="EUR", close=Decimal(3000), source="t"))
        db.add(PriceDaily(asset="HBAR", day=day, quote="EUR", close=Decimal("0.1"), source="t"))
    db.commit()
    newest = [i["at"] for i in _items(authed)["items"]]
    oldest = [i["at"] for i in _items(authed, desc="false")["items"]]
    assert newest == sorted(newest, reverse=True) and oldest == sorted(oldest)
    by_value = _items(authed, sort="value")["items"]
    # the ETH transfer (3,000 €) before the HBAR receive of 7,302 × 0.1 = 730 €
    assert by_value[0]["type"] == "transfer"
    raw_old = authed.get("/api/raw", params={"desc": "false"}).json()["rows"]
    assert [r["timestamp"] for r in raw_old] == sorted(r["timestamp"] for r in raw_old)


def test_a_coin_moved_twice_pairs_both_hops_but_never_guesses():
    # Bitget → Ronin (23 s apart) → bridge → Ethereum (20 min later)
    sends = [h("bitget", 0, "100", source=1), h("ronin_out", 9, "100", source=2)]
    receives = [h("ronin_in", -1, "100", source=2), h("eth_in", 29, "100", source=3)]
    pairs, ambiguous = detect.find_pairs(sends, receives)
    assert {(p.send, p.receive) for p in pairs} == {("bitget", "ronin_in"), ("ronin_out", "eth_in")}
    assert ambiguous == []
    # two equal sends, one receive: still open, both
    pairs, ambiguous = detect.find_pairs(
        [h("a", 0, "5"), h("b", 10, "5")], [h("r", 20, "5", source=2)]
    )
    assert pairs == [] and sorted(ambiguous) == ["a", "b"]


def test_every_amount_carries_its_value_at_the_time(two_sources, authed, db):
    from app.modules.prices.models import PriceDaily

    for i in range(10):
        db.add(
            PriceDaily(
                asset="ETH",
                day=T.date() + timedelta(days=i),
                quote="EUR",
                close=Decimal(3000),
                source="t",
            )
        )
    db.commit()
    transfer = next(i for i in _items(authed)["items"] if i["type"] == "transfer")
    assert transfer["send"]["values"]["outgoing"] == "3000.00"
    assert transfer["receive"]["values"]["incoming"] == "2981.10"  # 0.9937 ETH


def test_receive_finds_its_send_and_a_fee_booking_joins_the_transfer(two_sources, authed, db):
    from app.modules.raw import service as raw

    a, b = two_sources
    # an open receive at the wallet can look for its send now
    open_recv = next(
        i["row"]
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["kind"] == "receive" and i["row"]["incoming"][0] == "ETH"
    )
    cands = authed.get(f"/api/merged/candidates/{open_recv['id']}").json()
    assert (
        cands
        and cands[0]["partner"]["kind"] == "send"
        and cands[0]["receive_id"] == open_recv["id"]
    )
    # a separate 0.1 USDT deduction next to the send is offered and joins the transfer
    raw.import_movements(
        db,
        a,
        "file",
        "fee",
        [
            Movement(
                timestamp=T + timedelta(minutes=1),
                kind=Kind.OTHER,
                outgoing_asset="USDT",
                outgoing_amount=Decimal("0.1"),
            )
        ],
    )
    transfer = next(i for i in _items(authed)["items"] if i["type"] == "transfer")
    offered = authed.get(f"/api/merged/attachable/{transfer['send']['id']}").json()
    assert [o["outgoing"] for o in offered] == [["USDT", "0.1"]]
    assert (
        authed.post(
            "/api/merged/attach",
            json={"send_id": transfer["send"]["id"], "extra_id": offered[0]["id"]},
        ).status_code
        == 204
    )
    items = _items(authed)["items"]
    transfer = next(i for i in items if i["type"] == "transfer")
    assert [e["outgoing"] for e in transfer["extras"]] == [["USDT", "0.1"]]
    assert transfer["extras"][0]["attached_at"] and transfer["linked_at"] is None
    assert not any(i["type"] == "row" and i["row"]["id"] == offered[0]["id"] for i in items)
    authed.post(f"/api/merged/detach/{offered[0]['id']}")
    assert any(
        i["type"] == "row" and i["row"]["id"] == offered[0]["id"] for i in _items(authed)["items"]
    )
    # the server checks too (review 2026-10-24): a receive, or the other half of a transfer,
    # is no fee of it
    wrong = authed.post(
        "/api/merged/attach",
        json={"send_id": transfer["send"]["id"], "extra_id": transfer["receive"]["id"]},
    )
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "merged.wrong_row"
    # attached again, then the transfer split: the fee is an ordinary line again, not hidden
    fee_id = offered[0]["id"]
    authed.post("/api/merged/attach", json={"send_id": transfer["send"]["id"], "extra_id": fee_id})
    authed.post(
        "/api/merged/split",
        json={"send_id": transfer["send"]["id"], "receive_id": transfer["receive"]["id"]},
    )
    assert any(i["type"] == "row" and i["row"]["id"] == fee_id for i in _items(authed)["items"])


def test_a_send_becomes_a_transfer_to_an_own_source(two_sources, authed, db):
    from app.modules.raw import service as raw

    a, b = two_sources
    raw.import_movements(
        db,
        a,
        "file",
        "x",
        [
            Movement(
                timestamp=T + timedelta(days=5),
                kind=Kind.SEND,
                outgoing_asset="SOL",
                outgoing_amount=Decimal(2),
            )
        ],
    )
    send = next(
        i["row"]
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["outgoing"][0] == "SOL"
    )
    # b has no SOL receive: one is entered there and linked
    r = authed.post(
        "/api/merged/make-transfer", json={"send_id": send["id"], "target_source_id": b.id}
    ).json()
    assert r["created"] is True
    transfer = next(
        i
        for i in _items(authed)["items"]
        if i["type"] == "transfer" and i["send"]["id"] == send["id"]
    )
    assert transfer["receive"]["source_id"] == b.id and transfer["receive"]["incoming"] == [
        "SOL",
        "2",
    ]
    # the ETH send that is open: b has a fitting receive already, it is linked, nothing created
    open_send = next(
        i["row"]
        for i in _items(authed, show="open")["items"]
        if i["row"]["kind"] == "send" and i["row"]["outgoing"][0] == "ETH"
    )
    r = authed.post(
        "/api/merged/make-transfer", json={"send_id": open_send["id"], "target_source_id": b.id}
    ).json()
    assert r["created"] is False


def test_decisions_follow_an_edit_and_a_reset(two_sources, authed, db):
    """Editing half of a transfer linked by hand kept neither the link nor its fee
    (Vanixxx, 2026-10-06); a reset brings the original back with them."""
    from app.modules.raw import service as raw

    a, _ = two_sources
    open_send = next(i for i in _items(authed, show="open")["items"] if i["row"]["kind"] == "send")[
        "row"
    ]
    receive = authed.get(f"/api/merged/candidates/{open_send['id']}").json()[0]["receive"]["id"]
    authed.post("/api/merged/link", json={"send_id": open_send["id"], "receive_id": receive})
    raw.import_movements(
        db,
        a,
        "file",
        "fee",
        [
            Movement(
                timestamp=T + timedelta(days=3, minutes=1),
                kind=Kind.FEE,
                fee_asset="ETH",
                fee_amount=Decimal("0.0002"),
            )
        ],
    )
    fee = next(
        i["row"]
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["kind"] == "fee"
    )
    # from the fee: the transfer it may belong to
    offered = authed.get(f"/api/merged/transfers-for/{fee['id']}").json()
    assert [o["send"]["id"] for o in offered] == [open_send["id"]]
    authed.post("/api/merged/attach", json={"send_id": open_send["id"], "extra_id": fee["id"]})
    # correct the send: the link and the fee stay with the new version
    edited = authed.put(
        f"/api/raw/{open_send['id']}",
        json={
            "kind": "send",
            "time": "2025-01-25T13:00:00",
            "outgoing_asset": "ETH",
            "outgoing_amount": "0.495",
        },
    ).json()
    t = next(
        i
        for i in _items(authed)["items"]
        if i["type"] == "transfer" and i["receive"]["id"] == receive
    )
    assert t["send"]["id"] == edited["id"] and t["reason"] == "manual"
    assert t["linked_at"] and t["extras"][0]["attached_at"]  # for the collected history
    assert [e["id"] for e in t["extras"]] == [fee["id"]]
    assert t["send"]["channel"] == "manual" and t["send"]["origin"] == "file"
    assert t["send"]["modified"] is True
    # reset to the original: still one transfer, still with its fee
    assert authed.post(f"/api/raw/{open_send['id']}/restore").status_code == 204
    t = next(
        i
        for i in _items(authed)["items"]
        if i["type"] == "transfer" and i["receive"]["id"] == receive
    )
    assert t["send"]["id"] == open_send["id"] and [e["id"] for e in t["extras"]] == [fee["id"]]
    assert t["send"]["origin"] == "file" and t["send"]["edited"] is True
    assert t["send"]["modified"] is False  # the "edited" mark is gone after the reset


def test_free_search_and_own_notes(two_sources, authed, db):
    """One search box for coin, transaction ID, comment and note; a note of one's own
    neither changes the row nor marks it edited, and stays when the row is corrected."""
    hbar = next(
        i["row"]
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["incoming"] == ["HBAR", "7302"]
    )
    assert (
        authed.put(
            "/api/merged/note", json={"raw_id": hbar["id"], "text": "Ledger Staking"}
        ).status_code
        == 204
    )
    found = _items(authed, q="ledger hbar")["items"]
    assert [i["row"]["id"] for i in found] == [hbar["id"]]
    assert found[0]["row"]["note"] == "Ledger Staking" and found[0]["row"]["modified"] is False
    assert [i["type"] for i in _items(authed, q="eth")["items"]].count("transfer") == 1
    assert _items(authed, q="nothing-like-this")["items"] == []
    # the date in the user's zone counts, written either way (T is 12:00 UTC)
    assert any(i["type"] == "transfer" for i in _items(authed, q="22.01.2025")["items"])
    assert any(i["type"] == "transfer" for i in _items(authed, q="2025-01-22 eth")["items"])
    # notices: with a note
    body = authed.get("/api/merged", params={"show": "noted"}).json()
    assert [i["row"]["id"] for i in body["items"]] == [hbar["id"]] and body["summary"]["noted"] == 1
    # notices, kind and market are searchable by key (the page adds its own words)
    dust = authed.get("/api/merged", params={"q": "staub|dust"}).json()["items"]
    assert dust and all(i["dust"] for i in dust)
    assert all(i["row"]["market"] == "spot" for i in _items(authed, q="hbar spot")["items"])
    clean = authed.get("/api/merged", params={"show": "clean"}).json()["items"]
    assert clean and not any(i["type"] == "row" and i["dust"] for i in clean)
    assert len(clean) == len(_items(authed)["items"]) - len(dust)
    # "not dust" takes a line off the suggestion, and back
    tiny = dust[0]["row"]["id"]
    authed.post("/api/merged/dust", json={"raw_ids": [tiny], "dust": False})
    assert tiny not in [i["row"]["id"] for i in _items(authed, show="dust")["items"]]
    authed.post("/api/merged/dust", json={"raw_ids": [tiny], "dust": True})
    assert tiny in [i["row"]["id"] for i in _items(authed, show="dust")["items"]]
    # the source's name counts: every line of "Wallet-ish", the transfer included
    by_source = _items(authed, q="wallet-ish")["items"]
    assert len(by_source) >= 3 and any(i["type"] == "transfer" for i in by_source)
    edited = authed.put(
        f"/api/raw/{hbar['id']}",
        json={
            "kind": "receive",
            "time": "2025-01-22T13:00:00",
            "incoming_asset": "HBAR",
            "incoming_amount": "7300",
        },
    ).json()
    row = next(i["row"] for i in _items(authed, q="ledger")["items"])
    assert row["id"] == edited["id"] and row["note"] == "Ledger Staking"
    authed.put("/api/merged/note", json={"raw_id": edited["id"], "text": ""})
    assert _items(authed, q="ledger")["items"] == []


def test_saving_without_a_change_adds_no_version(two_sources, authed):
    hbar = next(
        i["row"]
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["incoming"] == ["HBAR", "7302"]
    )
    tz_time = authed.get(f"/api/raw/{hbar['id']}/history").json()[0]["time"]
    same = authed.put(
        f"/api/raw/{hbar['id']}",
        json={
            "kind": "receive",
            "time": tz_time,
            "incoming_asset": "HBAR",
            "incoming_amount": "7302",
        },
    ).json()
    assert same["id"] == hbar["id"]
    assert len(authed.get(f"/api/raw/{hbar['id']}/history").json()) == 1


def test_filters_take_several_values(two_sources, authed):
    a, b = two_sources

    def ids(**params):
        return sorted(
            (i["type"], (i.get("row") or i.get("send"))["id"])
            for i in _items(authed, **params)["items"]
        )

    # several kinds: the union of each one alone
    both = ids(kind="income,transfer")
    assert both == sorted(ids(kind="income") + ids(kind="transfer")) and len(both) >= 2
    # several sources: everything of either
    assert ids(source_id=f"{a.id},{b.id}") == ids()
    # several coins
    coins = ids(asset="hbar,dot")
    assert coins == sorted(ids(asset="HBAR") + ids(asset="DOT"))
    bad = authed.get("/api/merged", params={"source_id": "x"})
    assert bad.json()["error"]["code"] == "raw.invalid_filter"


def test_a_correction_may_move_to_another_source(two_sources, authed):
    """The transfer's receive was booked at the wrong wallet: corrected into the other
    source, the original stays, history and reset work across both (Vanixxx, 2026-10-08)."""
    a, b = two_sources
    t = next(i for i in _items(authed)["items"] if i["type"] == "transfer")
    recv = t["receive"]
    moved = authed.put(
        f"/api/raw/{recv['id']}",
        json={
            "kind": "receive",
            "time": "2025-01-22T13:04:00",
            "incoming_asset": "ETH",
            "incoming_amount": "0.9937",
            "source_id": a.id,
        },
    ).json()
    history = authed.get(f"/api/raw/{moved['id']}/history").json()
    assert [h["id"] for h in history] == [recv["id"], moved["id"]]
    row = next(
        i["row"]
        for i in _items(authed)["items"]
        if i["type"] == "row" and i["row"]["id"] == moved["id"]
    )  # same source as the send now: no transfer any more
    assert row["source_id"] == a.id and row["modified"] is True
    assert authed.post(f"/api/raw/{recv['id']}/restore").status_code == 204
    t2 = next(i for i in _items(authed)["items"] if i["type"] == "transfer")
    assert t2["receive"]["id"] == recv["id"] and t2["receive"]["source_id"] == b.id


def test_facets_show_what_the_other_filters_leave(two_sources, authed):
    """With "income" chosen only DOT had any: the coin list can dim the rest; the kinds name
    each kind of income (Vanixxx, 2026-10-08)."""
    f = authed.get("/api/merged/facets", params={"kind": "income"}).json()
    assert f["assets"] == ["DOT"]
    assert (
        "income:staking" in f["kinds"] and "transfer" in f["kinds"]
    )  # kinds ignore their own filter
    staking = _items(authed, kind="income:staking")["items"]
    assert [i["row"]["incoming"][0] for i in staking] == ["DOT"]
    assert _items(authed, kind="income:airdrop")["items"] == []


def test_filter_by_origin(two_sources, authed):
    """API, file, chain or by hand (Vanixxx, 2026-10-09); a correction counts as where its
    original came from."""
    files = _items(authed, origin="file")["items"]
    assert files and len(files) == len(_items(authed)["items"])
    assert _items(authed, origin="manual,api")["items"] == []
    hbar = next(
        i["row"] for i in files if i["type"] == "row" and i["row"]["incoming"] == ["HBAR", "7302"]
    )
    authed.post(
        f"/api/sources/{hbar['source_id']}/manual",
        json={
            "kind": "receive",
            "time": "2025-02-01T10:00:00",
            "incoming_asset": "SOL",
            "incoming_amount": "1",
        },
    )
    assert [i["row"]["incoming"][0] for i in _items(authed, origin="manual")["items"]] == ["SOL"]


def test_a_transfer_cannot_link_two_coins(two_sources, authed, db):
    """BCH out, USD in is a transfer plus a trade (Cryptex, Vanixxx 2026-10-11)."""
    from app.modules.raw.models import RawTransaction

    send = db.query(RawTransaction).filter_by(kind="send").first()
    src = authed.post("/api/sources", json={"provider": "manual", "label": "Elsewhere"}).json()[
        "id"
    ]
    got = authed.post(
        f"/api/sources/{src}/manual",
        json={
            "kind": "receive",
            "time": "2025-01-22T13:00",
            "incoming_asset": "USD",
            "incoming_amount": "1000",
        },
    ).json()
    r = authed.post("/api/merged/link", json={"send_id": send.id, "receive_id": got["id"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "merged.asset_mismatch"


def test_split_halves_stay_single_until_linked_by_hand(two_sources, authed, db):
    from app.modules.raw import service as raw

    # a second receive that would fit the same send too, a little later
    raw.import_movements(
        db,
        two_sources[1],
        "file",
        "b2",
        [
            Movement(
                timestamp=T + timedelta(minutes=40),
                kind=Kind.RECEIVE,
                incoming_asset="ETH",
                incoming_amount=Decimal("0.995"),
            )
        ],
    )
    # two receives fit: nothing is linked on a guess; Vanixxx links one, then splits it again
    rows = [i["row"] for i in _items(authed)["items"] if i["type"] == "row"]
    send = next(r for r in rows if r["outgoing"] == ["ETH", "1"])
    first = next(r for r in rows if r["incoming"] == ["ETH", "0.9937"])
    pair = {"send_id": send["id"], "receive_id": first["id"]}
    assert authed.post("/api/merged/link", json=pair).status_code == 204
    assert authed.post("/api/merged/split", json=pair).status_code == 204
    # the next run must not pair the send with the other receive behind Vanixxx's back
    after = _items(authed)
    assert after["summary"]["transfers"] == 0
    other = next(
        i["row"]["id"]
        for i in after["items"]
        if i["type"] == "row"
        and i["row"]["kind"] == "receive"
        and i["row"]["id"] != pair["receive_id"]
        and i["row"]["incoming"] == ["ETH", "0.995"]
    )
    # linking by hand still works
    link = {"send_id": pair["send_id"], "receive_id": other}
    assert authed.post("/api/merged/link", json=link).status_code == 204
    assert _items(authed)["summary"]["transfers"] == 1

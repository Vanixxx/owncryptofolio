"""Cosmos SDK chains through their public REST (LCD) endpoints (2026-10-23).

One reader for every chain of the family; a plugin per chain only names its chain.

* **Transactions** by event search: `transfer.sender='me'` and `transfer.recipient='me'`
  (`/cosmos/tx/v1beta1/txs?query=…`, 100 per page by `pagination.offset`, newest first so an
  incremental fetch can stop early). Both queries, merged by hash: every coin the account
  sends, receives, pays as fee or collects as reward is one `transfer` event.
* **Fee:** the first `transfer` of a transaction without `msg_index` that leaves the fee
  payer for the fee amount (the ante handler's); the payer's `fee_pay`/`tx.fee` names it.
* **Staking is not a movement:** delegating, undelegating and redelegating move coins between
  the account and the pools without a `transfer` event, so nothing is booked. Delegated and
  unbonding coins stay part of the balance (`balance` adds them), which is why the check
  needs no event for the end of an unbonding. A `transfer` to me from the distribution module
  inside a staking message is a **reward**: income (staking).
* **IBC coins** (`ibc/HASH`) are resolved to their base denom
  (`/ibc/apps/transfer/v1/denom_traces`).
  A base denom with a `u` prefix has six decimals (`uatom` → ATOM); anything else is not read
  and said so, never guessed.
* Not read: pending (unclaimed) rewards, slashing, authz and feegrant paid by others beyond
  the fee payer, tokens of other denom kinds (factory, CW20).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

from app.modules.plugins import chain
from app.modules.plugins.contract import IncomeKind, Kind, Movement

PAGE = 100
DECIMALS = 6
COIN = re.compile(r"^(\d+)(.+)$")
REWARD_ACTIONS = (
    "MsgDelegate",
    "MsgUndelegate",
    "MsgBeginRedelegate",
    "MsgCancelUnbondingDelegation",
    "MsgWithdrawDelegatorReward",
    "MsgWithdrawValidatorCommission",
)
KNOWN = {"uatom": "ATOM", "uosmo": "OSMO", "utia": "TIA", "uusdc": "USDC", "uakt": "AKT"}


@dataclass(frozen=True)
class Chain:
    asset: str
    denom: str
    servers: tuple[str, ...]


class Client:
    def __init__(self, spec: Chain) -> None:
        self.spec = spec
        self.traces: dict[str, str | None] = {}

    def get(self, path: str, base: str | None = None):
        """From `base`, else from the first server that answers."""
        last: Exception | None = None
        for server in (base,) if base else self.spec.servers:
            try:
                return chain.http_json(f"{server}{path}")
            except chain.ChainUnavailable as exc:
                last = exc
        raise last or chain.ChainUnavailable("no answer")

    def base_denom(self, denom: str) -> str | None:
        if not denom.startswith("ibc/"):
            return denom
        if denom not in self.traces:
            # no answer is an error, not an unknown coin: dropping it would lose the coin and
            # shift the numbering of the transaction's other coins (review 2026-10-24)
            trace = (self.get(f"/ibc/apps/transfer/v1/denom_traces/{quote(denom[4:])}") or {}).get(
                "denom_trace"
            ) or {}
            self.traces[denom] = trace.get("base_denom")
        return self.traces[denom]

    def coin(self, amount: str, denom: str) -> tuple[str, Decimal] | None:
        """(asset, amount) or None for a denom that is not read."""
        base = self.base_denom(denom)
        if not base:
            return None
        if base == self.spec.denom:
            return self.spec.asset, chain.units(amount, DECIMALS)
        if base in KNOWN:
            return KNOWN[base], chain.units(amount, DECIMALS)
        if re.fullmatch(r"u[a-z]{2,10}", base):
            return base[1:].upper(), chain.units(amount, DECIMALS)
        return None


def search(client: Client, address: str, cutoff: datetime | None) -> list[dict]:
    """Transactions with a transfer from or to the address, merged by hash.

    Public nodes keep different stretches of history (and a load-balanced name answers from
    whichever node it likes): every server is asked and what they found is joined. One that
    does not answer is left out; none answering is an error."""
    found: dict[str, dict] = {}
    answered = False
    last: Exception | None = None
    # a server that stops in the middle of the pages leaves a gap: fine only if another
    # server read that side to the end (review 2026-10-24)
    complete: set[str] = set()
    broken: set[str] = set()
    for server in client.spec.servers:
        for side in ("sender", "recipient"):
            offset = 0
            while True:
                query = quote(f"transfer.{side}='{address}'")
                try:
                    page = client.get(
                        f"/cosmos/tx/v1beta1/txs?query={query}&order_by=ORDER_BY_DESC"
                        f"&pagination.limit={PAGE}&pagination.offset={offset}",
                        base=server,
                    )
                except chain.ChainUnavailable as exc:
                    last = exc
                    if offset:
                        broken.add(side)
                    break
                responses = (page or {}).get("tx_responses")
                txs = (page or {}).get("txs")
                if not isinstance(responses, list) or not isinstance(txs, list):
                    last = chain.ChainUnavailable("invalid answer")
                    if offset:
                        broken.add(side)
                    break
                answered = True
                for r, t in zip(responses, txs, strict=False):
                    found[r["txhash"]] = {"response": r, "tx": t}
                offset += len(responses)
                oldest = min((_time(r) for r in responses), default=None)
                if len(responses) < PAGE or (cutoff and oldest and oldest < cutoff):
                    complete.add(side)
                    break
    if not answered:
        raise last or chain.ChainUnavailable("no answer")
    if broken - complete:
        raise chain.ChainUnavailable("history broke off in the middle")
    return sorted(found.values(), key=lambda x: _time(x["response"]))


def _time(response: dict) -> datetime:
    return datetime.fromisoformat(response["timestamp"].replace("Z", "+00:00"))


def _attrs(event: dict) -> dict[str, str]:
    return {a["key"]: a.get("value") for a in event.get("attributes") or []}


def _coins(text: str) -> list[tuple[str, str]]:
    out = []
    for part in (text or "").split(","):
        m = COIN.match(part.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def convert(me: str, items: list[dict], client: Client) -> list[Movement]:
    out: list[Movement] = []
    for item in items:
        r, t = item["response"], item["tx"]
        # a failed transaction carries only its fee events: read like any other
        events = r.get("events") or []
        when = _time(r)
        messages = [
            m.get("@type", "").rsplit(".", 1)[-1]
            for m in (t.get("body") or {}).get("messages") or []
        ]
        # the fee the transaction names (the fee_pay event can show another, split, figure)
        fee_text = ",".join(
            f"{c['amount']}{c['denom']}"
            for c in ((t.get("auth_info") or {}).get("fee") or {}).get("amount") or []
        )
        fee_paid = False
        paid_fee: tuple[str, Decimal] | None = None
        n = 0
        transfers = [_attrs(e) for e in events if e["type"] == "transfer"]
        for a in transfers:
            sender, receiver = a.get("sender"), a.get("recipient")
            index = a.get("msg_index")
            for amount, denom in _coins(a.get("amount") or ""):
                coin = client.coin(amount, denom)
                if coin is None:
                    continue
                n += 1
                base = {"timestamp": when, "external_id": f"{r['txhash']}:{n}", "raw": a}
                if (
                    index is None
                    and sender == me
                    and not fee_paid
                    and f"{amount}{denom}" in fee_text
                ):
                    fee_paid = True
                    paid_fee = coin
                    continue  # the fee, booked below
                if sender == me or receiver == me:
                    message = (
                        messages[int(index)]
                        if index is not None and int(index) < len(messages)
                        else None
                    )
                    if receiver == me and sender != me and message in REWARD_ACTIONS:
                        out.append(
                            Movement(
                                kind=Kind.INCOME,
                                income_kind=IncomeKind.STAKING,
                                incoming_asset=coin[0],
                                incoming_amount=coin[1],
                                counterparty=sender,
                                comment="staking rewards",
                                **base,
                            )
                        )
                        continue
                    out.append(
                        chain.transfer(
                            sent=sender == me,
                            received=receiver == me,
                            asset=coin[0],
                            amount=coin[1],
                            sender=sender,
                            receiver=receiver,
                            **base,
                        )
                    )
        if paid_fee:
            fee_asset, fee_amount = paid_fee
            # onto the first send of the transaction, else a fee of its own
            first = next(
                (
                    i
                    for i, m in enumerate(out)
                    if m.external_id.startswith(r["txhash"]) and m.kind == Kind.SEND
                ),
                None,
            )
            if first is not None and out[first].outgoing_asset == fee_asset:
                out[first] = out[first].model_copy(
                    update={"fee_asset": fee_asset, "fee_amount": fee_amount}
                )
            else:
                out.append(
                    Movement(
                        kind=Kind.FEE,
                        fee_asset=fee_asset,
                        fee_amount=fee_amount,
                        comment=", ".join(messages) or None,
                        timestamp=when,
                        external_id=f"{r['txhash']}:fee",
                        raw={"fee": fee_text},
                    )
                )
    out.sort(key=lambda m: m.timestamp)
    return out


def fetch(
    spec: Chain,
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
) -> Iterator[Movement]:
    client = Client(spec)
    cutoff = since - timedelta(days=1) if since else None
    items = search(client, address, cutoff)
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(items)})
    yield from chain.since_only(convert(address, items, client), since)


def balance(spec: Chain, address: str) -> list:
    """Liquid + delegated + unbonding, per denom the reader knows."""
    client = Client(spec)
    totals: dict[str, Decimal] = {}

    def add(denom: str, amount: str | int) -> None:
        coin = client.coin(str(amount), denom)
        if coin and Decimal(coin[1]) != 0:
            totals[coin[0]] = totals.get(coin[0], Decimal(0)) + coin[1]

    for c in (
        client.get(f"/cosmos/bank/v1beta1/balances/{address}?pagination.limit=200") or {}
    ).get("balances") or []:
        add(c["denom"], c["amount"])
    for d in (
        client.get(f"/cosmos/staking/v1beta1/delegations/{address}?pagination.limit=200") or {}
    ).get("delegation_responses") or []:
        add(
            (d.get("balance") or {}).get("denom") or spec.denom,
            (d.get("balance") or {}).get("amount") or 0,
        )
    for u in (
        client.get(
            f"/cosmos/staking/v1beta1/delegators/{address}/unbonding_delegations?pagination.limit=200"
        )
        or {}
    ).get("unbonding_responses") or []:
        for e in u.get("entries") or []:
            add(spec.denom, e.get("balance") or 0)
    totals.setdefault(spec.asset, Decimal(0))
    return [("spot", asset, amount) for asset, amount in totals.items()]


def now() -> datetime:
    return datetime.now(UTC)

"""A small read-only JSON API (ADR 0050): the same reading functions as MCP, by plain HTTP.

For a widget on the phone, a Home Assistant sensor, a spreadsheet, an automation. One URL per
reading tool, `GET /api/v1/<name>?<params>`, with the same tokens as MCP (header
`Authorization: Bearer …`) and its own switch `api.enabled`. Answers are masked like the MCP
ones; every call is logged. Nothing here writes.
"""

import inspect
import logging
import time
from datetime import UTC, datetime
from functools import cache
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ValidationError, create_model

from app.core.errors import AppError
from app.modules.mcp import server, service

router = APIRouter(prefix="/api/v1", tags=["api"])
log = logging.getLogger("api")


def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    plain = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    with server._db() as db:
        from app.modules.settings import service as settings_service

        enabled = settings_service.all_settings(db)["api.enabled"]
        row = service.verify(db, plain, "api")
        name = row.name if row else None
    if name is None:
        raise AppError("api.token_invalid", 401)
    if not enabled:
        raise AppError("api.off", 403)
    return name


@cache
def _params(name: str) -> type[BaseModel]:
    """The query parameters of a tool, read from its signature (the session left out)."""
    fn = server.READERS[name]
    fields: dict[str, Any] = {}
    for p in list(inspect.signature(fn).parameters.values())[1:]:
        fields[p.name] = (p.annotation, ... if p.default is inspect.Parameter.empty else p.default)
    return create_model(f"{name}_params", **fields)


def _describe(name: str) -> dict:
    fn = server.READERS[name]
    schema = _params(name).model_json_schema()
    return {
        "path": f"/api/v1/{name}",
        "description": inspect.cleandoc(fn.__doc__ or ""),
        "params": {
            k: {x: v[x] for x in ("type", "description", "default", "anyOf") if x in v}
            for k, v in schema.get("properties", {}).items()
        },
    }


@router.get("")
def index(request: Request) -> dict:
    """What the API offers: every endpoint with its description and parameters."""
    _token(request)
    return {"endpoints": [_describe(n) for n in sorted(server.READERS)]}


@router.get("/{name}")
def call(name: str, request: Request) -> Any:
    who = _token(request)
    if name not in server.READERS:
        raise AppError("api.unknown", 404, name=name)
    started = time.monotonic()
    status = "error"
    args = dict(request.query_params)
    try:
        try:
            values = _params(name).model_validate(args).model_dump()
        except ValidationError as exc:
            raise AppError(
                "api.invalid_params", 400, reason=str(exc).splitlines()[0][:200]
            ) from exc
        with server._db() as db:
            out = server.clean(server.READERS[name](db, **values))
        status = "ok"
        return out
    except AppError as exc:
        status = exc.code
        raise
    finally:
        service.last_call.update(tool=f"api {name}", token=who, at=datetime.now(UTC).isoformat())
        log.info(
            "api=%s client=%s args=%s status=%s ms=%d",
            name, who, args, status, int((time.monotonic() - started) * 1000),
        )  # fmt: skip

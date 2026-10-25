import logging
import platform
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.bootstrap.migrate import revisions
from app.core import logs
from app.core.config import get_settings
from app.core.db import get_engine, get_session
from app.core.version import app_version
from app.modules.system import service

router = APIRouter(prefix="/api/system", tags=["system"])
browser = logging.getLogger("frontend")


@router.get("/status")
def status(request: Request, db: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    boot = request.app.state.boot
    current, head = revisions(get_engine(), settings.database_url)
    server = db.execute(text("SHOW server_version")).scalar()
    name = db.execute(text("SELECT current_database()")).scalar()
    started = request.app.state.started_at
    return {
        "version": app_version(),
        "started_at": started.isoformat(),
        "uptime_seconds": int((datetime.now(UTC) - started).total_seconds()),
        "python": platform.python_version(),
        "database": {
            "connected": True,
            "name": name,
            "server_version": server,
            "created_on_start": boot.database_created,
        },
        "migration": {"current": current, "head": head, "up_to_date": current == head},
        "data_dir": str(settings.data_dir),
        "keys": boot.keys.sources,
        "operations": service.operations(db),
    }


@router.get("/backup-key")
def backup_key(request: Request) -> dict:
    return {"backup_key": request.app.state.boot.keys.backup_key}


@router.get("/logs")
def log_lines(after: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=2000)) -> dict:
    """The log lines after `after` (ADR 0047): the page asks every few seconds."""
    return {"lines": logs.ring.since(after, limit), "last": logs.ring.seq, "level": logs.level()}


class ClientLine(BaseModel):
    level: str = Field(pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    message: str = Field(max_length=4000)
    page: str | None = Field(None, max_length=300)


@router.post("/logs/client", status_code=204)
def client_lines(lines: list[ClientLine] = Body(..., max_length=50)) -> None:
    """What went wrong in the browser, in the same log as the backend's lines."""
    for x in lines:
        browser.log(
            logging.getLevelName(x.level), "%s%s", x.message, f" ({x.page})" if x.page else ""
        )

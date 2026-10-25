"""Upload, show and remove own logos."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import AppError
from app.modules.logos import service, site_icons

router = APIRouter(prefix="/api/logos", tags=["logos"])


@router.get("")
def listing(db: Session = Depends(get_session)) -> list[dict]:
    return service.listing(db)


@router.get("/site/{provider}")
async def site_icon(provider: str) -> Response:
    """An exchange's website icon, fetched by this installation itself (not shipped)."""
    path = await run_in_threadpool(site_icons.fetch, provider)
    if path is None:
        raise AppError("logos.not_found", 404)
    headers = {"Cache-Control": "private, max-age=604800", "X-Content-Type-Options": "nosniff"}
    if path.suffix == ".svg":
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
    return Response(path.read_bytes(), media_type=site_icons.media_type(path), headers=headers)


@router.get("/{kind}/{key}")
def show(kind: str, key: str, db: Session = Depends(get_session)) -> Response:
    row = service.get(db, kind, key)
    headers = {
        "Cache-Control": "private, max-age=31536000, immutable",  # the URL carries ?v=
        "X-Content-Type-Options": "nosniff",
    }
    if row.mime == "image/svg+xml":
        # an uploaded SVG may carry a script: opened on its own it runs nothing. Only for
        # SVG: some browsers refuse to show raster images with this header (2026-10-05)
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
    return Response(row.data, media_type=row.mime, headers=headers)


@router.put("/{kind}/{key}", status_code=204)
async def upload(
    kind: str, key: str, file: UploadFile = File(...), db: Session = Depends(get_session)
) -> None:
    data = await file.read(service.MAX_BYTES + 1)
    service.store(db, kind, key, data)


@router.delete("/{kind}/{key}", status_code=204)
def remove(kind: str, key: str, db: Session = Depends(get_session)) -> None:
    service.remove(db, kind, key)

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.jobs import service
from app.modules.jobs.models import Job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobIn(BaseModel):
    kind: str
    source_id: int | None = None


@router.get("")
def list_jobs(db: Session = Depends(get_session)) -> list[dict]:
    jobs = db.scalars(select(Job).order_by(Job.id.desc()).limit(50))
    return [service.job_dict(j) for j in jobs]


@router.post("", status_code=201)
def create(body: JobIn, db: Session = Depends(get_session)) -> dict:
    if body.kind == "fetch" and body.source_id is None:
        from app.core.errors import AppError

        raise AppError("jobs.source_required", 400)
    return service.job_dict(service.enqueue(db, body.kind, body.source_id))

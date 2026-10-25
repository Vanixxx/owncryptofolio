from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.plugins.registry import registry
from app.modules.sources import service, services

router = APIRouter(prefix="/api", tags=["sources"])


class SourceIn(BaseModel):
    provider: str
    label: str
    address: str | None = None
    wallet_id: int | None = None


class WalletIn(BaseModel):
    name: str


@router.get("/plugins")
def plugins() -> dict:
    return {"providers": service.providers(), "errors": registry().errors}


@router.get("/sources")
def list_sources(db: Session = Depends(get_session)) -> list[dict]:
    return service.overview(db)


@router.post("/sources", status_code=201)
def create(body: SourceIn, db: Session = Depends(get_session)) -> dict:
    s = service.create(db, body.provider, body.label, body.address, body.wallet_id)
    return {"id": s.id}


@router.delete("/sources/{source_id}", status_code=204)
def delete(source_id: int, db: Session = Depends(get_session)) -> None:
    service.delete_source(db, source_id)


@router.put("/sources/{source_id}/credentials", status_code=204)
def set_credentials(source_id: int, body: dict[str, str], db: Session = Depends(get_session)):
    service.set_credentials(db, source_id, body)


@router.get("/sources/alerts")
def alerts(db: Session = Depends(get_session)) -> list[dict]:
    return service.alerts(db)


@router.delete("/sources/{source_id}/credentials", status_code=204)
def delete_credentials(source_id: int, db: Session = Depends(get_session)) -> None:
    service.delete_credentials(db, source_id)


@router.post("/sources/{source_id}/check")
def check(source_id: int, db: Session = Depends(get_session)) -> dict:
    s = service.check_credentials(db, source_id)
    return {"ok": s.last_check_ok, "message": s.last_check_message}


@router.get("/wallets")
def list_wallets(db: Session = Depends(get_session)) -> list[dict]:
    return service.wallets(db)


@router.post("/wallets", status_code=201)
def create_wallet(body: WalletIn, db: Session = Depends(get_session)) -> dict:
    w = service.create_wallet(db, body.name)
    return {"id": w.id, "name": w.name}


@router.patch("/wallets/{wallet_id}")
def rename_wallet(wallet_id: int, body: WalletIn, db: Session = Depends(get_session)) -> dict:
    w = service.rename_wallet(db, wallet_id, body.name)
    return {"id": w.id, "name": w.name}


@router.delete("/wallets/{wallet_id}", status_code=204)
def delete_wallet(wallet_id: int, db: Session = Depends(get_session)) -> None:
    service.delete_wallet(db, wallet_id)


class ServiceKeyIn(BaseModel):
    key: str


class AutoFetchIn(BaseModel):
    auto_fetch: bool


@router.get("/service-keys")
def list_service_keys(db: Session = Depends(get_session)) -> list[dict]:
    return services.overview(db)


@router.put("/service-keys/{service_name}", status_code=204)
def set_service_key(service_name: str, body: ServiceKeyIn, db: Session = Depends(get_session)):
    services.store(db, service_name, body.key)


@router.delete("/service-keys/{service_name}", status_code=204)
def delete_service_key(service_name: str, db: Session = Depends(get_session)) -> None:
    services.remove(db, service_name)


@router.patch("/sources/{source_id}", status_code=204)
def set_auto_fetch(source_id: int, body: AutoFetchIn, db: Session = Depends(get_session)) -> None:
    source = service.get(db, source_id)
    source.auto_fetch = body.auto_fetch
    db.commit()

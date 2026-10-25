"""Errors the UI can translate: a stable code plus parameters, never prose (ADR 0026)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, status: int = 400, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.params = params


def error_body(code: str, **params: Any) -> dict[str, Any]:
    return {"error": {"code": code, "params": params}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, **exc.params), status_code=exc.status)

    from sqlalchemy.exc import OperationalError

    @app.exception_handler(OperationalError)
    async def _db_gone(_: Request, exc: OperationalError) -> JSONResponse:
        # the database went away while the app runs: a clear answer instead of a 500
        return JSONResponse(error_body("db.unavailable"), status_code=503)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()]
        return JSONResponse(error_body("request.invalid", fields=fields), status_code=422)

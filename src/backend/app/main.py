import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.routing import Route

from app.bootstrap.database import BootstrapError
from app.bootstrap.run import run_bootstrap
from app.core import logs
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import AppError, install_error_handlers
from app.core.version import app_version
from app.modules.auth import service as auth_service
from app.modules.auth.api import router as auth_router
from app.modules.auth.middleware import install_auth_guard
from app.modules.backup.api import router as backup_router
from app.modules.backup.schedule import schedule_loop
from app.modules.balances.api import router as balances_router
from app.modules.export.api import router as export_router
from app.modules.health.api import router as health_router
from app.modules.imports.api import router as imports_router
from app.modules.jobs import service as jobs_service
from app.modules.jobs.api import router as jobs_router
from app.modules.jobs.runners import register_all
from app.modules.logos.api import router as logos_router
from app.modules.manual.api import router as manual_router
from app.modules.mcp import server as mcp_server
from app.modules.mcp.api import router as mcp_router
from app.modules.mcp.rest import router as api_v1_router
from app.modules.merged.api import router as merged_router
from app.modules.portfolio.api import router as portfolio_router
from app.modules.prices.api import router as prices_router
from app.modules.raw.api import router as raw_router
from app.modules.settings import service as settings_service
from app.modules.settings.api import router as settings_router
from app.modules.sources.api import router as sources_router
from app.modules.stats.api import router as stats_router
from app.modules.system.api import router as system_router
from app.modules.tax.api import router as tax_router

log = logging.getLogger("owncryptofolio")

# Core modules are listed here on purpose: a visible list, not auto-discovery (ADR 0016).
ROUTERS = (
    health_router,
    auth_router,
    settings_router,
    system_router,
    sources_router,
    imports_router,
    balances_router,
    manual_router,
    merged_router,
    logos_router,
    portfolio_router,
    export_router,
    prices_router,
    raw_router,
    jobs_router,
    backup_router,
    tax_router,
    stats_router,
    mcp_router,
    api_v1_router,
)


BOOT_FIRST_WAIT = 5.0
NO_CACHE = {"Cache-Control": "no-cache"}  # a newly chosen icon shows at once
BOOT_RETRY_SECONDS = 10.0


def _finish_boot(app: FastAPI, boot) -> None:
    """Everything that needs the database, once it is there."""
    with Session(get_engine()) as db:
        app.state.setup_done = auth_service.is_set_up(db)
        logs.set_level(settings_service.all_settings(db)["system.log_level"])
    app.state.boot = boot
    if not app.state.setup_done and boot.setup_code:
        log.warning("=" * 60)
        log.warning("First start: open the web UI and enter the setup code  %s", boot.setup_code)
        log.warning("=" * 60)
    app.state.ready = True


def _start_workers(app: FastAPI, stop: asyncio.Event) -> list:
    if not get_settings().background_workers:
        return []
    with Session(get_engine()) as db:
        if n := jobs_service.recover_interrupted(db):
            log.warning("%d job(s) were interrupted by the last shutdown", n)
    return [
        asyncio.create_task(jobs_service.worker_loop(stop)),
        asyncio.create_task(schedule_loop(stop)),
    ]


async def _boot_when_reachable(app: FastAPI, stop: asyncio.Event, tasks: list) -> None:
    """The database was not there at start (after a power cut it comes up later): the web
    page already answers "no database" and this keeps trying until it can start
    (Vanixxx, 2026-10-15)."""
    while not stop.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=BOOT_RETRY_SECONDS)
        if stop.is_set():
            return
        try:
            boot = await asyncio.to_thread(run_bootstrap, get_settings(), BOOT_FIRST_WAIT)
        except BootstrapError as exc:
            log.warning("Database still not reachable: %s", exc)
            continue
        _finish_boot(app, boot)
        tasks.extend(_start_workers(app, stop))
        log.info("owncryptofolio %s ready (database came back)", app_version())
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.started_at = datetime.now(UTC)
    app.state.ready = False
    app.state.setup_done = False
    register_all()
    stop = asyncio.Event()
    tasks: list = []
    try:
        boot = run_bootstrap(settings, min(settings.db_wait_seconds, BOOT_FIRST_WAIT))
    except BootstrapError as exc:
        log.error("Database not reachable, the web page says so and the app keeps trying: %s", exc)
        tasks.append(asyncio.create_task(_boot_when_reachable(app, stop, tasks)))
    else:
        _finish_boot(app, boot)
        tasks.extend(_start_workers(app, stop))
        log.info("owncryptofolio %s ready", app_version())
    # the MCP server's request handling runs for the app's lifetime (ADR 0049)
    async with app.state.mcp.session_manager.run():
        yield
    stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    get_engine().dispose()


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    logs.install()
    app = FastAPI(title="owncryptofolio", version=app_version(), lifespan=lifespan)
    app.state.failure_delay = 1.0  # fixed delay instead of lockouts (ADR 0023)
    install_error_handlers(app)
    install_auth_guard(app)
    for router in ROUTERS:
        app.include_router(router)
    # Claude through MCP (ADR 0049): its own token check, not the web login
    app.state.mcp, gateway = mcp_server.build(app)
    app.router.routes.append(Route("/mcp", endpoint=gateway, methods=["GET", "POST", "DELETE"]))
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    dist = get_settings().frontend_dist
    if not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    def icon() -> str:
        """The home screen icon chosen in the settings (Vanixxx, 2026-10-21), E5 by default."""
        from app.modules.settings import service as settings_service
        from app.modules.settings.registry import ICONS

        if app.state.ready:
            with Session(get_engine()) as db:
                chosen = settings_service.all_settings(db)["appearance.icon"]
                if chosen in ICONS:
                    return chosen
        return "E5"

    # iOS asks for these when a page is added to the home screen
    @app.get("/apple-touch-icon.png", include_in_schema=False)
    @app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    def touch_icon():
        return FileResponse(dist / "app-icons" / f"{icon()}-180.png", headers=NO_CACHE)

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        name = icon()
        return JSONResponse(
            {
                "name": "owncryptofolio",
                "short_name": "owncryptofolio",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#0b1418",
                "theme_color": "#0b1418",
                "icons": [
                    {"src": f"/app-icons/{name}-{s}.png", "sizes": f"{s}x{s}", "type": "image/png"}
                    for s in (192, 512)
                ],
            },
            media_type="application/manifest+json",
            headers=NO_CACHE,
        )

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise AppError("not_found", 404)
        # Unknown paths return index.html so reloading a sub page works (ADR 0016).
        file = (dist / path).resolve()
        if path and file.is_file() and dist.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(dist / "index.html")


app = create_app()

"""Registers the job kinds. Kept separate so jobs/service.py knows no module."""

from app.modules.backup import service as backup
from app.modules.jobs import service
from app.modules.jobs.fetch import run_fetch


def _backup(session, job, progress):
    progress({"step": "backup"})
    run = backup.run_backup(session, "manual")
    if run.status != "done":
        raise RuntimeError(run.message or "backup failed")
    return backup.run_dict(run)


def _prices(session, job, progress):
    from app.modules.prices import service as prices

    return prices.run_all(session, progress)


def _fine(session, job, progress):
    """Fine prices, then the fine portfolio values computed from them (ADR 0044)."""
    from app.modules.portfolio import fine as portfolio_fine
    from app.modules.prices import fine

    result = fine.fetch(session, progress=progress)
    result["values"] = portfolio_fine.rebuild(session)
    return result


def register_all() -> None:
    service.register("fetch", run_fetch)
    service.register("backup", _backup)
    service.register("prices", _prices)
    service.register("fine", _fine)

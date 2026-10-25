"""First-start step 1 and 2: wait for PostgreSQL, create the target database if missing."""

import logging
import time

import psycopg
from psycopg import errors, sql
from sqlalchemy.engine import make_url

log = logging.getLogger(__name__)


class BootstrapError(RuntimeError):
    """A first-start step failed; the message tells the operator what to do."""


def _conninfo(database_url: str, database: str | None = None) -> tuple[str, str]:
    url = make_url(database_url)
    target = url.database or "postgres"
    plain = url.set(drivername="postgresql", database=database or target)
    return plain.render_as_string(hide_password=False), target


def ensure_database(database_url: str, wait_seconds: float = 60.0) -> bool:
    """Wait until the server answers; create the database if it does not exist.

    Returns True when the database was created by this call.
    """
    conninfo, target = _conninfo(database_url)
    deadline = time.monotonic() + wait_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            with psycopg.connect(conninfo, connect_timeout=5):
                return False
        except psycopg.OperationalError as exc:
            if _database_missing(exc):
                _create_database(database_url, target)
                return True
            if time.monotonic() >= deadline:
                raise BootstrapError(
                    f"Database server not reachable after {wait_seconds:.0f}s: {_first_line(exc)}"
                ) from exc
            log.info("Waiting for database (attempt %d): %s", attempt, _first_line(exc))
            time.sleep(min(2.0, max(0.1, deadline - time.monotonic())))


def _database_missing(exc: psycopg.OperationalError) -> bool:
    # Connection-time errors carry no sqlstate; the server message is the only signal.
    return "does not exist" in str(exc) and "database" in str(exc)


def _create_database(database_url: str, target: str) -> None:
    maintenance, _ = _conninfo(database_url, "postgres")
    log.warning("Database %r does not exist, creating it", target)
    try:
        with psycopg.connect(maintenance, autocommit=True, connect_timeout=5) as conn:
            conn.execute(
                sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(target)
                )
            )
    except errors.InsufficientPrivilege as exc:
        raise BootstrapError(
            f"Database {target!r} is missing and the user may not create it. "
            f"Grant CREATEDB or run once: CREATE DATABASE \"{target}\" ENCODING 'UTF8';"
        ) from exc
    except errors.DuplicateDatabase:
        log.info("Database %r was created concurrently", target)


def _first_line(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__

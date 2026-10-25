"""Guards the raw layer against delete and update (ADR 0001, ADR 0021).

On 2026-08-30 an ad-hoc script emptied the old raw table. A rule that only
lives in a document is no rule. Both paths are covered:

- ORM path: `session.delete(obj)` and changed attributes, caught in `before_flush`.
- Bulk path: `query(...).delete()` / `execute(delete(...))` bypass `before_flush`
  but fire `do_orm_execute` — measured, also for Core table statements.

Exempt: databases with `_test` in their *name* (fixtures must clean up), and
deliberate maintenance inside `raw_unlocked("<reason>")`. Raw SQL and
`TRUNCATE` bypass the ORM and are not caught; database rights or triggers would
be the next step and were rejected as over-engineering (ADR 0021).
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session


class RawLayerProtected(RuntimeError):
    """A delete or update of raw rows was refused."""


# ContextVar, not threading.local: async endpoints share a thread, a thread-local
# unlock inside an `await` could leak to a concurrent request.
_unlocked: contextvars.ContextVar[bool] = contextvars.ContextVar("raw_unlocked", default=False)


@contextmanager
def raw_unlocked(reason: str) -> Iterator[None]:
    if not reason or not reason.strip():
        raise ValueError("raw_unlocked requires a reason")
    token = _unlocked.set(True)
    try:
        yield
    finally:
        _unlocked.reset(token)


def is_test_database(session: Session) -> bool:
    bind = session.get_bind()
    engine = getattr(bind, "engine", bind)
    # The database *name*, not the whole URL: a user "app_test_ro" must not
    # switch the guard off on a production database.
    return "_test" in (engine.url.database or "")


def _protected(session: Session) -> bool:
    return not _unlocked.get() and not is_test_database(session)


def _refuse(action: str, count: int) -> None:
    raise RawLayerProtected(
        f"{action} of {count} raw row(s) refused (ADR 0001). "
        'Wrap deliberate maintenance in raw_unlocked("<reason>").'
    )


_active = False


def activate(cls: type) -> None:
    global _active
    if _active:
        return
    _active = True
    table = cls.__table__.name

    @event.listens_for(Session, "before_flush")
    def _before_flush(session: Session, *_: object) -> None:
        if not _protected(session):
            return
        deleted = [o for o in session.deleted if isinstance(o, cls)]
        if deleted:
            _refuse("Delete", len(deleted))
        changed = [o for o in session.dirty if isinstance(o, cls) and session.is_modified(o)]
        if changed:
            _refuse("Update", len(changed))

    @event.listens_for(Session, "do_orm_execute")
    def _bulk(state: ORMExecuteState) -> None:
        if not (state.is_delete or state.is_update):
            return
        target = getattr(state.statement, "table", None)
        if target is None or target.name != table or not _protected(state.session):
            return
        _refuse("Bulk delete" if state.is_delete else "Bulk update", 1)

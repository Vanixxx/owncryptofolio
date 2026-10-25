"""Decisions follow a transaction to its new version (Vanixxx, 2026-10-06).

They are anchored on fingerprints, and an edit or a reset makes another raw row the valid
one, with another fingerprint: without this, editing half of a transfer linked by hand
dropped the link, an attached fee fell off, a spam mark was lost. The old version keeps its
decisions too (it is history); a decision already there for the new one is replaced.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.merged.models import (
    NotDustMark,
    OpenSendMark,
    SpamMark,
    TransferDecision,
    TransferExtra,
    TxNote,
)


def carry(session: Session, old_fp: str, new_fp: str) -> None:
    if old_fp == new_fp:
        return
    for d in list(
        session.scalars(
            select(TransferDecision).where(
                (TransferDecision.send_fp == old_fp) | (TransferDecision.receive_fp == old_fp)
            )
        )
    ):
        send = new_fp if d.send_fp == old_fp else d.send_fp
        receive = new_fp if d.receive_fp == old_fp else d.receive_fp
        session.execute(
            delete(TransferDecision).where(
                TransferDecision.send_fp == send, TransferDecision.receive_fp == receive
            )
        )
        session.add(TransferDecision(send_fp=send, receive_fp=receive, decision=d.decision))
    mark = session.get(OpenSendMark, old_fp)
    if mark is not None:
        session.execute(delete(OpenSendMark).where(OpenSendMark.send_fp == new_fp))
        session.add(OpenSendMark(send_fp=new_fp, mark=mark.mark, note=mark.note))
    if session.get(SpamMark, old_fp) is not None and session.get(SpamMark, new_fp) is None:
        session.add(SpamMark(fingerprint=new_fp))
    extra = session.get(TransferExtra, old_fp)
    if extra is not None:
        session.execute(delete(TransferExtra).where(TransferExtra.extra_fp == new_fp))
        session.add(TransferExtra(extra_fp=new_fp, send_fp=extra.send_fp))
    if session.get(NotDustMark, old_fp) is not None and session.get(NotDustMark, new_fp) is None:
        session.add(NotDustMark(fingerprint=new_fp))
    note = session.get(TxNote, old_fp)
    if note is not None and session.get(TxNote, new_fp) is None:
        session.add(TxNote(fingerprint=new_fp, text=note.text))
    # an extra belongs to one send: it moves along with the send
    for e in session.scalars(select(TransferExtra).where(TransferExtra.send_fp == old_fp)):
        e.send_fp = new_fp
    session.flush()

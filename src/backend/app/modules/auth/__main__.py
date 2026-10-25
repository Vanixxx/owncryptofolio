"""A forgotten password, on the server's command line (Vanixxx, 2026-10-23).

    docker exec -it owncryptofolio python -m app.modules.auth reset-password

Whoever may run commands in the container owns the server anyway; the web interface offers
no way around the password. The new one is asked twice and never shown.
"""

import argparse
import getpass
import sys

from app.core.db import _session_factory
from app.core.errors import AppError
from app.modules import models  # noqa: F401
from app.modules.auth import service


def main(argv: list[str] | None = None, ask=getpass.getpass) -> int:
    p = argparse.ArgumentParser(prog="python -m app.modules.auth")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reset-password", help="set a new password for the web interface")
    p.parse_args(argv)
    first = ask("New password: ")
    if first != ask("Repeat it: "):
        print("The passwords do not match; nothing changed.", file=sys.stderr)
        return 1
    with _session_factory()() as session:
        try:
            service.set_password(session, first)
        except AppError as exc:
            print(f"Not changed: {exc.code} {exc.params or ''}".strip(), file=sys.stderr)
            return 1
    print("Password changed. Sign in with the new one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

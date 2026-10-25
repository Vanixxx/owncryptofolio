"""Backup on the command line — the emergency path when the app does not start.

python -m app.modules.backup run [--no-probe]
python -m app.modules.backup restore FILE --database NAME [--replace]
python -m app.modules.backup export FILE        # decrypted level-2 export to stdout
"""

import argparse
import sys
from pathlib import Path

from app.bootstrap.keys import load_or_create_keys
from app.core.config import get_settings
from app.core.db import _session_factory
from app.core.keys import set_keys
from app.modules import models  # noqa: F401
from app.modules.backup import service


def main() -> int:
    p = argparse.ArgumentParser(prog="python -m app.modules.backup")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--no-probe", action="store_true")
    rs = sub.add_parser("restore")
    rs.add_argument("file", type=Path)
    rs.add_argument("--database", required=True)
    rs.add_argument("--replace", action="store_true")
    ex = sub.add_parser("export")
    ex.add_argument("file", type=Path)
    args = p.parse_args()

    s = get_settings()
    set_keys(
        load_or_create_keys(
            s.data_dir, {n: getattr(s, n) for n in ("credentials_key", "session_key", "backup_key")}
        )
    )
    if args.cmd == "run":
        with _session_factory()() as session:
            run = service.run_backup(session, "manual", with_probe=not args.no_probe)
        print(
            f"{run.status}: {run.dump_file} {run.export_file} rows={run.rows} "
            f"probe={run.probe_ok} {run.message or ''}"
        )
        return 0 if run.status == "done" else 1
    if args.cmd == "restore":
        service.restore(args.file, args.database, replace=args.replace)
        print(f"restored into {args.database}")
        return 0
    for line in service.read_export(args.file):
        sys.stdout.write(f"{line}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

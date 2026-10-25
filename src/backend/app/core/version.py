"""The displayed version comes from git, never maintained by hand (ADR 0009)."""

import os
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache
def app_version() -> str:
    if env := os.environ.get("APP_VERSION"):
        return env
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
        return out.stdout.strip().removeprefix("v") or "0.0.0-dev"
    except (OSError, subprocess.SubprocessError):
        return "0.0.0-dev"

"""Process-wide access to the keys loaded by the first-start chain (ADR 0030)."""

from app.bootstrap.keys import Keys

_keys: Keys | None = None


def set_keys(keys: Keys) -> None:
    global _keys
    _keys = keys


def get_keys() -> Keys:
    if _keys is None:
        raise RuntimeError("keys not loaded; run the bootstrap first")
    return _keys

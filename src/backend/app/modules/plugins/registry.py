"""Discovers plugins: every folder in integrations/ with a plugin.toml (ADR 0003).

Drop a folder in, restart, it is there — no core change. A plugin that fails to
load is reported, not fatal: one broken plugin must not take the sources page
down with it (lesson from the old register, which was all-or-nothing).
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType

from app.modules.plugins.manifest import Channel, Manifest

log = logging.getLogger(__name__)
INTEGRATIONS_DIR = Path(__file__).resolve().parents[3] / "integrations"


@dataclass(frozen=True)
class Plugin:
    key: str  # folder name, e.g. "bitget_api"
    manifest: Manifest
    module: ModuleType

    @property
    def provider(self) -> str:
        return self.manifest.source.provider

    @property
    def channel(self) -> Channel:
        return self.manifest.source.channel


@dataclass(frozen=True)
class Registry:
    plugins: dict[str, Plugin]
    errors: dict[str, str]

    def for_provider(self, provider: str) -> list[Plugin]:
        return [p for p in self.plugins.values() if p.provider == provider]

    def find(self, provider: str, channel: Channel) -> Plugin | None:
        return next((p for p in self.for_provider(provider) if p.channel is channel), None)


def discover(directory: Path = INTEGRATIONS_DIR, package: str = "integrations") -> Registry:
    plugins: dict[str, Plugin] = {}
    errors: dict[str, str] = {}
    for folder in sorted(p for p in directory.iterdir() if (p / "plugin.toml").exists()):
        try:
            manifest = Manifest.load(folder / "plugin.toml")
            module = importlib.import_module(f"{package}.{folder.name}.reader")
            plugins[folder.name] = Plugin(folder.name, manifest, module)
        except Exception as exc:  # noqa: BLE001 — any plugin failure is reported, not fatal
            errors[folder.name] = f"{type(exc).__name__}: {exc}"
            log.error("Plugin %s failed to load: %s", folder.name, exc)
    _expand(plugins, errors)
    return Registry(plugins, errors)


def _expand(plugins: dict[str, Plugin], errors: dict[str, str]) -> None:
    """A plugin with `expand()` stands for many sources (ccxt: one per exchange, ADR 0048).
    An exchange with its own plugin for that channel keeps it."""
    for key, template in [(k, p) for k, p in plugins.items() if hasattr(p.module, "expand")]:
        del plugins[key]
        own = {(p.provider, p.channel) for p in plugins.values()}
        try:
            for provider, manifest, module in template.module.expand(template.manifest):
                if (provider, manifest.source.channel) not in own:
                    plugins[f"{key}:{provider}"] = Plugin(f"{key}:{provider}", manifest, module)
        except Exception as exc:  # noqa: BLE001 — as above: reported, not fatal
            errors[key] = f"{type(exc).__name__}: {exc}"
            log.error("Plugin %s failed to expand: %s", key, exc)


@lru_cache
def registry() -> Registry:
    return discover()

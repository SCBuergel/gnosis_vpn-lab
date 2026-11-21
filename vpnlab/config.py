"""Paths and the pinned configuration from lab.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"  # keys, identities, passwords, tokens (never committed)
STATE = ROOT / "state"  # inventory, addresses, transaction journal (never committed)
RAW = ROOT / "raw"  # raw logs and counters (never committed)
CACHE = ROOT / "cache"  # downloaded tools (never committed)
RESULTS = ROOT / "results"  # small, committed summaries
REMOTE = ROOT / "remote"
TEMPLATES = ROOT / "templates"

EXIT = "exit"
CLIENT = "client"


@dataclass(frozen=True)
class Config:
    data: dict[str, Any]

    @property
    def lab(self) -> dict[str, Any]:
        return self.data["lab"]

    @property
    def name(self) -> str:
        return self.lab["name"]

    @property
    def relays(self) -> list[str]:
        return list(self.lab["relays"])

    @property
    def hoprd_nodes(self) -> list[str]:
        return [*self.relays, EXIT]

    @property
    def machines(self) -> list[str]:
        return [*self.relays, EXIT, CLIENT]

    @property
    def provider_name(self) -> str:
        return self.lab["provider"]

    @property
    def provider(self) -> dict[str, Any]:
        return self.data["providers"][self.provider_name]

    @property
    def funding(self) -> dict[str, Any]:
        return self.data["funding"]

    def software(self, name: str) -> dict[str, Any]:
        return self.data["software"][name]


def load_config(path: Path = ROOT / "lab.toml") -> Config:
    config = Config(tomllib.loads(path.read_text()))
    if config.provider_name not in config.data.get("providers", {}):
        raise ValueError(f"lab.provider = {config.provider_name!r} has no [providers.{config.provider_name}] section")
    if len(set(config.machines)) != len(config.machines):
        raise ValueError("machine names must be unique; 'exit' and 'client' are reserved")
    return config


def expand(path: str) -> Path:
    return Path(path).expanduser()

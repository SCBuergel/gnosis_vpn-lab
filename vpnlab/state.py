"""Per-deployment state files under state/ and secrets/, always private (0600 in 0700 directories)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import SECRETS, STATE


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_private(path: Path, text: str) -> None:
    private_dir(path.parent)
    tmp = path.with_name(path.name + ".tmp")
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
    tmp.replace(path)


def read_json(name: str, default: Any = None) -> Any:
    path = STATE / name
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(name: str, value: Any) -> None:
    write_private(STATE / name, json.dumps(value, indent=1) + "\n")


def inventory() -> dict[str, dict[str, Any]]:
    """Machine name -> {id, public, private, ...} as the provider reported it."""
    return read_json("inventory.json", {})


def nodes() -> dict[str, dict[str, str]]:
    """Machine name -> {address, peer, ...}: public identifiers of the HOPR nodes."""
    return read_json("nodes.json", {})


def safes() -> dict[str, dict[str, str]]:
    """hoprd node name -> {safe, module}."""
    return read_json("safes.json", {})


def identity_dir(name: str) -> Path:
    return private_dir(SECRETS / "identities" / name)


def secret(name: str, filename: str) -> str:
    return (identity_dir(name) / filename).read_text().strip()

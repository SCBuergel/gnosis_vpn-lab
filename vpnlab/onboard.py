"""On-chain onboarding of the hoprd nodes with hopli: identities and Safes."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import subprocess
import urllib.request
from pathlib import Path

from . import state
from .config import CACHE, RAW, Config

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def ensure_hopli(config: Config) -> Path:
    """Download the pinned hopli once and verify its hash."""
    pin = config.software("hopli")
    path = CACHE / f"hopli-{pin['version']}"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        with urllib.request.urlopen(pin["url"], timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != pin["sha256"]:
            raise RuntimeError("hopli download does not match its pinned SHA-256")
        path.write_bytes(data)
        path.chmod(0o755)
    elif hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
        raise RuntimeError(f"{path} does not match its pinned SHA-256")
    return path


def parse_identity(output: str) -> dict[str, str]:
    """Public identifiers from `hopli identity read` output."""
    text = ANSI.sub("", output)
    address = re.search(r"Identity addresses: \[(0x[0-9a-fA-F]{40})\]", text)
    peer = re.search(r"Identity peerids: \[(\w+)\]", text)
    packet_key = re.search(r"packet_key: \(priv_key: <REDACTED>, pub_key: (0x[0-9a-f]{64})", text)
    if not (address and peer and packet_key):
        raise RuntimeError("could not read the identity's public identifiers from hopli's output")
    return {"address": address.group(1).lower(), "peer": peer.group(1), "packet_key": packet_key.group(1)}


def identity_file(name: str) -> Path:
    files = sorted(state.identity_dir(name).glob("*.id"))
    if len(files) != 1:
        raise RuntimeError(f"expected exactly one identity file for {name}, found {len(files)}")
    return files[0]


def create_identity(config: Config, name: str) -> dict[str, str]:
    """Create the node's identity locally (so it is backed up before any funds move); idempotent."""
    hopli = ensure_hopli(config)
    directory = state.identity_dir(name)
    password = directory / "password"
    if not password.exists():
        state.write_private(password, secrets.token_urlsafe(30))
    if not (directory / "api-token").exists():
        state.write_private(directory / "api-token", secrets.token_urlsafe(24))
    common = ["-d", str(directory), "-x", name, "-p", str(password)]
    if not list(directory.glob("*.id")):
        subprocess.run([hopli, "identity", "create", *common, "-n", "1"], check=True, capture_output=True)
    read = subprocess.run([hopli, "identity", "read", *common], check=True, capture_output=True, text=True)
    return parse_identity(read.stdout + read.stderr)


def parse_safe(output: str) -> dict[str, str]:
    text = ANSI.sub("", output)
    safe = re.search(r"^safe (0x[0-9a-fA-F]{40})$", text, re.M)
    module = re.search(r"^node_module (0x[0-9a-fA-F]{40})$", text, re.M)
    if not (safe and module):
        raise RuntimeError("hopli did not report a Safe and module address")
    return {"safe": safe.group(1), "module": module.group(1)}


def create_safe(config: Config, name: str, owner: str, deployer_key: str) -> dict[str, str]:
    """Deploy one Safe and node module for the node, owned by `owner`. The deployer key only pays gas."""
    hopli = ensure_hopli(config)
    directory = state.identity_dir(name)
    command = [
        str(hopli), "safe-module", "create",
        "--network", config.lab["network"],
        "--provider-url", config.lab["rpc_url"],
        "-d", str(directory), "-x", name, "-p", str(directory / "password"),
        "--admin-address", owner,
        "--allowance", "100000",
    ]  # fmt: skip
    # The key goes through the environment: command-line arguments are visible to every local process.
    completed = subprocess.run(
        command, env={**os.environ, "PRIVATE_KEY": deployer_key}, capture_output=True, text=True, timeout=600
    )
    log = RAW / "onboarding" / f"safe-{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(ANSI.sub("", completed.stdout + completed.stderr))
    if completed.returncode != 0:
        raise RuntimeError(f"hopli safe-module create failed for {name}; see {log}")
    return parse_safe(completed.stdout + completed.stderr)

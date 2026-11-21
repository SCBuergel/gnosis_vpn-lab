"""SSH to the lab machines through a generated config (state/ssh_config); host aliases are lab-<name>."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import state
from .config import CLIENT, SECRETS, STATE, Config

SSH_CONFIG = STATE / "ssh_config"
KEY = SECRETS / "keys" / "lab_ed25519"
CLIENT_PRIVATE = "client-priv"  # the client through the first relay, over the private network


def ensure_key() -> str:
    """Create the lab SSH key once and return its public half."""
    state.private_dir(KEY.parent)
    if not KEY.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "vpn-lab", "-f", str(KEY)], check=True)
    return KEY.with_suffix(".pub").read_text().strip()


def render_config(inventory: dict[str, dict], jump: str) -> str:
    common = (
        "  User root\n"
        f"  IdentityFile {KEY}\n"
        "  IdentitiesOnly yes\n"
        f"  UserKnownHostsFile {STATE / 'known_hosts'}\n"
        "  StrictHostKeyChecking accept-new\n"
        "  ConnectTimeout 15\n"
        "  ServerAliveInterval 20\n"
    )
    blocks = [f"Host lab-{name}\n  HostName {info['public']}\n{common}" for name, info in sorted(inventory.items())]
    if CLIENT in inventory and inventory[CLIENT].get("private"):
        # The VPN's killswitch cuts SSH from public addresses but allows private ranges.
        blocks.append(
            f"Host lab-{CLIENT_PRIVATE}\n  HostName {inventory[CLIENT]['private']}\n  ProxyJump lab-{jump}\n{common}"
        )
    return "\n".join(blocks)


def write_config(config: Config) -> None:
    state.write_private(SSH_CONFIG, render_config(state.inventory(), config.relays[0]))


def run(host: str, command: str, *, check: bool = True, timeout: float = 600, stdin: bytes | None = None) -> str:
    """Run a shell command on lab-<host>; returns stdout. stderr is passed through on failure."""
    completed = subprocess.run(
        ["ssh", "-F", str(SSH_CONFIG), "-o", "BatchMode=yes", f"lab-{host}", command],
        input=stdin,
        capture_output=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        tail = completed.stderr.decode(errors="replace")[-600:]
        raise RuntimeError(f"command on {host} failed ({completed.returncode}): {tail}")
    return completed.stdout.decode(errors="replace")


def fetch(host: str, command: str, destination: Path, *, timeout: float = 600) -> int:
    """Write the raw stdout of a remote command to a local file; returns the byte count.

    The command must print only the wanted bytes: anything else on stdout corrupts the file.
    """
    completed = subprocess.run(
        ["ssh", "-F", str(SSH_CONFIG), "-o", "BatchMode=yes", f"lab-{host}", command],
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"fetch from {host} failed: {completed.stderr.decode(errors='replace')[-400:]}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(completed.stdout)
    return len(completed.stdout)


def upload(host: str, files: dict[str, bytes | Path], directory: str = "/root/lab") -> None:
    """Put files into a private directory on the machine. Values are contents or local paths."""
    run(host, f"mkdir -p {directory} && chmod 700 {directory}")
    for name, content in files.items():
        data = content.read_bytes() if isinstance(content, Path) else content
        run(host, f"umask 077 && cat > {directory}/{name}", stdin=data)

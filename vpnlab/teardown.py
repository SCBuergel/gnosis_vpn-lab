"""Delete the lab's machines, and the timer that does so at a fixed time (a hard billing cap)."""

from __future__ import annotations

import shlex
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import client, ssh, state
from .config import CLIENT, EXIT, ROOT, Config
from .onboard import identity_file
from .providers import Provider

UNIT = "vpn-lab-destroy"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


def missing_identity_backups(config: Config) -> list[str]:
    """Nodes whose keys are not on this machine. Deleting such a machine could strand its funds."""
    missing = []
    for name in config.hoprd_nodes:
        try:
            identity_file(name)
            state.secret(name, "password")
        except (RuntimeError, FileNotFoundError):
            missing.append(name)
    if not client.identity_backed_up():
        missing.append(CLIENT)
    return missing


def backup_payment_state(config: Config, stamp: str) -> dict[str, str]:
    """Best effort: copy the payment-pool state of client and exit. Without it, pool balances are hard to recover."""
    user, network = config.lab["client_user"], config.lab["network"]
    sources = {
        CLIENT: f"tar -C /home/{user}/.local/share/gnosisvpn/networks/{shlex.quote(network)} -cz pix",
        EXIT: "tar -C /var/lib/hoprd -cz curvy-pix.redb",
    }
    outcome = {}
    for name, command in sources.items():
        target = state.identity_dir(name) / f"payment-state-{stamp}.tgz"
        try:
            # The client is reached over the private network: its public SSH is cut while the VPN is connected.
            host = ssh.CLIENT_PRIVATE if name == CLIENT else name
            size = ssh.fetch(host, command, target, timeout=180)
            target.chmod(0o600)
            outcome[name] = f"saved {size} bytes"
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            outcome[name] = f"NOT SAVED: {str(error)[:200]}"
    return outcome


def destroy(config: Config, provider: Provider) -> dict[str, Any]:
    """Delete every machine carrying the lab tag. Refuses while a node's keys are not backed up locally."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    record: dict[str, Any] = {"at": stamp, "deleted": [], "payment_state": {}}
    machines = provider.list(config.name)
    if machines:
        missing = missing_identity_backups(config)
        if missing:
            record["refused"] = f"no local key backup for: {', '.join(missing)}"
            state.write_json("destroy.json", record)
            return record
        record["payment_state"] = backup_payment_state(config, stamp)
    for machine in machines:
        provider.delete(machine, config.name)
        record["deleted"].append(machine.name)
    record["left"] = [machine.name for machine in provider.list(config.name)]
    state.write_json("destroy.json", record)
    return record


def schedule(hours: float) -> datetime:
    """Install a persistent systemd user timer that runs `destroy --yes` at now + hours.

    It fires only while this machine and the user's systemd instance run; with Persistent=true a
    missed time is caught up at the next start.
    """
    when = datetime.now(UTC) + timedelta(hours=hours)
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    (UNIT_DIR / f"{UNIT}.service").write_text(
        "[Unit]\nDescription=Delete the vpn-lab machines (billing cap)\n\n"
        "[Service]\nType=oneshot\n"
        f"WorkingDirectory={ROOT}\n"
        f"ExecStart={sys.executable} -m vpnlab destroy --yes\n"
    )
    (UNIT_DIR / f"{UNIT}.timer").write_text(
        "[Unit]\nDescription=Delete the vpn-lab machines at a fixed time\n\n"
        f"[Timer]\nOnCalendar={when:%Y-%m-%d %H:%M:%S} UTC\nPersistent=true\n\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", f"{UNIT}.timer"], check=True, capture_output=True)
    state.write_json("timer.json", {"destroy_at_utc": when.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return when


def cancel() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", f"{UNIT}.timer"], check=False, capture_output=True)
    for suffix in ("service", "timer"):
        (UNIT_DIR / f"{UNIT}.{suffix}").unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    (state.STATE / "timer.json").unlink(missing_ok=True)


def timer_status() -> str:
    listed = subprocess.run(
        ["systemctl", "--user", "list-timers", f"{UNIT}.timer", "--all", "--no-pager"], capture_output=True, text=True
    )
    return listed.stdout.strip()

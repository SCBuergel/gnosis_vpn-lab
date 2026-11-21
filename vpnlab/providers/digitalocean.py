"""DigitalOcean droplets through the public API (standard library only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import Machine

API_ROOT = "https://api.digitalocean.com/v2/"
PACKAGES = ["curl", "jq", "tmux", "iputils-ping", "nftables", "python3", "chrony"]
READY_MARKER = "/var/lib/vpn-lab-ready"


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"DigitalOcean API {status}: {message}")
        self.status = status


def cloud_config(public_key: str) -> str:
    """cloud-init user data. JSON is valid YAML, so no text templating is needed."""
    config = {
        "ssh_authorized_keys": [public_key],
        # DigitalOcean images force a root password change on first login, which breaks non-interactive SSH.
        "bootcmd": [["sh", "-c", 'chage -d "$(date +%F)" -M 99999 root']],
        "package_update": True,
        "packages": PACKAGES,
        "runcmd": [["systemctl", "enable", "--now", "chrony"], ["touch", READY_MARKER]],
    }
    return "#cloud-config\n" + json.dumps(config, indent=1) + "\n"


def _ipv4(droplet: dict[str, Any], kind: str) -> str | None:
    for network in droplet.get("networks", {}).get("v4", []):
        if network.get("type") == kind:
            return network.get("ip_address")
    return None


def to_machine(droplet: dict[str, Any], tag: str) -> Machine:
    return Machine(
        name=droplet["name"].removeprefix(f"{tag}-"),
        id=str(droplet["id"]),
        public=_ipv4(droplet, "public"),
        private=_ipv4(droplet, "private"),
        status=droplet["status"],
        size=droplet["size_slug"],
        region=droplet["region"]["slug"],
        created=droplet["created_at"],
    )


@dataclass
class DigitalOcean:
    token: str
    region: str
    size: str
    image: str
    timeout_s: float = 90

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> DigitalOcean:
        token = Path(settings["token_file"]).expanduser().read_text().strip()
        return cls(token=token, region=settings["region"], size=settings["size"], image=settings["image"])

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        request = urllib.request.Request(
            API_ROOT + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = response.read()
        except urllib.error.HTTPError as error:
            raise ApiError(error.code, error.read().decode(errors="replace")[:300]) from None
        return json.loads(payload) if payload else None

    def create(self, name: str, tag: str, ssh_public_key: str) -> Machine:
        body = {
            "name": f"{tag}-{name}",
            "region": self.region,
            "size": self.size,
            "image": self.image,
            "user_data": cloud_config(ssh_public_key),
            "tags": [tag],
            "backups": False,
            "ipv6": False,
            "monitoring": False,
        }
        return to_machine(self.request("POST", "droplets", body)["droplet"], tag)

    def list(self, tag: str) -> list[Machine]:
        droplets = self.request("GET", f"droplets?tag_name={tag}&per_page=200")["droplets"]
        return [to_machine(droplet, tag) for droplet in droplets]

    def delete(self, machine: Machine, tag: str) -> None:
        try:
            droplet = self.request("GET", f"droplets/{machine.id}")["droplet"]
        except ApiError as error:
            if error.status == 404:
                return
            raise
        if tag not in droplet.get("tags", []):
            raise RuntimeError(f"droplet {machine.id} lacks tag {tag}; refusing to delete it")
        try:
            self.request("DELETE", f"droplets/{machine.id}")
        except ApiError as error:
            if error.status != 404:
                raise

    def hourly_price(self) -> float | None:
        try:
            sizes = self.request("GET", "sizes?per_page=200")["sizes"]
        except ApiError:
            return None
        for size in sizes:
            if size["slug"] == self.size:
                return float(size["price_hourly"])
        return None

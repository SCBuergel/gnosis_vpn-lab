"""Cloud providers. The lab talks to a provider only through the `Provider` protocol below.

To add one (for example AWS): implement the protocol in a new module, register it in `PROVIDERS`,
and add a `[providers.<name>]` section to lab.toml. See docs/adding-a-provider.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Machine:
    """One virtual machine as the lab needs to know it."""

    name: str  # lab name: relay1, exit, client, ...
    id: str  # the provider's identifier
    public: str | None  # public IPv4; the relays must be reachable on it (9091 TCP and UDP)
    private: str | None  # address on a network shared by all lab machines (used to reach the client)
    status: str
    size: str
    region: str
    created: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Provider(Protocol):
    """What the lab needs from a cloud. Every method acts only on machines carrying the lab tag."""

    def create(self, name: str, tag: str, ssh_public_key: str) -> Machine:
        """Create one machine that accepts root SSH logins with the given key, non-interactively."""

    def list(self, tag: str) -> list[Machine]:
        """All machines with the tag, with their current addresses."""

    def delete(self, machine: Machine, tag: str) -> None:
        """Delete one machine. Must refuse a machine that does not carry the tag."""

    def hourly_price(self) -> float | None:
        """Price of one machine per hour in USD, or None when the provider cannot tell."""


def _digitalocean(settings: dict[str, Any]) -> Provider:
    from .digitalocean import DigitalOcean

    return DigitalOcean.from_settings(settings)


PROVIDERS: dict[str, Callable[[dict[str, Any]], Provider]] = {
    "digitalocean": _digitalocean,
}


def get_provider(name: str, settings: dict[str, Any]) -> Provider:
    if name not in PROVIDERS:
        raise ValueError(f"unknown provider {name!r}; known: {', '.join(sorted(PROVIDERS))}")
    return PROVIDERS[name](settings)

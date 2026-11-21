"""Render node configuration from templates. Pure functions: no network, no files written."""

from __future__ import annotations

from .config import TEMPLATES, Config

LOG_FILTER_RELAY = (
    "info,isahc=error,sea_orm=warn,sqlx=warn,hyper_util=warn,hickory_resolver=warn,"
    "hopr_transport_session=debug,hopr_strategy=debug"
)
LOG_FILTER_EXIT = LOG_FILTER_RELAY + ",hopr_protocol_pix=debug,hopr_session_server_forwarder=debug"
# The planner logs every candidate path set at debug; verify.planner_paths reads those lines.
LOG_FILTER_CLIENT = "info,hopr_transport::path=debug"
PROVING_FILES_DIR = "/usr/local/share/curvy-zk"


def address_bytes(address: str) -> list[int]:
    """An Ethereum address as its 20 byte values, the form hoprd's YAML expects for allowlist entries."""
    digits = address.lower().removeprefix("0x")
    if len(digits) != 40:
        raise ValueError(f"not an Ethereum address: {address!r}")
    return list(bytes.fromhex(digits))


def fill(template: str, values: dict[str, str]) -> str:
    text = (TEMPLATES / template).read_text()
    for key, value in values.items():
        text = text.replace(f"@{key}@", value)
    if "@" in "".join(line.split("#")[0] for line in text.splitlines()):
        raise ValueError(f"template {template} has unfilled placeholders")
    return text


def relay_config(config: Config) -> str:
    return fill("relay.cfg.yaml", {"INDEXER_URL": config.lab["indexer_url"]})


def exit_config(config: Config, relay_addresses: dict[str, str]) -> str:
    """relay_addresses: relay name -> node address; the exit may open channels to these only."""
    lines = [
        f"            - {address_bytes(address)}   # {address.lower()} {name}"
        for name, address in relay_addresses.items()
    ]
    return fill(
        "exit.cfg.yaml",
        {
            "INDEXER_URL": config.lab["indexer_url"],
            "RELAY_COUNT": str(len(relay_addresses)),
            "ALLOWLIST": "\n".join(lines),
        },
    )


def client_config(exit_address: str, relay_addresses: dict[str, str]) -> str:
    return fill(
        "client.toml",
        {
            "EXIT_ADDRESS": exit_address,
            "RELAY_COUNT": str(len(relay_addresses)),
            "RELAY_ADDRESSES": ", ".join(f'"{address}"' for address in relay_addresses.values()),
        },
    )


def hoprd_env(config: Config, *, password: str, api_token: str, safe: str, module: str, public_ip: str | None) -> str:
    """Environment file of a hoprd node. public_ip=None runs the node without publishing an address (the exit)."""
    lines = [
        "HOPRD_IDENTITY=/etc/hoprd/node.id",
        f"HOPRD_PASSWORD={password}",
        "HOPRD_DATA=/var/lib/hoprd",
        "HOPRD_API=1",
        "HOPRD_API_HOST=127.0.0.1",
        "HOPRD_API_PORT=3001",
        f"HOPRD_API_TOKEN={api_token}",
        f"HOPRD_SAFE_ADDRESS={safe}",
        f"HOPRD_MODULE_ADDRESS={module}",
        f"HOPRD_BLOKLI_URL={config.lab['indexer_url']}",
        "RUST_BACKTRACE=1",
    ]
    if public_ip is None:
        lines += [f"CURVY_ZK_KEYS_DIR={PROVING_FILES_DIR}", f"RUST_LOG={LOG_FILTER_EXIT}"]
    else:
        lines += [f"HOPRD_HOST={public_ip}:9091", "HOPRD_ANNOUNCE=1", f"RUST_LOG={LOG_FILTER_RELAY}"]
    return "\n".join(lines) + "\n"

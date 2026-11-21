"""Install released software on the lab machines. All install logic lives in the static scripts under remote/."""

from __future__ import annotations

import shlex

from . import render, ssh, state
from .config import CLIENT, EXIT, REMOTE, Config
from .onboard import identity_file

LAB_DIR = "/root/lab"


def _args(*values: str) -> str:
    return " ".join(shlex.quote(value) for value in values)


def _hoprd_files(config: Config, name: str, node_config: str, public_ip: str | None) -> dict[str, bytes]:
    safe = state.safes()[name]
    env = render.hoprd_env(
        config,
        password=state.secret(name, "password"),
        api_token=state.secret(name, "api-token"),
        safe=safe["safe"],
        module=safe["module"],
        public_ip=public_ip,
    )
    return {
        "hoprd.cfg.yaml": node_config.encode(),
        "hoprd.env": env.encode(),
        "node.id": identity_file(name).read_bytes(),
        "fetch.sh": (REMOTE / "fetch.sh").read_bytes(),
        "install-hoprd.sh": (REMOTE / "install-hoprd.sh").read_bytes(),
    }


def relay_addresses(config: Config) -> dict[str, str]:
    nodes = state.nodes()
    return {name: nodes[name]["address"] for name in config.relays}


def install_relay(config: Config, name: str) -> str:
    """A relay: the released hoprd binary, announcing its public address, opening no channels."""
    public_ip = state.inventory()[name]["public"]
    ssh.upload(name, _hoprd_files(config, name, render.relay_config(config), public_ip), LAB_DIR)
    hoprd, validator = config.software("hoprd"), config.software("hoprd_cfg")
    return ssh.run(
        name,
        f"cd {LAB_DIR}"
        f" && bash fetch.sh {_args(hoprd['url'], hoprd['sha256'], f'{LAB_DIR}/hoprd')}"
        f" && bash fetch.sh {_args(validator['url'], validator['sha256'], f'{LAB_DIR}/hoprd-cfg')}"
        f" && bash install-hoprd.sh {LAB_DIR}/hoprd {LAB_DIR}/hoprd-cfg",
        timeout=900,
    )


def install_exit(config: Config) -> str:
    """The exit: hoprd with exit payments from the published image, no published address, plus the VPN server."""
    files = _hoprd_files(config, EXIT, render.exit_config(config, relay_addresses(config)), None)
    for script in ("extract-exit-hoprd.sh", "install-exit-server.sh", "exit-wg-hooks.sh"):
        files[script] = (REMOTE / script).read_bytes()
    ssh.upload(EXIT, files, LAB_DIR)
    image, server = config.software("hoprd_exit"), config.software("gnosis_vpn_server")
    extract = _args(image["image"], image["sha256"], f"{LAB_DIR}/img", render.PROVING_FILES_DIR)
    return ssh.run(
        EXIT,
        f"cd {LAB_DIR}"
        f" && bash extract-exit-hoprd.sh {extract}"
        f" && bash fetch.sh {_args(server['url'], server['sha256'], f'{LAB_DIR}/gnosis_vpn-server')}"
        # The server unit brings up the session target address that hoprd forwards sessions to.
        f" && bash install-exit-server.sh {LAB_DIR}/gnosis_vpn-server {LAB_DIR}/exit-wg-hooks.sh"
        f" && bash install-hoprd.sh {LAB_DIR}/img/hoprd {LAB_DIR}/img/hoprd-cfg",
        timeout=1800,
    )


def install_client(config: Config) -> str:
    """The client: the released package with the exit pinned and channels restricted to the lab relays."""
    client_config = render.client_config(state.nodes()[EXIT]["address"], relay_addresses(config))
    ssh.upload(
        CLIENT,
        {"client.toml": client_config.encode(), "install-client.sh": (REMOTE / "install-client.sh").read_bytes()},
        LAB_DIR,
    )
    package = config.software("client")
    arguments = _args(
        package["channel"], config.lab["network"], config.lab["indexer_url"], package["url"], package["sha256"],
        package["version"], config.lab["client_user"], render.LOG_FILTER_CLIENT,
    )  # fmt: skip
    return ssh.run(CLIENT, f"cd {LAB_DIR} && bash install-client.sh {arguments}", timeout=1800)

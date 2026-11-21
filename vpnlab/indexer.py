"""Read-only queries to the network's indexer (Blokli, GraphQL)."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from .config import Config


def query(config: Config, text: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"query": text, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        config.lab["indexer_url"].rstrip("/") + "/graphql",
        body,
        {"content-type": "application/json", "user-agent": "vpn-lab"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        answer = json.loads(response.read())
    if answer.get("errors"):
        raise RuntimeError(f"indexer: {answer['errors']}")
    return answer["data"]


def chain_info(config: Config) -> dict[str, Any]:
    fields = "blockNumber network ticketPrice minTicketWinningProbability keyBindingFee finality"
    return query(config, f"{{ chainInfo {{ ... on ChainInfo {{ {fields} }} }} }}")["chainInfo"]


def account(config: Config, address: str) -> dict[str, Any] | None:
    """The on-chain account (key binding) of a node address, or None when it has none."""
    text = (
        "query($c:String){ accounts(chainKey:$c){ ... on AccountsList "
        "{ accounts { keyid chainKey packetKey multiAddresses safeAddress } } } }"
    )
    accounts = query(config, text, {"c": address})["accounts"]["accounts"]
    return accounts[0] if accounts else None


def address_of(config: Config, keyid: int) -> str:
    text = "query($k:Int){ accounts(keyid:$k){ ... on AccountsList { accounts { chainKey } } } }"
    return query(config, text, {"k": keyid})["accounts"]["accounts"][0]["chainKey"].lower()


def channels(config: Config, address: str) -> list[dict[str, Any]]:
    """Every channel of a node: [{direction, peer (address), status, balance, ticket_index}]."""
    node = account(config, address)
    if node is None:
        return []
    text = (
        "query($s:Int,$d:Int){ channels(sourceKeyId:$s,destinationKeyId:$d){ ... on ChannelsList "
        "{ channels { source destination balance status ticketIndex } } } }"
    )
    found = []
    for direction, variable, peer_field in (("outgoing", "s", "destination"), ("incoming", "d", "source")):
        for channel in query(config, text, {variable: node["keyid"]})["channels"]["channels"]:
            found.append(
                {
                    "direction": direction,
                    "peer": address_of(config, int(channel[peer_field])),
                    "status": channel["status"],
                    "balance": channel["balance"],
                    "ticket_index": int(channel["ticketIndex"]),
                }
            )
    return found

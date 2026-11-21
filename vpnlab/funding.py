"""Transfers from the funding Safe. Every transfer is journaled before it is broadcast and sent at most once.

This wraps the wallet of gnosis_vpn-bench (`[funding] bench_path`), which needs web3: run the lab with an
interpreter that has it, for example the bench's .venv. Nothing here is imported unless a funding command runs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import state
from .config import SECRETS, STATE, Config, expand

DEPLOYER_KEY = SECRETS / "keys" / "deployer.key"


def _wallet(config: Config) -> Any:
    bench = str(expand(config.funding["bench_path"]))
    if bench not in sys.path:
        sys.path.insert(0, bench)
    try:
        from gvpn_bench.finance import wallet
    except ImportError as error:
        raise SystemExit(f"funding needs the gnosis_vpn-bench checkout at {bench} and web3: {error}") from None
    return wallet


class Funding:
    """One connection to the chain and the funding Safe, with the lab's transaction journal."""

    def __init__(self, config: Config) -> None:
        self.wallet = _wallet(config)
        self.w3 = self.wallet.connect_chain(config.lab["rpc_url"])
        self.source = self.wallet.load_funding_source(expand(config.funding["key_file"]))
        self.token = self.wallet.token_contract(self.w3)
        # The bench journal only needs an object with a `state` directory.
        self.journal = self.wallet.Journal(SimpleNamespace(state=STATE))

    @property
    def owner(self) -> str:
        return self.source.account.address

    def balances(self, address: str) -> dict[str, str]:
        checksum = self.w3.to_checksum_address(address)
        return {
            "xdai": str(self.w3.from_wei(self.w3.eth.get_balance(checksum), "ether")),
            "wxhopr": str(self.w3.from_wei(self.token.functions.balanceOf(checksum).call(), "ether")),
        }

    def source_balances(self) -> dict[str, str]:
        described = self.wallet.describe_source(self.w3, self.source)
        return {key: described[key] for key in ("safe_wxhopr", "safe_xdai", "owner_gas_xdai")}

    def _send(self, purpose: str, **kwargs: Any) -> str:
        self.journal.reconcile(self.w3)
        if self.journal.confirmed(purpose):
            return "already confirmed"
        return self.journal.send(self.w3, self.source.account, purpose, **kwargs)

    def wxhopr(self, to: str, amount: str, purpose: str) -> str:
        """wxHOPR from the funding Safe."""
        from gvpn_bench.finance.chain import WXHOPR_TOKEN

        recipient = self.w3.to_checksum_address(to)
        data = self.token.functions.transfer(recipient, self.w3.to_wei(amount, "ether"))._encode_transaction_data()
        call = self.wallet.safe_call(self.w3, self.source.safe, self.source.account, WXHOPR_TOKEN, data)
        return self._send(purpose, call=call)

    def xdai(self, to: str, amount: str, purpose: str) -> str:
        """xDAI from the funding Safe."""
        recipient = self.w3.to_checksum_address(to)
        value = self.w3.to_wei(amount, "ether")
        call = self.wallet.safe_call(self.w3, self.source.safe, self.source.account, recipient, value=value)
        return self._send(purpose, call=call)

    def xdai_from_owner(self, to: str, amount: str, purpose: str) -> str:
        """xDAI from the funding Safe's owner account (used for the deployer's gas)."""
        return self._send(purpose, to=self.w3.to_checksum_address(to), value=self.w3.to_wei(amount, "ether"))


def deployer_key() -> str:
    """A throwaway key that only pays gas for the Safe deployments. Created once."""
    from eth_account import Account

    if not DEPLOYER_KEY.exists():
        state.write_private(DEPLOYER_KEY, Account.create().key.hex())
    return DEPLOYER_KEY.read_text().strip()


def deployer_address() -> str:
    from eth_account import Account

    return Account.from_key(deployer_key()).address


def journal_entries() -> list[dict[str, Any]]:
    import json

    path: Path = STATE / "transactions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

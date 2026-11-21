"""Throughput through the tunnel: timed downloads run on the client while it is connected."""

from __future__ import annotations

import csv
import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import ssh
from .config import Config

DEFAULT_URL = "https://fsn1-speed.hetzner.com/100MB.bin"  # speed.cloudflare.com refused requests of 100 MB and more
FIELDS = ["started_utc", "url", "bytes", "seconds", "mbit_per_s", "http_code"]


def download(url: str, timeout_s: int = 600) -> dict[str, Any]:
    """One download on the client; curl reports the size, duration and HTTP status."""
    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fmt = '{"bytes": %{size_download}, "seconds": %{time_total}, "http_code": %{http_code}}'
    output = ssh.run(
        ssh.CLIENT_PRIVATE,
        f"curl -s -4 -m {int(timeout_s)} -o /dev/null -w {shlex.quote(fmt)} {shlex.quote(url)}",
        check=False,
        timeout=timeout_s + 60,
    )
    sample = json.loads(output)
    seconds = float(sample["seconds"])
    rate = sample["bytes"] * 8 / seconds / 1e6 if seconds > 0 and sample["http_code"] == 200 else None
    return {
        "started_utc": started,
        "url": url,
        "bytes": int(sample["bytes"]),
        "seconds": round(seconds, 2),
        # A failed download has no rate; it is never reported as zero.
        "mbit_per_s": round(rate, 2) if rate is not None else "",
        "http_code": sample["http_code"],
    }


def append_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerows(rows)


def throughput(config: Config, results_dir: Path, url: str = DEFAULT_URL, count: int = 3) -> list[dict[str, Any]]:
    rows = []
    for _ in range(count):
        row = download(url)
        rows.append(row)
        append_rows(results_dir / "throughput.csv", [row])
    return rows

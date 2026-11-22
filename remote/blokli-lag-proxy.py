#!/usr/bin/env python3
"""Fault injection: a pass-through proxy for Blokli that reports new Curvy notes late.

    blokli-lag-proxy.py LISTEN_HOST PORT UPSTREAM_URL LAG_FILE LOG_FILE ALLOWED_CLIENT

Only requests from the address ALLOWED_CLIENT are served; the proxy listens on a public address.

Every request is forwarded to UPSTREAM_URL unchanged and its answer is streamed back, subscriptions
included. The one exception is the query `curvyNoteStatus`: a note that Blokli knows is reported as
unknown (status 0) until LAG seconds after this proxy first saw Blokli report it as known. LAG is the
number in LAG_FILE, read at every such query; a missing file or 0 means no lag.

A note that is already committed (status 2) the first time it is asked about is never held back. Those
are the pool's older funding notes; holding them back would break payments for a reason no real Blokli
lag produces.

Every note-status query is written to LOG_FILE: time, note, Blokli's status, the status reported.
"""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "host", "content-length",
}  # fmt: skip
UNKNOWN = 0
COMMITTED = 2


class Proxy:
    def __init__(self, upstream: str, lag_file: Path, log_file: Path, allowed_client: str) -> None:
        self.upstream = upstream.rstrip("/")
        self.allowed_client = allowed_client
        self.lag_file = lag_file
        self.log_file = log_file
        self.first_known: dict[str, float] = {}  # note id -> when Blokli first reported it as known
        self.exempt: set[str] = set()
        self.session: ClientSession | None = None

    def lag(self) -> float:
        try:
            return float(self.lag_file.read_text().strip())
        except (OSError, ValueError):
            return 0.0

    def log(self, note: str, real: int, reported: int, lag: float) -> None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        with self.log_file.open("a") as stream:
            stream.write(f"{stamp} note={note} blokli={real} reported={reported} lag_s={lag:g}\n")

    def reported_status(self, note: str, real: int) -> int:
        lag = self.lag()
        reported = real
        if real != UNKNOWN and note not in self.exempt:
            now = time.monotonic()
            if note not in self.first_known and real == COMMITTED:
                self.exempt.add(note)
            else:
                first = self.first_known.setdefault(note, now)
                if now - first < lag:
                    reported = UNKNOWN
        self.log(note, real, reported, lag)
        return reported

    async def handle(self, request: web.Request) -> web.StreamResponse:
        assert self.session is not None
        if request.remote != self.allowed_client:
            return web.Response(status=403, text="not the lab client\n")
        body = await request.read()
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
        url = self.upstream + request.rel_url.raw_path_qs
        note = note_of(body)
        if note is not None:
            headers.pop("Accept-Encoding", None)
        upstream = await self.session.request(request.method, url, headers=headers, data=body or None)
        try:
            out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
            if note is not None:
                raw = await upstream.read()
                out_headers.pop("Content-Encoding", None)
                return web.Response(status=upstream.status, headers=out_headers, body=self.rewrite(note, raw))
            response = web.StreamResponse(status=upstream.status, headers=out_headers)
            await response.prepare(request)
            async for chunk in upstream.content.iter_any():
                await response.write(chunk)
            await response.write_eof()
            return response
        finally:
            upstream.release()

    def rewrite(self, note: str, raw: bytes) -> bytes:
        try:
            answer = json.loads(raw)
            status = answer["data"]["curvyNoteStatus"]
            real = int(status["status"])
        except (ValueError, KeyError, TypeError):
            return raw  # an error answer: pass it on as it is
        reported = self.reported_status(note, real)
        if reported == real:
            return raw
        status["status"] = reported
        return json.dumps(answer).encode()


def note_of(body: bytes) -> str | None:
    """The note id if the request is a curvyNoteStatus query."""
    if b"curvyNoteStatus" not in body:
        return None
    try:
        return str(json.loads(body)["variables"]["noteId"])
    except (ValueError, KeyError, TypeError):
        return None


async def main() -> None:
    host, port, upstream, lag_file, log_file, allowed_client = sys.argv[1:7]
    proxy = Proxy(upstream, Path(lag_file), Path(log_file), allowed_client)
    # auto_decompress off: bodies are passed on byte for byte with their Content-Encoding.
    proxy.session = ClientSession(auto_decompress=False, timeout=ClientTimeout(total=None, sock_connect=15))
    app = web.Application(client_max_size=16 * 1024 * 1024)
    app.router.add_route("*", "/{path:.*}", proxy.handle)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host, int(port)).start()
    print(f"blokli lag proxy listening on {host}:{port}, upstream {proxy.upstream}", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())

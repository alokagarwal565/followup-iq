"""Per-client token buckets for the public demo, which has no login by design.

The Gemini keys are the real cost exposure, so analysis triggers get their own, tighter budget.
State is in memory: correct for the single Render instance this app runs on; multiple instances
would need a shared store such as Redis.
"""

import json
import time
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.errors import error_body

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_MAX_TRACKED_CLIENTS = 10_000


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        writes_per_min: int,
        analyze_per_min: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.limits = {"write": writes_per_min, "analyze": analyze_per_min}
        self.clock = clock
        self.buckets: dict[tuple[str, str], tuple[float, float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        kind = "analyze" if scope["path"].endswith("/analyze") else "write"
        if not self._take(self._client(scope), kind):
            await self._reject(send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _client(scope: Scope) -> str:
        # Behind exactly one trusted proxy (Render), the proxy appends the connecting client's IP
        # as the last X-Forwarded-For entry. Earlier entries come from the client and can be
        # forged, so keying on them would let anyone dodge the limit by varying the header.
        headers: dict[bytes, bytes] = dict(scope["headers"])
        forwarded = headers.get(b"x-forwarded-for", b"").decode("latin-1")
        if forwarded:
            return forwarded.split(",")[-1].strip()
        client = scope.get("client")
        return str(client[0]) if client else "unknown"

    def _take(self, client: str, kind: str) -> bool:
        capacity = float(self.limits[kind])
        now = self.clock()
        if len(self.buckets) > _MAX_TRACKED_CLIENTS:
            self.buckets.clear()
        tokens, updated = self.buckets.get((client, kind), (capacity, now))
        tokens = min(capacity, tokens + (now - updated) * capacity / 60.0)
        if tokens < 1.0:
            self.buckets[(client, kind)] = (tokens, now)
            return False
        self.buckets[(client, kind)] = (tokens - 1.0, now)
        return True

    @staticmethod
    async def _reject(send: Send) -> None:
        body = json.dumps(
            error_body("rate_limited", "Too many requests. Please wait a moment and try again.")
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [(b"content-type", b"application/json"), (b"retry-after", b"10")],
            }
        )
        await send({"type": "http.response.body", "body": body})

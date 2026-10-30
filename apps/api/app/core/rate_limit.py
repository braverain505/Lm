"""Rate limiting for API endpoints — real fixed-window limiter (slowapi).

Endpoints decorate with e.g.::

    @limiter.limit("5/15minutes")
    def login(payload: LoginRequest, request: Request, ...):

and the decorated endpoint MUST take a ``request: Request`` parameter (the
decorator injects the client identity through it). On breach, slowapi raises
``RateLimitExceeded`` which the handler registered in main.py converts to the
standard error envelope with code ``ERR_RATE_LIMITED`` (HTTP 429).

Client identity
---------------
The browser never calls this service directly: it goes through the web app's
``/api/proxy`` route, which forwards the request server-side. The TCP peer of
every request is therefore the proxy, and keying on that address (the slowapi
default) puts every user in a single bucket — a handful of sign-in attempts by
anyone returned 429 "too many attempts" to everybody. ``get_client_ip`` uses
the address the proxy forwards instead, falling back to the socket peer for
direct callers (local dev, health checks).

Forwarded headers are only trustworthy while the API is reachable solely
through the proxy. The per-account failed-login lockout in auth_service is the
backstop if a caller reaches the API directly and spoofs the header.

Storage is the in-process memory backend, which is correct for the current
single-container Render deployment. If the API is ever scaled to multiple
workers/instances, point the limiter at Redis (RATELIMIT_REDIS_URL) — the
memory backend would only limit per-process.
"""
from starlette.requests import Request

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded  # re-exported for main.py
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """The best-known client address, used as the rate-limit key.

    ``X-Forwarded-For`` is a comma-separated hop list whose first entry is the
    original client; ``X-Real-IP`` is the single-address alternative some
    proxies set.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip")
    if real and real.strip():
        return real.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)

__all__ = ["limiter", "RateLimitExceeded", "get_remote_address", "get_client_ip"]

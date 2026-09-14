"""Rate limiting for API endpoints — real fixed-window limiter (slowapi).

Endpoints decorate with e.g.::

    @limiter.limit("5/15minutes")
    def login(payload: LoginRequest, request: Request, ...):

and the decorated endpoint MUST take a ``request: Request`` parameter (the
decorator injects the client identity through it). On breach, slowapi raises
``RateLimitExceeded`` which the handler registered in main.py converts to the
standard error envelope with code ``ERR_RATE_LIMITED`` (HTTP 429).

Storage is the in-process memory backend, which is correct for the current
single-container Render deployment. If the API is ever scaled to multiple
workers/instances, point the limiter at Redis (RATELIMIT_REDIS_URL) — the
memory backend would only limit per-process.
"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded  # re-exported for main.py
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter", "RateLimitExceeded", "get_remote_address"]

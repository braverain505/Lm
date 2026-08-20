"""Rate limiting for API endpoints.

Temporary stub until slowapi is installed.
For production, install slowapi: pip install slowapi

Usage in routers:
    @limiter.limit("5/15minutes")
    def endpoint(...):
        pass
"""


class RateLimiter:
    """Stub rate limiter that does nothing until slowapi is installed."""

    def limit(self, rate: str):
        """Decorator that does nothing (stub for development)."""
        def decorator(func):
            return func
        return decorator


# Initialize rate limiter stub
limiter = RateLimiter()

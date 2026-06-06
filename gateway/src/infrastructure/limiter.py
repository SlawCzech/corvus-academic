"""Rate-limiter dependencies backed by Redis via fastapi-limiter."""

from fastapi_limiter.depends import RateLimiter

login_rate_limit = RateLimiter(times=5, seconds=60)
analysis_rate_limit = RateLimiter(times=10, seconds=60)

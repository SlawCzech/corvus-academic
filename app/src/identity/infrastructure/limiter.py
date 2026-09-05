"""Rate-limiter dependencies using fastapi-limiter 0.2+ (pyrate_limiter backend)."""

from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Rate
from pyrate_limiter import Limiter as PyrateLimiter

_login_limiter = PyrateLimiter(Rate(5, Duration.MINUTE))
_analysis_limiter = PyrateLimiter(Rate(10, Duration.MINUTE))

login_rate_limit = RateLimiter(limiter=_login_limiter)

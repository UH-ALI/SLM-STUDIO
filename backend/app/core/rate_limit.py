import redis
from fastapi import HTTPException, status
from app.core.config import settings

_redis = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def check_rate_limit(key: str, limit: int = 30, window: int = 60):
    """
    Fixed-window rate limiter using Redis.
    Default: 30 requests per 60 seconds per key.
    Reuses the existing Redis instance (Celery broker).

    Fails OPEN if Redis is unreachable — degrades to "no rate limiting"
    during a Redis outage rather than locking every caller out.
    """
    rk = f"rl:{key}"
    try:
        count = _redis.incr(rk)
        if count == 1:
            _redis.expire(rk, window)
        ttl = _redis.ttl(rk)
    except redis.RedisError:
        return

    if count > limit:
        retry_after = ttl if ttl and ttl > 0 else window
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment.",
            headers={"Retry-After": str(retry_after)},
        )


def reset_rate_limit(key: str) -> None:
    """
    Clears the counter for `key`. [NEXT_STEPS.md #2] Used on a successful
    login (so a user who fat-fingered their password once or twice isn't
    left sitting partway to a lockout) and when a fresh password-reset code
    is issued (so requesting a new code — the documented way out of a
    lockout — actually grants a clean set of attempts).
    """
    try:
        _redis.delete(f"rl:{key}")
    except redis.RedisError:
        pass

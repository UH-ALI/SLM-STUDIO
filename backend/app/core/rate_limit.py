import redis
from fastapi import HTTPException, status
from app.core.config import settings

_redis = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def check_rate_limit(key: str, limit: int = 30, window: int = 60):
    """
    Fixed-window rate limiter using Redis.
    Default: 30 requests per 60 seconds per key.
    Reuses the existing Redis instance (Celery broker).
    """
    rk = f"rl:{key}"
    count = _redis.incr(rk)
    if count == 1:
        _redis.expire(rk, window)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment.",
        )

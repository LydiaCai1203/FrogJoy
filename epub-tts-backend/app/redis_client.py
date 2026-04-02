import os
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

pool = redis.ConnectionPool.from_url(REDIS_URL)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=pool)

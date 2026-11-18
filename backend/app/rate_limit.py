# backend/app/rate_limit.py
"""Rate limiting por janela deslizante (Redis quando REDIS_URL configurada; fallback em memória)."""

from collections import defaultdict, deque
import os
from threading import Lock
import time

from fastapi import HTTPException, Request, status

_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()


def reset_rate_limits() -> None:
    """Limpa os contadores em memória (útil em testes automatizados)."""
    with _LOCK:
        _BUCKETS.clear()


async def _check_redis_rate_limit(redis_url: str, key: str, max_requests: int, window_seconds: int) -> bool:
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return False

    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        if count > max_requests:
            ttl = await client.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde antes de tentar novamente.",
                headers={"Retry-After": str(max(1, ttl if ttl and ttl > 0 else window_seconds))},
            )
        return True
    except HTTPException:
        raise
    except Exception:
        return False
    finally:
        await client.aclose()


def rate_limit(max_requests: int, window_seconds: int, key_prefix: str):
    """Dependência FastAPI que limita requisições por IP na janela informada."""

    async def _limiter(request: Request) -> None:
        if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "false":
            return
        client_ip = request.client.host if request.client else "unknown"
        bucket_key = f"rl:{key_prefix}:{client_ip}"

        redis_url = os.getenv("REDIS_URL", "").strip()
        if redis_url:
            handled = await _check_redis_rate_limit(redis_url, bucket_key, max_requests, window_seconds)
            if handled:
                return

        now = time.monotonic()
        cutoff = now - window_seconds

        with _LOCK:
            q = _BUCKETS[bucket_key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - q[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Muitas tentativas. Aguarde antes de tentar novamente.",
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

    return _limiter

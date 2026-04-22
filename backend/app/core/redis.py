import json
import logging

import redis

from app.config import settings

log = logging.getLogger(__name__)

def redis_client() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

def get_cache(key: str) -> dict | None:
    try:
        client = redis_client()
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        log.warning(f"캐시 조회 실패: {e}")
        return None


def set_cache(key: str, value: dict) -> None:
    """TTL 일단 60초 적용"""
    try:
        client = redis_client()
        client.setex(key, settings.CACHE_TTL, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        log.warning(f"캐시 저장 실패: {e}")
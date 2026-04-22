import json
from loguru import logger

import redis.asyncio as aioredis

from app.config import settings

def redis_client() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_cache(key: str) -> dict | None:
    try:
        client = redis_client()
        value = await client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning(f"캐시 조회 실패: {e}")
        return None

async def set_cache(key: str, value: dict) -> None:
    """TTL 일단 60초 적용"""
    try:
        client = redis_client()
        await client.setex(key, settings.CACHE_TTL, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"캐시 저장 실패: {e}")
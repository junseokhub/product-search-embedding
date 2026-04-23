import time
import hashlib
from fastapi import APIRouter, Query
from loguru import logger

from app.core.redis import get_cache, set_cache
from app.core.circuit_breaker import circuit_breaker
from app.schemas.search import SearchResponse, EMPTY_RESPONSE
from app.services.search import search_products

router = APIRouter()

def make_cache_key(query, image_url, site, broadcast_date) -> str:
    raw = f"{query}:{image_url}:{site}:{broadcast_date}"
    return "search:" + hashlib.md5(raw.encode()).hexdigest()


@router.get("/search", response_model=SearchResponse)
async def search(
        query: str | None = Query(None), image_url: str | None = Query(None),
        site: str | None = Query(None), broadcast_date: str | None = Query(None)
):
    start_time = time.time()
    cache_key = make_cache_key(query, image_url, site, broadcast_date)

    cached = await get_cache(cache_key)
    if cached:
        print(f"[캐시 응답] 소요시간: {time.time() - start_time:.3f}s")
        return SearchResponse(**cached)

    if circuit_breaker.check():
        print(f"[Circuit OPEN] 소요시간: {time.time() - start_time:.3f}s")
        return EMPTY_RESPONSE

    try:
        result = await search_products(query, image_url, site, broadcast_date)
        await set_cache(cache_key, result.model_dump())
        print(f"[검색 완료] 소요시간: {time.time() - start_time:.3f}s")
        return result
    except Exception as e:
        logger.error(f"ES 검색 실패: {e}")
        circuit_breaker.record_failure()
        cached = await get_cache(cache_key)
        if cached:
            print(f"[ES 장애 - 캐시 응답] 소요시간: {time.time() - start_time:.3f}s")
            return SearchResponse(**cached)
        print(f"[ES 장애 - 빈 응답] 소요시간: {time.time() - start_time:.3f}s")
        return EMPTY_RESPONSE
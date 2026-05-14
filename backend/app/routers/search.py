import time
import hashlib
from datetime import date
from fastapi import APIRouter, Query, Depends
from loguru import logger
from elasticsearch import AsyncElasticsearch

from app.core.redis import get_cache, set_cache
from app.core.circuit_breaker import circuit_breaker
from app.schemas.search import SearchResponse, EMPTY_RESPONSE
from app.services.search import search_products
from app.core.elasticsearch import elastic_search_client

router = APIRouter()

def make_cache_key(query: str | None, image_url: str | None, site: str | None, broadcast_date: date | None) -> str:
    date_str = broadcast_date.isoformat() if broadcast_date else ""
    raw = f"{query or ''}:{image_url or ''}:{site or ''}:{date_str}"
    return "search:" + hashlib.md5(raw.encode()).hexdigest()


@router.get("/search", response_model=SearchResponse)
async def search(
        es: AsyncElasticsearch = Depends(elastic_search_client),
        query: str | None = Query(None), 
        image_url: str | None = Query(None),
        site: str | None = Query(None), 
        broadcast_date: date | None = Query(None),
):
    start_time = time.time()
    cache_key = make_cache_key(query, image_url, site, broadcast_date)

    try:
        cached = await get_cache(cache_key)
        if cached:
            logger.info(f"[캐시 응답] 소요시간: {time.time() - start_time:.3f}s")
            return SearchResponse(**cached)
    except Exception as ce:
        logger.warning(f"Redis 조회 실패 (무시하고 진행): {ce}")

    if circuit_breaker.check():
        logger.warning(f"[Circuit OPEN] 소요시간: {time.time() - start_time:.3f}s")
        return EMPTY_RESPONSE

    try:
        result = await search_products(es, query, image_url, site, broadcast_date)
    except Exception as e:
        logger.error(f"ES 검색 실패: {e}")
        circuit_breaker.record_failure()
        
        try:
            cached = await get_cache(cache_key)
            if cached:
                logger.info(f"[ES 장애 - 캐시 응답] 소요시간: {time.time() - start_time:.3f}s")
                return SearchResponse(**cached)
        except Exception:
            pass

        logger.error(f"[ES 장애 - 빈 응답] 소요시간: {time.time() - start_time:.3f}s")
        return EMPTY_RESPONSE

    try:
        await set_cache(cache_key, result.model_dump())
    except Exception as ce:
        logger.error(f"Redis 저장 실패: {ce}")

    logger.info(f"[검색 완료] 소요시간: {time.time() - start_time:.3f}s")
    return result
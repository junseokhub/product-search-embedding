import time
import hashlib
import asyncio
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


# Redis 저장이 실패했을 때 백그라운드에서 로그를 남기기 위한 안전장치 함수
async def safe_set_cache(key: str, value: dict):
    try:
        await set_cache(key, value)
    except Exception as ce:
        logger.error(f"Redis 백그라운드 저장 실패: {ce}")


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

    # 1. 빠른 캐시 조회 (Redis 장애 시 무시하고 진행)
    try:
        cached = await get_cache(cache_key)
        if cached:
            logger.info(f"[캐시 응답] 소요시간: {time.time() - start_time:.3f}s")
            return SearchResponse(**cached)
    except Exception as ce:
        logger.warning(f"Redis 조회 실패 (무시하고 진행): {ce}")

    # 2. 서킷 브레이커 체크 (외부 서비스 장애 확산 방지)
    if circuit_breaker.check():
        logger.warning(f"[Circuit OPEN] 소요시간: {time.time() - start_time:.3f}s")
        return EMPTY_RESPONSE

    # 3. 메인 검색 로직 및 예외 처리
    try:
        # [성공 흐름] ES 검색 성공
        result = await search_products(es, query, image_url, site, broadcast_date)
        
        # [수정] Redis 저장을 기다리지 않고 백그라운드로 던져서 응답 속도를 극대화합니다.
        asyncio.create_task(safe_set_cache(cache_key, result.model_dump()))

        logger.info(f"[검색 완료] 소요시간: {time.time() - start_time:.3f}s")
        return result

    except Exception as e:
        # [실패 흐름] ES 검색 실패 시 폴백(Fallback) 처리
        logger.error(f"ES 검색 실패: {e}")
        circuit_breaker.record_failure()
        
        # 메인 검색은 실패했지만, 혹시 그사이 캐시가 생겼는지 한 번 더 확인 (Stale 캐시 응답용)
        try:
            cached = await get_cache(cache_key)
            if cached:
                logger.info(f"[ES 장애 - 캐시 응답] 소요시간: {time.time() - start_time:.3f}s")
                return SearchResponse(**cached)
        except Exception:
            pass

        # 캐시도 없다면 최종 빈 응답 반환
        logger.error(f"[ES 장애 - 빈 응답] 소요시간: {time.time() - start_time:.3f}s")
        return EMPTY_RESPONSE

from elasticsearch import AsyncElasticsearch
from app.config import  settings
from app.core.es_mapping import INDEX_MAPPING, INDEX_NAME
from loguru import logger

def elastic_search_client() -> AsyncElasticsearch:
    return AsyncElasticsearch(settings.ELASTICSEARCH_URL)

async def create_index():
    """인덱스 생성"""
    async with elastic_search_client() as es:
        if not await es.indices.exists(index=INDEX_NAME):
            await es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
            logger.info(f"인덱스 생성 완료: {INDEX_NAME}")
        else:
            logger.info(f"인덱스 존재: {INDEX_NAME}")

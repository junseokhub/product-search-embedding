from elasticsearch import Elasticsearch
from app.config import  settings
from app.core.es_mapping import INDEX_MAPPING, INDEX_NAME
from loguru import logger

def elastic_search_client() -> Elasticsearch:
    return Elasticsearch(settings.ELASTICSEARCH_URL)


def create_index():
    """인덱스 생성"""
    es = elastic_search_client()
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
        logger.info(f"인덱스 생성 완료: {INDEX_NAME}")
    else:
        logger.info(f"인덱스 존재: {INDEX_NAME}")



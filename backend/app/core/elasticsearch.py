from elasticsearch import Elasticsearch
from app.config import  settings
from app.core.es_mapping import INDEX_MAPPING, INDEX_NAME
import logging

log = logging.getLogger(__name__)

def elastic_search_client() -> Elasticsearch:
    return Elasticsearch(settings.ELASTICSEARCH_URL)


def create_index():
    """인덱스 생성"""
    es = elastic_search_client()
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
        log.info(f"인덱스 생성 완료: {INDEX_NAME}")
    else:
        log.info(f"인덱스 존재: {INDEX_NAME}")



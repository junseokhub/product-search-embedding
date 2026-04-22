import asyncio
from app.core.elasticsearch import elastic_search_client
from app.core.es_query import (
    build_filters,
    build_text_query,
    build_image_query,
    build_hybrid_query,
    build_aggregations
)
from app.core.es_mapping import INDEX_NAME
from app.embedding.clip import embedding
from app.schemas.search import SearchResponse, ProductResult, Aggregations


def _parse_results(hits: list) -> list[ProductResult]:
    """ES 검색 결과를 ProductResult 리스트로 변환"""
    results = []
    for hit in hits:
        src = hit["_source"]
        results.append(ProductResult(
            product_name=src["name"],
            site=src["site"],
            price=src["price"],
            broadcast_date=src["broadcast_date"],
            broadcast_time=src.get("broadcast_time"),
            image_url=src.get("image_url"),
            score=hit["_score"] or 0.0
        ))
    return results


def _parse_aggregations(aggs: dict) -> Aggregations:
    """ES 집계 결과 Aggregations로 변환"""
    site_counts = {
        bucket["key"]: bucket["doc_count"]
        for bucket in aggs["site_counts"]["buckets"]
    }
    return Aggregations(
        min_price=int(aggs["min_price"]["value"] or 0),
        max_price=int(aggs["max_price"]["value"] or 0),
        site_counts=site_counts
    )


async def search_products(query: str | None, image_url: str | None, site: str | None, broadcast_date: str | None) -> SearchResponse:
    """검색 타입에 따라 텍스트,이미지,hybrid 검색"""
    es = elastic_search_client()
    filters = build_filters(site, broadcast_date)
    loop = asyncio.get_running_loop()

    if query and image_url:
        text_vector = await loop.run_in_executor(None, embedding.embed_text, query)
        image_vector = await embedding.embed_image_from_url(image_url)
        es_query = build_hybrid_query(text_vector, query, image_vector, filters)
    elif query:
        text_vector = await loop.run_in_executor(None, embedding.embed_text, query)
        es_query = build_text_query(text_vector, query, filters)
    elif image_url:
        image_vector = await embedding.embed_image_from_url(image_url)
        es_query = build_image_query(image_vector, filters)
    else:
        return SearchResponse(total=0, results=[], aggregations=Aggregations())

    es_query["aggs"] = build_aggregations()

    async with elastic_search_client() as es:
        response = await es.search(index=INDEX_NAME, body=es_query)

    hits = response["hits"]["hits"]
    aggs = response["aggregations"]

    return SearchResponse(
        total=response["hits"]["total"]["value"],
        results=_parse_results(hits),
        aggregations=_parse_aggregations(aggs)
    )
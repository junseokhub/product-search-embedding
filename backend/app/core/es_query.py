def build_filters(site: str | None, broadcast_date: str | None) -> list:
    filters = []
    if site:
        filters.append(
            {
                "term": {
                    "site": site
                }
            })
    if broadcast_date:
        filters.append(
            {
                "term": {
                    "broadcast_date": broadcast_date
                }
            })
    return filters

def build_text_query(vector: list[float], query: str, filters: list) -> dict:
    """
    BM25, KNN을 합친텍스트 검색 쿼리
    이유 README.md 기록
    """
    return {
        "query": {
            "bool": {
                "should": [
                    {"match": {"name": {"query": query, "boost": 0.5}}}
                ],
                "filter": filters
            }
        },
        "knn": {
            "field": "name_vector",
            "query_vector": vector,
            "k": 50,
            "num_candidates": 100,
            "boost": 0.5,
            "filter": filters
        }
    }

def build_image_query(vector: list[float], filters: list) -> dict:
    """이미지 기반 쿼리"""
    return {
        "knn": {
            "field": "image_vector",
            "query_vector": vector,
            "k": 50,
            "num_candidates": 100,
            "filter": filters
        }
    }

def build_hybrid_query(text_vector: list[float], query: str, image_vector: list[float], filters: list) -> dict:
    """둘다 입력된 경우, hybrid 쿼리"""
    return {
        "query": {
            "bool": {
                "should": [
                    {"match": {"name": {"query": query, "boost": 0.3}}}
                ],
                "filter": filters
            }
        },
        "knn": [
            {
                "field": "name_vector",
                "query_vector": text_vector,
                "k": 50,
                "num_candidates": 100,
                "boost": 0.4,
                "filter": filters
            },
            {
                "field": "image_vector",
                "query_vector": image_vector,
                "k": 50,
                "num_candidates": 100,
                "boost": 0.3,
                "filter": filters
            }
        ]
    }

def build_aggregations() -> dict:
    """최소가격, 최대가격, 쇼핑사별 집계"""
    return {
        "min_price": {"min": {"field": "price"}},
        "max_price": {"max": {"field": "price"}},
        "site_counts": {"terms": {"field": "site"}}
    }
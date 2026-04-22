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

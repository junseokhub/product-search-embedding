from pydantic import BaseModel
from typing import Optional, Dict, List

class ProductResult(BaseModel):
    product_name: str
    site: str
    price: int
    broadcast_date: str
    broadcast_time: Optional[str] = None
    image_url: Optional[str] = None
    score: float

class Aggregations(BaseModel):
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    site_counts: Dict[str, int] = {}

class SearchResponse(BaseModel):
    total: int
    results: List[ProductResult]
    aggregations: Aggregations

EMPTY_RESPONSE = SearchResponse(total=0, results=[], aggregations=Aggregations())

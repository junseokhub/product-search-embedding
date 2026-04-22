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

# Response format (JSON):
# {
#  "total": 100,
#  "results": [
#  {
#  "product_name": "상품명",
#  "site": "쇼핑사명",
#  "price": 29900,
#  "broadcast_date": "2025-09-01",
#  "broadcast_time": "10:00",
#  "image_url": "https://...",
#  "score": 0.95
#  }
#  ],
#  "aggregations": {
#  "min_price": 9900,
#  "max_price": 99000,
#  "site_counts": {
#  "CJ온스타일": 25,
#  "GS샵": 30,
#  "현대홈쇼핑": 20,
#  "롯데홈쇼핑": 25
#  }
#  },
# }

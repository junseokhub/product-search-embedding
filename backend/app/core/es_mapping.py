INDEX_NAME = "products"

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "korean_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["lowercase"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "pid": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "korean_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "site": {"type": "keyword"},
            "price": {"type": "integer"},
            "broadcast_date": {
                "type": "date",
                "format": "yyyy-MM-dd"
            },
            "broadcast_time": {"type": "keyword"},
            "image_url": {
                "type": "keyword",
                "index": False
            },
            "name_vector": {
                "type": "dense_vector",
                "dims": 512,
                "index": True,
                "similarity": "cosine"
            },
            "image_vector": {
                "type": "dense_vector",
                "dims": 512,
                "index": True,
                "similarity": "cosine"
            }
        }
    }
}
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL")
    ES_INDEX: str = os.getenv("ES_INDEX", "products")

    REDIS_URL: str = os.getenv("REDIS_URL")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "60"))

    CB_OPEN_DURATION: int = int(os.getenv("CB_OPEN_DURATION", "60"))

    CLIP_MODEL_NAME: str = os.getenv("CLIP_MODEL_NAME", "ViT-B-32")
    CLIP_PRETRAINED: str = os.getenv("CLIP_PRETRAINED", "openai")


settings = Settings()
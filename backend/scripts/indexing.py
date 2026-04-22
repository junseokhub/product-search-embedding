import asyncio
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from elasticsearch.helpers import async_bulk

from app.core.elasticsearch import create_index, elastic_search_client

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BATCH_SIZE = 100


async def index_products(csv_path: Path, embeddings_dir: Path):
    # 임베딩 파일 읽기 및 ES 색인
    await create_index()
    es = elastic_search_client()
    async with elastic_search_client() as es:
        df = pd.read_csv(csv_path)

        # Path 객체를 활용해 경로 결합
        name_vectors = np.load(embeddings_dir / "name_vectors.npy")
        image_vectors = np.load(embeddings_dir / "image_vectors.npy")
        valid_indices = np.load(embeddings_dir / "valid_indices.npy")

        log.info(f"{len(valid_indices)}개 상품 색인 시작")

        batch = []
        for i, idx in enumerate(valid_indices):
            row = df.iloc[idx]

            dt = datetime.fromisoformat(str(row["broadcast_date"]))

            doc = {
                "_index": "products",
                "_id": str(row["pid"]),
                "_source": {
                    "pid": str(row["pid"]),
                    "name": row["name"],
                    "site": row["site"],
                    "price": int(row["price"]),
                    "broadcast_date": dt.strftime("%Y-%m-%d"),
                    "broadcast_time": dt.strftime("%H:%M"),
                    "image_url": row["image_url"],
                    "name_vector": name_vectors[i].tolist(),
                    "image_vector": image_vectors[i].tolist(),
                }
            }
            batch.append(doc)

            if len(batch) >= BATCH_SIZE:
                await async_bulk(es, batch)
                batch = []
                log.info(f"{i + 1}개 데이터 색인 중...")

        if batch:
            await async_bulk(es, batch)

        log.info("모든 작업 완료!")


if __name__ == "__main__":
    CURRENT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = CURRENT_DIR.parent

    asyncio.run(index_products(
        csv_path=PROJECT_ROOT / 'data' / 'products.csv',
        embeddings_dir=PROJECT_ROOT / 'data' / 'embeddings'
    ))
import logging
import numpy as np
import pandas as pd
from tqdm import tqdm
from pathlib import Path

from app.embedding.clip import CLIPEmbedding

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def generate_embeddings(csv_path: Path, output_dir: Path):
    """CSV 읽어서 텍스트/이미지 임베딩 계산 후 npy 파일로 저장"""
    # 임베딩 계산은 너무 오래 걸려서 한 번 실행하고 파일로 보관
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    log.info(f"{len(df)}개 상품 임베딩 시작")

    embedder = CLIPEmbedding()

    name_vectors = []
    image_vectors = []
    valid_indices = []

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        try:
            name_vector = embedder.embed_text(str(row["name"]))
            image_vector = embedder.embed_image_from_url(str(row["image_url"]))

            name_vectors.append(name_vector)
            image_vectors.append(image_vector)
            valid_indices.append(idx)

        except Exception as e:
            pid = row.get('pid', 'Unknown')
            log.warning(f"pid={pid} 스킵: {e}")

    np.save(output_dir / "name_vectors.npy", np.array(name_vectors))
    np.save(output_dir / "image_vectors.npy", np.array(image_vectors))
    np.save(output_dir / "valid_indices.npy", np.array(valid_indices))

    log.info(f"임베딩 저장 완료 - 성공: {len(valid_indices)}, 실패: {len(df) - len(valid_indices)}")


if __name__ == "__main__":
    CURRENT_FILE = Path(__file__).resolve()
    PROJECT_ROOT = CURRENT_FILE.parent.parent

    generate_embeddings(
        csv_path=PROJECT_ROOT / 'data' / 'products.csv',
        output_dir=PROJECT_ROOT / 'data' / 'embeddings'
    )
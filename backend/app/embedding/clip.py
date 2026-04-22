from io import BytesIO

import httpx
import open_clip
import torch
from PIL import Image

from app.config import settings


class CLIPEmbedding:
    """CLIP 모델로 텍스트,이미지 벡터화"""

    def __init__(self):
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            settings.CLIP_MODEL_NAME,
            pretrained=settings.CLIP_PRETRAINED
        )
        self.tokenizer = open_clip.get_tokenizer(settings.CLIP_MODEL_NAME)
        self.model.eval()

    def embed_text(self, text: str) -> list[float]:
        """텍스트 벡터화"""
        tokens = self.tokenizer([text])
        with torch.no_grad():
            vector = self.model.encode_text(tokens)
            vector = vector / vector.norm(dim=-1, keepdim=True)
        return vector[0].tolist()

    def embed_image_from_url(self, url: str) -> list[float]:
        """이미지 URL 벡터화"""
        response = httpx.get(url, timeout=10)
        image = Image.open(BytesIO(response.content)).convert("RGB")
        tensor = self.preprocess(image).unsqueeze(0)
        with torch.no_grad():
            vector = self.model.encode_image(tensor)
            vector = vector / vector.norm(dim=-1, keepdim=True)
        return vector[0].tolist()

embedding = CLIPEmbedding()




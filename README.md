- 임베딩을 활용하여 image search, text search, hybrid search를 지원하는 검색 API를 개발합니다.

## 기술 스택

- FastAPI, Elasticsearch 9.3, Redis, CLIP (ViT-B/32), Docker Compose

## 실행 방법

### env 파일 생성
```
ELASTICSEARCH_URL=http://elasticsearch:9200
ES_INDEX=products
REDIS_URL=redis://redis:6379
CACHE_TTL=60
CB_OPEN_DURATION=60
CLIP_MODEL_NAME=ViT-B-32
CLIP_PRETRAINED=openai
```

### 임베딩 파일
- 임베딩 파일은 backend/data/embeddings/ 경로
  - name_vectors.npy
  - image_vectors.npy
  - valid_indices.npy

### 실행

```bash
docker compose up --build
```

ES 헬스체크 → Redis 헬스체크 → 색인 자동 실행 → 백엔드 시작 → 프론트엔드 시작 순서

- Front End: http://localhost:3000
- BackEnd: http://localhost:8000
- API 문서: http://localhost:8000/docs

### 수동 색인 (필요한 경우)

```bash
# 임베딩 파일 새로 생성 (시간 많이 걸림) <추후 개선 필요>
- env에 "PYTHONPATH=." 추가
cd backend
PYTHONPATH=. python scripts/generate_embeddings.py

# ES 색인
PYTHONPATH=. python scripts/indexing.py
```

## 검색 API
- 텍스트
```
GET /search?query=헬스
```
- 이미지 검색
```
GET /search?image_url=https://...
```
- 하이브리드 검색 (텍스트, 이미지)
```
GET /search?query=헬스&image_url=https://...
```
- 필터
```
GET /search?query=헬스&site=cjmall
GET /search?query=헬스&broadcast_date=2025-09-01
GET /search?query=헬스&site=cjmall&broadcast_date=2025-09-01
```

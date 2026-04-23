# APLUS 백엔드 엔지니어 과제
- 임베딩을 활용하여 image search, text search, hybrid search를 지원하는 검색 API를 개발합니다.

## 기술 스택

- FastAPI, Elasticsearch 9.3, Redis, CLIP (ViT-B/32), Docker Compose

## 실행 방법

### env 파일 생성
- git에 없기 떄문에 backend/.env 파일을 직접 만들어야 합니다.
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
- 임베딩 파일은 backend/data/embeddings/ 경로에 있어야 합니다.
  - name_vectors.npy
  - image_vectors.npy
  - valid_indices.npy

용량이 괜찮을 듯 해서 git에 포함시켰습니다. (각 28MB, 총 56MB)

### 실행

```bash
docker compose up --build
```

ES 헬스체크 → Redis 헬스체크 → 색인 자동 실행 → 백엔드 시작 → 프론트엔드 시작 순서로 진행됩니다.

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

## 주요 기술 선택 이유 및 추후 결정

### CLIP (ViT-B/32)
- 텍스트와 이미지를 같은 벡터 공간에 임베딩하는 모델입니다.
- 이 과제에서 텍스트/이미지/hybrid 검색을 모두 지원해야 하기 때문에 선택했습니다. 
- 텍스트 전용 모델은 이미지 검색이 불가능하고, 이미지 전용 모델은 텍스트 검색이 불가능합니다. CLIP은 둘 다 같은 공간에 임베딩하므로 교차 검색이 가능합니다.
- 한국어 특화 모델(Korean-CLIP)이 더 정확할 수 있으나, 레퍼런스가 적고 설치가 복잡하고 무료라는 점에서 과제 수준에서는 적합하다고 판단해서 CLIP ViT-B/32를 선택했습니다. 
- 모델 교체는 .env의 CLIP_MODEL_NAME, CLIP_PRETRAINED 값만 변경하면 됩니다. 
- 추후 유료 버전 사용시 아래와 같이 진행하면 될 것 같습니다.
  - requirements.txt에 라이브러리 추가
  - .env에 API_KEY 추가
  - config.py 에 API_KEY추가
  - clip.py에서 모델 로딩 시 api_key 파라미터 전달
    
### Elasticsearch
- 벡터 검색, 필터링, 집계를 동시에 지원합니다. 
- 기존 제가 사용하던 Milvus 같은 전용 벡터 DB는 벡터 검색에 특화되어 있지만 site 필터, 날짜 필터, 가격 집계를 처리하기 어렵습니다. 
- ES는 이 모든 것을 하나의 쿼리로 처리할 수 있는 장점이 있다고 생각합니다.
- 기존에는 ES 연결이 매번 요청되었습니다. 해당 부분을 lifespan을 사용해 어플리케이션 실행할 때 한번만 되게 변경했습니다.

### 텍스트 검색 방식 (BM25 + KNN)
- 처음에는 KNN만 사용했는데 CLIP의 한국어 약점으로 인해 검색 품질이 낮았습니다. 
- ES의 RRF를 시도했으나 (현 버전 기준(9.3.0)) 유료 기능이었습니다. 그래서 BM25 키워드 검색과 KNN 벡터 검색을 직접 결합하는 방식으로 변경했습니다. 
- boost 값은 BM25 0.5, KNN 0.5로 동일하게 설정했으며, 나머지는 크게 의미를 두진 않았고 1.0으로 맞추게끔만 조절했습니다.
  - 해당 값들은 추후 실제 서비스일 경우 지표 기반으로 튜닝이 필요할 것 같습니다.

### Redis 캐시
- 인메모리 기반으로 조회 속도가 빠르고 TTL 기능이 내장되어 있어서 요구 사항대로 1분 캐시 구현을 진행했습니다.
- 검색 파라미터를 해시로 변환해서 캐시 키로 사용했습니다. image_url 같은 긴 값이 키로 들어올 경우를 대비해 고정 길이(32자)로 정규화했습니다.

### Circuit Breaker
- ES 장애가 발생했을 때 요청마다 타임아웃을 기다리지 않도록 차단합니다. 
- 요구사항대로 60초 동안 OPEN 상태를 유지하고 이후 자동으로 CLOSED로 전환됩니다.

### Nginx
- nginx reverse proxy를 사용해 /api/ 요청을 백엔드로 프록시했습니다.
- 백엔드 주소를 하드코딩 할 수 있지만 일단 자유롭게 만들라하셔서 html로 최대한 간단하게 구현햇고, html은 정적파일이라 환경변수도 읽지도 못해 해당 방식을 선택했습니다.

### I/O 비동기 처리
- 솔직히 동기로도 지금 수준에서는 충분하다고 판단했었습니다. 그런데 과제에서 FastAPI를 선택한 이유가 비동기 I/O처리까지 고려할 것으로 생각되서 전환했습니다.
- 정작 I/O작업인 ES검색, Redis 캐시, 이미지 다운로드 같은걸 전부 동기로 처리하면 의미가 없다고도 생각했습니다.
- 그래서 기존 동기 방식에서 I/O 작업들만 비동기로 처리하고, 이미지 임베딩 계산만 executor로 스레드풀에서 실행하게 했습니다.


## 추후 개선 할 점

### 검색 품질
- Korean-CLIP 등 한국어 특화 모델로 교체하면 더 품질이 좋아지지 않을까 생각합니다.
  - 하지만 아직 Korean-CLIP의 성능을 확실히 몰라서 다른 대안도 고려해야합니다.
- boost 값 튜닝 (NDCG, MRR 등)을 지표기반으로 튜닝합니다. 
- 임베딩 캐싱 (같은 쿼리 반복 시 재계산 방지) 
  - 현재는 요구 사항대로 검색 결과만 1분동안 캐시에 저장한 뒤 동일 검색 요청에서는 캐시된 결과가 나오도록 했지만 추후엔 검색마다 다 임베딩이 안되도록 임베딩도 캐싱하면 더 좋을 것 같습니다.

### 성능
- 임베딩 생성 시 이미지 다운로드 병렬화

### 안정성
- Circuit Breaker Half-Open 상태 추가 (현재는 CLOSED/OPEN만 있음)
- 색인 실패한 pid 저장 후 재시작 시 이어서 처리
- Redis 장애 시 graceful degradation (현재도 try-except로 처리 중이나 모니터링 부재)

### 인프라 (Kubernetes)
- 현재 개인 서버 운영중인 클러스터기준을 실제 운용 서버라고 생각하고 판단해봤습니다.
- ES는 ECK(Elastic Cloud on Kubernetes) operator로 StatefulSet 배포를 하면 좋지 않을까 생각됩니다. 
  - PVC로 데이터 영속성을 보장하고 3노드 클러스터로 구성하면 HA가 됩니다.
- 백엔드는 Deployment로 배포하고 HPA로 부하에 따라 자동 스케일링합니다. 
- Redis는 Redis Operator나 Helm chart(opstree/redis)로 배포합니다. 
  - bitnami가 이제 전면 유료로 전환되며 기존것들 업데이트가 없을거라고 들어서 현재 개인환경에는 opstree/redis-cluster로 구성되어 있어 추후엔 redis-cluster를 적용하면 좋을것 같습니다. 
- 색인 작업은 Kubernetes Job으로 실행하고 initContainer 패턴으로 백엔드 Pod 시작 전에 완료되도록 하면 될 것 같습니다.
- Ingress는 nginx-ingress controller로 라우팅하고 cert-manager로 TLS 인증서를 자동 발급을 수 있게 됩니다.

## 어려웠던 부분
- Python/FastAPI가 솔직히 저에게 익숙한 프레임워크는 아닙니다. 실무에선 Flask정도 사용해봤었구요. 그래서 Java와 다른 패키지 관리 방식, 경로 처리(PYTHONPATH)등 개념이 낯설었습니다.
- ES의 RRF가 유료 기능인 줄 몰라서 시도했다가 403 에러로 확인 후 BM25+KNN 조합으로 변경했습니다.
- Docker 환경에서 CLIP 모델 캐시 경로 권한 문제가 있었습니다. appuser 홈 디렉토리를 명시적으로 생성해서 해결했습니다.
- 임베딩 생성이 7120개 상품을 순차 처리해서 시간이 많이 걸렸습니다.(처음엔 20-30분 사이 정도) 
  - 이후 간단하게 배치로도 구현해봤지만 크게 차이는 없었어서 추후 병렬 처리 개선이 필요하다고 생각합니다.

## 참고 레퍼런스

- https://fastapi.tiangolo.com
- https://fastapi.tiangolo.com/advanced/events/
- https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html
- https://github.com/mlfoundations/open_clip
- https://platform.openai.com/docs/guides/embeddings
- https://www.python-httpx.org/async/

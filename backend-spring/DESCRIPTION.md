# 상품 검색 API - Spring Boot

CLIP 임베딩 기반 텍스트 / 이미지 / Hybrid 검색 API입니다.
Spring Boot 내부에서 ONNX Runtime으로 CLIP 모델을 직접 실행해 벡터를 생성하고,
Elasticsearch에서 KNN + BM25 하이브리드 검색을 수행합니다.

---

## 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| Spring Boot | 3.5.13 | 웹 프레임워크 |
| Java | 21 | 언어 |
| Gradle Kotlin DSL | - | 빌드 도구 |
| Elasticsearch | 9.x | 벡터 + 텍스트 검색 |
| Redis | - | 검색 결과 캐시 |
| ONNX Runtime | 1.20.0 | CLIP 모델 실행 |
| DJL HuggingFace Tokenizers | 0.32.0 | 텍스트 토크나이징 |
| OpenCSV | 5.9 | CSV 파싱 |
| Lombok | - | 보일러플레이트 제거 |

---

## 프로젝트 구조

```
src/main/java/com/embedding/products/
├── config/
│   ├── AppConfig.java              # 앱 설정값 바인딩 (application.yml → record)
│   ├── ElasticsearchConfig.java    # ES 클라이언트 연결 설정
│   ├── IndexMappingConfig.java     # ES 인덱스/매핑 생성
│   └── RedisConfig.java            # Redis 직렬화 설정
├── controller/
│   └── SearchController.java       # GET /search 엔드포인트
├── core/
│   ├── CircuitBreaker.java         # ES 장애 차단 패턴
│   └── EsQueryBuilder.java         # ES 쿼리 빌더
├── document/
│   └── Product.java                # ES 문서 엔티티 (@Document)
├── dto/
│   ├── Aggregations.java           # 집계 응답 DTO
│   ├── DownloadResult.java         # 이미지 다운로드 중간 DTO
│   ├── ProductResult.java          # 검색 결과 DTO
│   ├── SearchParams.java           # 검색 파라미터 DTO
│   └── SearchResponse.java         # 최종 검색 응답 DTO
├── embedding/
│   └── ClipEmbedding.java          # CLIP 텍스트/이미지 임베딩
├── exception/
│   ├── GlobalExceptionHandler.java # 전역 예외 처리
│   └── SearchException.java        # 검색 전용 커스텀 예외
├── repository/
│   └── ProductRepository.java      # ES Repository 인터페이스
├── service/
│   ├── IndexingService.java        # CSV 읽기 + 색인 서비스
│   └── SearchService.java          # 검색 로직 서비스
├── IndexingRunner.java             # 앱 시작 시 자동 색인 실행
└── ProductsApplication.java        # 메인 클래스
```

---

## 실행 방법

### 1. CLIP 모델 ONNX 변환 (최초 1회)

CLIP은 원래 Python PyTorch 모델입니다.
Java에서 실행하려면 ONNX 포맷으로 변환해야 합니다.
변환된 파일은 `clip_onnx/` 폴더에 저장되며 용량이 크기 때문에 `.gitignore`에 포함되어 있습니다.

```bash
# 가상환경 생성 (전역 설치 방지)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# 변환 라이브러리 설치
pip install 'optimum[exporters-onnx]' 'optimum[onnx]'

# 변환 스크립트 실행
python3 convert_clip.py
```

`convert_clip.py`:
```python
from optimum.exporters.onnx import main_export

main_export(
    model_name_or_path="openai/clip-vit-base-patch32",
    output="./clip_onnx/",
    task="feature-extraction"
)
```

변환 결과 (약 577MB):
```
clip_onnx/
├── model.onnx        # 텍스트 + 이미지 통합 모델
├── tokenizer.json    # 토크나이저 설정
├── vocab.json        # 어휘 사전
└── merges.txt        # BPE 병합 규칙
```

### 2. Elasticsearch nori 플러그인 설치

한국어 형태소 분석을 위해 nori 플러그인이 필요합니다.
설치하지 않으면 인덱스 생성 시 오류가 발생합니다.

```bash
docker exec -it <elasticsearch-container> bin/elasticsearch-plugin install analysis-nori
docker restart <elasticsearch-container>
```

### 3. 환경 설정

`src/main/resources/application.yml`:

```yaml
spring:
  elasticsearch:
    uris: ${ELASTICSEARCH_URL:http://localhost:9200}
  data:
    redis:
      url: ${REDIS_URL:redis://localhost:6379}
  jackson:
    property-naming-strategy: SNAKE_CASE

app:
  es-index: ${ES_INDEX:products}
  cache-ttl: ${CACHE_TTL:60}
  cb-open-duration: ${CB_OPEN_DURATION:60}
  clip-model-path: ${CLIP_MODEL_PATH:./clip_onnx/model.onnx}
  clip-tokenizer-path: ${CLIP_TOKENIZER_PATH:./clip_onnx/tokenizer.json}
```

### 4. 실행

```bash
./gradlew bootRun
```

앱 시작 시 자동으로:
1. ES 인덱스가 없으면 nori 분석기 + dense_vector 매핑으로 인덱스 생성
2. ES에 데이터가 없으면 `data/products.csv`를 읽어서 자동 색인
3. 이미 색인된 데이터가 있으면 색인 스킵

- API: `http://localhost:8080`
- Swagger: `http://localhost:8080/swagger-ui.html`

---

## 검색 API

### 텍스트 검색
```
GET /search?query=다이어트
```

### 이미지 검색
```
GET /search?image_url=https://example.com/image.jpg
```

### Hybrid 검색 (텍스트 + 이미지)
```
GET /search?query=다이어트&image_url=https://example.com/image.jpg
```

### 필터
```
GET /search?query=다이어트&site=cjmall
GET /search?query=다이어트&broadcast_date=2025-09-01
GET /search?query=다이어트&site=cjmall&broadcast_date=2025-09-01
```

### 응답 예시
```json
{
  "total": 92,
  "results": [
    {
      "product_name": "푸응 파비플로라 다이어트 12박스",
      "site": "gsshop",
      "price": 268000,
      "broadcast_date": "2025-09-23",
      "image_url": "https://...",
      "score": 3.16
    }
  ],
  "aggregations": {
    "min_price": 0,
    "max_price": 649000,
    "site_counts": {
      "cjmall": 20,
      "gsshop": 10
    }
  }
}
```

---

## 코드 설명

### config/AppConfig.java

```java
@ConfigurationProperties(prefix = "app")
public record AppConfig(
        String esIndex,
        int cacheTtl,
        int cbOpenDuration,
        String clipModelPath,
        String clipTokenizerPath
) {}
```

`application.yml`의 `app.*` 값들을 Java 객체로 자동 바인딩합니다.
`record`를 사용해서 불변 객체로 만들었습니다. setter가 없기 때문에 런타임에 값이 변경될 위험이 없습니다.
`@ConfigurationProperties`는 생성자 바인딩 방식으로 동작하기 때문에 `record`와 궁합이 좋습니다.
`@EnableConfigurationProperties(AppConfig.class)`를 메인 클래스에 선언해야 동작합니다.

---

### config/ElasticsearchConfig.java

```java
@Configuration
public class ElasticsearchConfig extends ElasticsearchConfiguration {

    @Override
    public ClientConfiguration clientConfiguration() {
        return ClientConfiguration.builder()
                .connectedTo(host)
                .build();
    }
}
```

`ElasticsearchConfiguration`을 상속해서 ES 클라이언트 연결을 설정합니다.
`clientConfiguration()` 메서드만 오버라이드하면 Spring Data Elasticsearch가 나머지 Bean(`ElasticsearchClient`, `ElasticsearchOperations` 등)을 자동으로 생성해줍니다.
`application.yml`의 `spring.elasticsearch.uris`에서 호스트를 읽어와 `http://`를 제거한 후 사용합니다.

---

### config/IndexMappingConfig.java

```java
@PostConstruct
public void createIndexIfNotExists() throws Exception {
    boolean exists = esClient.indices().exists(r -> r.index(index)).value();
    if (exists) return;

    esClient.indices().create(CreateIndexRequest.of(r -> r
            .index(index)
            .settings(...)
            .mappings(...)
    ));
}
```

`@PostConstruct`는 Bean이 생성된 직후 딱 한 번 실행됩니다.
인덱스가 없을 때만 생성하므로 앱을 재시작해도 기존 데이터가 유지됩니다.
매핑에는 `nori_tokenizer` 기반 한국어 분석기, `keyword` 타입 필터 필드, `dense_vector` 타입 벡터 필드가 포함됩니다.
`dense_vector`에 `similarity: cosine`을 설정해서 코사인 유사도 기반 KNN 검색이 가능합니다.

---

### config/RedisConfig.java

```java
@Bean
public RedisTemplate<String, SearchResponse> redisTemplate(RedisConnectionFactory factory) {
    RedisTemplate<String, SearchResponse> template = new RedisTemplate<>();
    template.setConnectionFactory(factory);
    template.setKeySerializer(new StringRedisSerializer());
    template.setValueSerializer(new GenericJacksonJsonRedisSerializer());
    return template;
}
```

Redis에 저장할 때 키는 문자열, 값은 JSON으로 직렬화합니다.
`GenericJacksonJsonRedisSerializer`는 Spring Data Redis 4.0에서 도입된 Jackson 3 기반 직렬화기입니다.
기존의 `Jackson2JsonRedisSerializer`와 `GenericJackson2JsonRedisSerializer`는 4.0에서 deprecated 되었습니다.

---

### document/Product.java

```java
@Document(indexName = "products")
@Setting(settingPath = "elasticsearch/settings.json")
@Mapping(mappingPath = "elasticsearch/mappings.json")
@Builder
public record Product(
        @Id String pid,
        @Field(type = FieldType.Text, analyzer = "korean") String name,
        @Field(type = FieldType.Keyword) String site,
        @Field(type = FieldType.Integer) int price,
        @Field(type = FieldType.Keyword, name = "broadcast_date") String broadcastDate,
        @Field(type = FieldType.Keyword, name = "image_url") String imageUrl,
        @Field(type = FieldType.Dense_Vector, dims = 512, name = "name_vector") float[] nameVector,
        @Field(type = FieldType.Dense_Vector, dims = 512, name = "image_vector") float[] imageVector
) {}
```

ES 문서를 Java 객체로 표현한 엔티티 클래스입니다.
`@Document`로 인덱스 이름을 지정하고, `@Field`로 각 필드의 ES 타입을 선언합니다.
`@Setting`, `@Mapping`으로 외부 JSON 파일에서 설정을 읽어옵니다.
`record`를 사용해서 불변 객체로 만들었으며, `@Builder`로 빌더 패턴을 지원합니다.

> **주의**: 검색 결과를 `Product.class`로 역직렬화하면 `nameVector`, `imageVector` 필드 파싱 오류가 발생합니다.
> 이는 ES에서 반환되는 dense_vector 값이 Java `float[]`로 바로 매핑되지 않기 때문입니다.
> 따라서 검색 결과는 `Map.class`로 받아서 `ProductResult`로 수동 변환합니다.
> `Product`는 색인(저장) 전용으로 사용합니다.

---

### repository/ProductRepository.java

```java
public interface ProductRepository extends ElasticsearchRepository<Product, String> {}
```

Spring Data Elasticsearch가 제공하는 Repository 인터페이스입니다.
인터페이스만 선언하면 `save()`, `saveAll()`, `findById()`, `count()`, `delete()` 등의 기본 CRUD 메서드를 자동으로 생성해줍니다.
색인 시 `productRepository.saveAll(batch)`로 100개씩 bulk 저장합니다.

---

### embedding/ClipEmbedding.java

CLIP 모델을 ONNX Runtime으로 실행해서 텍스트/이미지 벡터를 생성합니다.

#### init()
```java
@PostConstruct
public void init() throws OrtException, IOException {
    env = OrtEnvironment.getEnvironment();
    OrtSession.SessionOptions opts = new OrtSession.SessionOptions();
    opts.setIntraOpNumThreads(Runtime.getRuntime().availableProcessors());
    opts.setInterOpNumThreads(Runtime.getRuntime().availableProcessors() / 2);
    session = env.createSession(modelPath, opts);
    tokenizer = HuggingFaceTokenizer.newInstance(Path.of(tokenizerPath));
}
```
앱 시작 시 ONNX 모델 파일을 메모리에 로드합니다.
`setIntraOpNumThreads`는 연산 하나를 처리할 때 사용할 스레드 수입니다.
`setInterOpNumThreads`는 여러 연산을 병렬로 처리할 때 사용할 스레드 수입니다.
CPU 코어 수에 맞춰 자동으로 설정해서 최대 성능을 냅니다.

#### embedText(String text)
```java
public float[] embedText(String text) throws OrtException {
    return embedTextBatch(List.of(text))[0];
}
```
단일 텍스트를 512차원 벡터로 변환합니다.
내부적으로 `embedTextBatch`를 호출해서 코드 중복을 제거했습니다.
검색 시 쿼리 텍스트를 벡터로 변환할 때 사용합니다.

#### embedTextBatch(List\<String\> texts)
```java
public float[][] embedTextBatch(List<String> texts) throws OrtException {
    // 1. 텍스트를 token ID로 변환 (토크나이징)
    // 2. 77 길이로 패딩/트런케이션
    // 3. ONNX 모델에 배치로 입력
    // 4. text_embeds 출력에서 벡터 추출
    // 5. L2 정규화
}
```
여러 텍스트를 한 번의 ONNX 호출로 처리합니다.
색인 시 100개씩 배치로 처리해서 ONNX 호출 횟수를 줄입니다.

토크나이징 과정:
- 텍스트를 BPE(Byte Pair Encoding) 방식으로 토큰 ID 배열로 변환
- CLIP은 최대 77개 토큰을 처리하므로 77 길이로 맞춤
- 짧으면 PAD 토큰(49407)으로 채우고, 길면 자름
- 이미지 입력(`pixel_values`)은 더미 값으로 채움 (텍스트 임베딩만 필요)

#### embedImage(BufferedImage image)
```java
public float[] embedImage(BufferedImage image) throws OrtException {
    return embedImageBatch(List.of(image))[0];
}
```
단일 이미지를 512차원 벡터로 변환합니다.
`embedImageBatch`를 호출해서 코드 중복을 제거했습니다.

#### embedImageBatch(List\<BufferedImage\> images)
```java
public float[][] embedImageBatch(List<BufferedImage> images) throws OrtException {
    // 1. 각 이미지를 224x224로 리사이즈
    // 2. CLIP 전처리 (평균/표준편차 정규화)
    // 3. NCHW 포맷으로 변환 (배치, 채널, 높이, 너비)
    // 4. ONNX 모델에 배치로 입력
    // 5. image_embeds 출력에서 벡터 추출
    // 6. L2 정규화
}
```
여러 이미지를 한 번의 ONNX 호출로 처리합니다.
텍스트 입력(`input_ids`, `attention_mask`)은 더미 값으로 채움 (이미지 임베딩만 필요)

이미지 전처리 상수:
```java
private static final float[] MEAN = {0.48145466f, 0.4578275f, 0.40821073f};
private static final float[] STD  = {0.26862954f, 0.26130258f, 0.27577711f};
```
CLIP 모델이 학습된 데이터셋의 RGB 평균과 표준편차입니다.
이 값으로 정규화해야 학습 때와 동일한 입력 분포가 됩니다.

#### preprocessImage(BufferedImage image)
```java
private float[] preprocessImage(BufferedImage image) {
    // 224x224 리사이즈
    // RGB 각 채널을 0~1 범위로 정규화
    // CLIP 평균/표준편차로 추가 정규화
    // NCHW 포맷으로 변환
}
```
NCHW 포맷이란 (Batch, Channel, Height, Width) 순서입니다.
예를 들어 R 채널 픽셀 전체 → G 채널 픽셀 전체 → B 채널 픽셀 전체 순서로 저장합니다.
`getRGB()`로 2D 배열을 한 번에 읽어서 3중 for문 없이 처리합니다.

#### normalize(float[] v)
```java
private float[] normalize(float[] v) {
    float norm = 0f;
    for (float x : v) norm += x * x;
    norm = (float) Math.sqrt(norm);
    float[] result = new float[v.length];
    for (int i = 0; i < v.length; i++) result[i] = v[i] / norm;
    return result;
}
```
벡터의 길이(L2 norm)를 1로 만드는 정규화입니다.
Elasticsearch의 `similarity: cosine` 설정은 정규화된 벡터를 기대하기 때문에 필수입니다.
정규화하면 코사인 유사도 계산이 내적(dot product)과 동일해져서 계산이 단순해집니다.

---

### core/EsQueryBuilder.java

ES 검색 쿼리를 생성하는 클래스입니다.

#### buildTextQuery()
```java
public SearchRequest buildTextQuery(float[] vector, String index, SearchParams params) {
    return SearchRequest.of(s -> s
            .index(index)
            .query(q -> q.bool(b -> b
                    .should(matchQuery(params.query(), 0.5f))  // BM25 키워드 검색
                    .should(knnQuery("name_vector", vectorList, 0.5f, filters))  // KNN 벡터 검색
                    .filter(filters)  // 필터 (점수 영향 없음)
            ))
            .aggregations(buildAggregations())
            .size(10)
    );
}
```
`bool.should`에 BM25와 KNN을 함께 넣어서 두 점수를 합산합니다.
`boost` 값으로 각 검색 방식의 가중치를 조절합니다.

#### buildHybridQuery()
텍스트 KNN(name_vector), 이미지 KNN(image_vector), BM25 세 가지를 결합합니다.
```
BM25(0.3) + 텍스트 KNN(0.4) + 이미지 KNN(0.3) = 1.0
```

#### matchQuery() / knnQuery()
```java
private Query matchQuery(String query, float boost) {
    return Query.of(q -> q.match(m -> m.field("name").query(query).boost(boost)));
}

private Query knnQuery(String field, List<Float> vector, float boost, List<Query> filters) {
    return Query.of(q -> q.knn(k -> k
            .field(field)
            .queryVector(vector)
            .numCandidates(100)
            .boost(boost)
            .filter(filters)
    ));
}
```
중복되는 쿼리 생성 코드를 메서드로 추출해서 재사용합니다.
`numCandidates(100)`은 KNN 후보군 크기로, 클수록 정확하지만 느립니다.

#### buildFilters()
```java
private List<Query> buildFilters(SearchParams params) {
    List<Query> filters = new ArrayList<>();
    if (params.site() != null) {
        filters.add(Query.of(q -> q.term(t -> t.field("site").value(params.site()))));
    }
    if (params.broadcastDate() != null) {
        filters.add(Query.of(q -> q.term(t -> t.field("broadcast_date").value(params.broadcastDate()))));
    }
    return filters;
}
```
`filter`는 점수에 영향을 주지 않고 결과만 걸러냅니다.
`should`와 달리 만족하지 않으면 결과에서 제외됩니다.
ES가 filter 결과를 캐싱하기 때문에 `should`보다 성능이 좋습니다.

#### buildAggregations()
```java
private Map<String, Aggregation> buildAggregations() {
    return Map.of(
            "min_price", Aggregation.of(a -> a.min(m -> m.field("price"))),
            "max_price", Aggregation.of(a -> a.max(m -> m.field("price"))),
            "site_counts", Aggregation.of(a -> a.terms(t -> t.field("site")))
    );
}
```
검색 결과에 대한 통계를 계산합니다.
`min`, `max`는 단일 값 집계이고, `terms`는 그룹별 카운트입니다.
검색 쿼리와 함께 전송되어 한 번의 요청으로 검색 결과와 집계 결과를 동시에 받습니다.

---

### core/CircuitBreaker.java

```java
@Component
public class CircuitBreaker {

    public void recordFailure() {
        this.isOpen = true;
        this.openedAt = System.currentTimeMillis();
    }

    public boolean check() {
        if (!isOpen) return false;
        long elapsed = (System.currentTimeMillis() - openedAt) / 1000;
        if (elapsed >= cbOpenDuration) {
            this.isOpen = false;
            return false;
        }
        return true;
    }
}
```

ES 장애 시 계속 요청을 보내는 것을 방지합니다.
ES가 다운된 상태에서 매 요청마다 타임아웃을 기다리면 응답 시간이 수십 초가 걸립니다.
Circuit Breaker가 열리면 즉시 빈 응답을 반환해서 빠른 응답을 유지합니다.

**상태 전환:**
- 정상 상태 → ES 오류 발생 → `OPEN` (요청 차단)
- `OPEN` 상태 → `cbOpenDuration`초 경과 → `CLOSED` (정상)

> **현재 한계**: HALF-OPEN 상태가 없어서 ES가 완전히 복구되지 않아도 CLOSED로 전환될 수 있습니다.
> 멀티 인스턴스 환경에서는 서버마다 Circuit 상태가 다를 수 있습니다.

---

### service/SearchService.java

```java
public SearchResponse search(SearchParams params) {
    if (params.query() == null && params.imageUrl() == null) return SearchResponse.EMPTY;

    try {
        // 쿼리 타입에 따라 임베딩 + ES 쿼리 생성
        // ES 검색 실행
        // 결과 파싱 후 반환
    } catch (Exception e) {
        throw new SearchException("검색 실패", e);
    }
}
```

검색 타입(텍스트/이미지/hybrid)에 따라 적절한 임베딩과 쿼리를 선택합니다.
ES에서 받은 원시 응답을 `ProductResult`, `Aggregations` DTO로 변환합니다.
예외 발생 시 `SearchException`(RuntimeException)으로 감싸서 던집니다.
Controller에서 `SearchException`을 잡아 Circuit Breaker를 열고 캐시를 확인합니다.

#### parseResults()
```java
private List<ProductResult> parseResults(List<Hit<Map>> hits) {
    return hits.stream().map(hit -> {
        Map src = hit.source();
        return new ProductResult(
                (String) src.get("name"),
                ...
                hit.score() != null ? hit.score().floatValue() : 0.0f
        );
    }).toList();
}
```
ES 검색 결과(`Hit<Map>`)에서 필요한 필드만 추출해서 `ProductResult`로 변환합니다.
`Product.class`로 직접 역직렬화하면 `dense_vector` 필드 파싱 오류가 발생하기 때문에 `Map.class`로 받습니다.

#### parseAggregations()
```java
private Aggregations parseAggregations(Map<String, Aggregate> aggs) {
    int minPrice = extractInt(aggs, "min_price", a -> a.min().value());
    int maxPrice = extractInt(aggs, "max_price", a -> a.max().value());
    // site_counts는 terms 집계 → key(사이트명): value(상품수) 맵으로 변환
}

private int extractInt(Map<String, Aggregate> aggs, String key,
                       Function<Aggregate, Double> extractor) {
    if (!aggs.containsKey(key)) return 0;
    Double value = extractor.apply(aggs.get(key));
    return value != null ? value.intValue() : 0;
}
```
`extractInt` 헬퍼 메서드로 min/max 집계 파싱 코드 중복을 제거했습니다.
함수형 인터페이스(`Function`)를 사용해서 어떤 집계 타입이든 처리할 수 있습니다.

---

### controller/SearchController.java

```java
@GetMapping("/search")
public SearchResponse search(...) throws NoSuchAlgorithmException {
    // 1. 캐시 확인
    // 2. Circuit Breaker 확인
    // 3. 검색 실행
    // 4. 캐시 저장
    // 5. 예외 시 Circuit Breaker + 캐시 폴백
}
```

**요청 처리 순서:**
1. MD5 해시로 캐시 키 생성
2. Redis에서 캐시된 결과 확인 → 있으면 즉시 반환
3. Circuit Breaker가 열려있으면 빈 응답 반환
4. 검색 실행 후 Redis에 캐시 저장 (TTL: `cacheTtl`초)
5. `SearchException` 발생 시 Circuit Breaker 열기 → 캐시 재확인 → 없으면 빈 응답

#### makeCacheKey()
```java
private String makeCacheKey(String query, String imageUrl, String site, String broadcastDate)
        throws NoSuchAlgorithmException {
    String raw = query + ":" + imageUrl + ":" + site + ":" + broadcastDate;
    MessageDigest md = MessageDigest.getInstance("MD5");
    return "search:" + HexFormat.of().formatHex(md.digest(raw.getBytes()));
}
```
검색 파라미터 조합을 MD5 해시(32자)로 변환해서 캐시 키로 사용합니다.
`image_url`처럼 긴 값이 포함될 때 키 길이를 고정시키기 위함입니다.

---

### service/IndexingService.java

```java
public void indexProducts(String csvPath) throws Exception {
    // 1. CSV 전체 읽기
    // 2. 100개 배치 단위로 반복
    //    - 이미지 다운로드 병렬 (Virtual Thread)
    //    - 텍스트 배치 임베딩
    //    - 이미지 배치 임베딩
    //    - ES bulk 저장
}
```

자세한 성능 개선 과정은 [WHY.md](./WHY.md)를 참고하세요.

#### downloadImage()
```java
private DownloadResult downloadImage(String[] line) {
    // CSV 한 줄 파싱
    // 이미지 URL이 있으면 다운로드
    // DownloadResult 반환
}
```
Virtual Thread로 병렬 실행됩니다.
이미지 다운로드는 네트워크 I/O이기 때문에 Virtual Thread로 병렬화하면 효과적입니다.
다운로드 실패 시 `imageVector`를 null로 설정하고 계속 진행합니다.

#### embedBatch()
```java
private List<Product> embedBatch(List<DownloadResult> batch) throws Exception {
    float[][] textVectors  = clipEmbedding.embedTextBatch(...);  // 100개 텍스트 한번에
    float[][] imageVectors = clipEmbedding.embedImageBatch(...); // 100개 이미지 한번에
    // Product 엔티티 조립 후 반환
}
```
텍스트와 이미지를 각각 배치로 한 번에 ONNX 모델에 입력합니다.
100개를 개별로 처리하면 ONNX 호출 200번이 필요하지만, 배치로 처리하면 2번으로 줄어듭니다.

---

### IndexingRunner.java

```java
@Component
@RequiredArgsConstructor
public class IndexingRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) throws Exception {
        long count = productRepository.count();
        if (count > 0) {
            log.info("데이터 존재 ({}개), 색인 스킵", count);
            return;
        }
        indexingService.indexProducts("./data/products.csv");
    }
}
```

`ApplicationRunner`는 Spring 애플리케이션이 완전히 시작된 후 실행됩니다.
ES에 이미 데이터가 있으면 색인을 스킵합니다.
`data/products.csv`에서 상품 데이터를 읽어 색인합니다.

---

### exception/SearchException.java

```java
public class SearchException extends RuntimeException {
    public SearchException(String message, Throwable cause) {
        super(message, cause);
    }
}
```

`RuntimeException`을 상속하기 때문에 메서드 시그니처에 `throws` 선언이 불필요합니다.
ES 검색 중 발생하는 모든 예외를 이 예외로 감싸서 던집니다.
Controller에서 `SearchException`을 잡아 Circuit Breaker와 캐시 폴백 처리를 합니다.

---

### exception/GlobalExceptionHandler.java

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    public ResponseEntity<String> handleException(Exception e) {
        log.error("Unhandled exception: {}", e.getMessage(), e);
        return ResponseEntity.internalServerError().body("서버 오류가 발생했습니다");
    }
}
```

`@RestControllerAdvice`는 모든 Controller에서 발생하는 예외를 한 곳에서 처리합니다.
`SearchException`은 Controller에서 직접 처리하고, 나머지 예상치 못한 예외는 여기서 처리합니다.
내부 에러 메시지가 클라이언트에 노출되지 않도록 합니다.

---

### dto 클래스들

모든 DTO는 `record`로 선언했습니다.
`record`는 Java 16에서 정식 출시된 불변 데이터 클래스입니다.
`@Getter`, `@AllArgsConstructor`, `equals()`, `hashCode()`, `toString()`이 자동으로 생성됩니다.

```java
// SearchParams - 검색 파라미터를 하나의 객체로 묶음
public record SearchParams(String query, String imageUrl, String site, String broadcastDate) {}

// SearchResponse - 최종 응답 + EMPTY 상수
public record SearchResponse(int total, List<ProductResult> results, Aggregations aggregations) {
    public static final SearchResponse EMPTY =
            new SearchResponse(0, List.of(), new Aggregations(null, null, Map.of()));
}

// ProductResult - 검색 결과 단일 상품
public record ProductResult(String productName, String site, int price, ...) {}

// Aggregations - 집계 결과
public record Aggregations(Integer minPrice, Integer maxPrice, Map<String, Long> siteCounts) {}

// DownloadResult - 색인 시 이미지 다운로드 중간 결과
public record DownloadResult(String pid, String name, ..., BufferedImage image) {}
```

`application.yml`에 `spring.jackson.property-naming-strategy: SNAKE_CASE` 설정으로
`productName` → `product_name`으로 자동 변환됩니다.
`@JsonProperty` 없이도 snake_case API 응답을 만들 수 있습니다.

---

## 참고

- [Spring Data Elasticsearch 공식 문서](https://docs.spring.io/spring-data/elasticsearch/reference/)
- [ONNX Runtime Java API](https://onnxruntime.ai/docs/get-started/with-java.html)
- [DJL HuggingFace Tokenizers](https://docs.djl.ai/api/java/0.32.0/ai/djl/huggingface/tokenizers/HuggingFaceTokenizer.html)
- [Elasticsearch KNN Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html)
- [FastAPI lifespan (원본 프로젝트)](https://fastapi.tiangolo.com/advanced/events/)

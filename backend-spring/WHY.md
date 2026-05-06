# WHY.md - 설계 결정 과정

이 문서는 개발 과정에서 내린 주요 결정들과 그 이유를 기록합니다.
"왜 이렇게 했는가"에 집중합니다.

---

## 1. 색인 속도 개선 과정

7120개 상품을 Elasticsearch에 색인할 때 각 상품마다 텍스트와 이미지를 CLIP 모델로 임베딩해야 합니다.
처음 구현부터 최종 구현까지 4단계의 개선 과정을 거쳤습니다.

---

### 1단계: 순차 처리 (초기 구현)

```java
// 한 번에 하나씩 처리
while ((line = reader.readNext()) != null) {
    String imageUrl = line[5];
    float[] nameVector = clipEmbedding.embedText(name);      // 1개 텍스트 임베딩
    float[] imageVector = clipEmbedding.embedImageFromUrl(imageUrl);  // 1개 이미지 다운로드 + 임베딩
    // ES에 1개씩 저장
}
```

**문제점:**
- 이미지 다운로드(네트워크 I/O)와 ONNX 연산(CPU)이 순차 실행
- 이미지를 다운로드하는 동안 CPU가 놀고, ONNX 연산 중에는 네트워크가 놂
- 100개 처리에 약 12초 소요
- 7120개 전체 색인에 약 15분 예상

---

### 2단계: Virtual Thread 적용

```java
// Virtual Thread로 각 상품을 병렬 처리
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    while ((line = reader.readNext()) != null) {
        final String[] finalLine = line;
        futures.add(executor.submit(() -> processLine(finalLine)));
    }
}
```

**Virtual Thread란?**
Java 21에서 정식 출시된 경량 스레드입니다.
OS 스레드가 아닌 JVM이 관리하는 스레드라서 수천 개를 만들어도 메모리 부담이 적습니다.
I/O 대기 중(이미지 다운로드)에 다른 Virtual Thread로 전환해서 CPU를 효율적으로 사용합니다.

**결과:**
- 100개 처리에 약 4초로 개선 (기존 대비 3배)
- 하지만 ONNX 연산이 내부적으로 직렬화되어 기대만큼 빠르지 않음

**한계:**
각 Virtual Thread가 텍스트 임베딩 → 이미지 다운로드 → 이미지 임베딩을 모두 처리합니다.
ONNX 세션이 내부 락을 사용하기 때문에 실제 CPU 연산은 순차 실행됩니다.

---

### 3단계: 배치 임베딩

```java
// 100개를 모아서 한 번에 ONNX에 입력
float[][] textVectors  = clipEmbedding.embedTextBatch(names);   // 100개 텍스트 한 번에
float[][] imageVectors = clipEmbedding.embedImageBatch(images); // 100개 이미지 한 번에
```

**왜 배치가 빠른가?**
ONNX 모델 호출에는 고정 오버헤드가 있습니다.
1개씩 100번 호출하면 오버헤드가 100번 발생하지만, 100개를 한 번에 호출하면 오버헤드가 1번입니다.
GPU가 있으면 배치 처리의 효과가 훨씬 큽니다.

**변경된 흐름:**
```
기존: 임베딩(1개) → 임베딩(1개) → ... → 임베딩(1개)  (100번 ONNX 호출)
변경: 임베딩(100개 한번에)                             (1번 ONNX 호출)
```

**결과:**
배치 처리 자체는 효과가 있었지만, 이미지 다운로드를 먼저 모두 완료한 후 임베딩을 시작하는 구조라
100개 다운로드 완료 대기 시간이 추가되어 체감 속도는 비슷했습니다.

---

### 4단계: 파이프라인 구조 (최종)

```
기존 구조:
[다운로드 100개 완료] → [임베딩 100개] → [저장] → [다운로드 100개 완료] → ...
  (대기 발생)

파이프라인 구조:
[다운로드 배치1] → [임베딩 배치1] → [저장 배치1]
[다운로드 배치2] → [임베딩 배치2] → [저장 배치2]  ← 동시 진행
[다운로드 배치3] → [임베딩 배치3] → [저장 배치3]
```

`BlockingQueue`를 사용해서 다운로드와 임베딩을 파이프라인으로 연결했습니다.

```java
BlockingQueue<List<DownloadResult>> queue = new LinkedBlockingQueue<>(3);

// 임베딩 스레드 (별도 Virtual Thread)
Thread embeddingThread = Thread.ofVirtual().start(() -> {
    while (!done.get() || !queue.isEmpty()) {
        List<DownloadResult> batch = queue.poll(100, TimeUnit.MILLISECONDS);
        if (batch == null) continue;
        List<Product> products = embedBatch(batch);   // 배치 임베딩
        productRepository.saveAll(products);           // ES 저장
    }
});

// 다운로드 (메인 스레드)
for (배치 단위) {
    List<Future<DownloadResult>> futures = batch.stream()
            .map(l -> executor.submit(() -> downloadImage(l)))  // Virtual Thread 병렬 다운로드
            .toList();
    queue.put(downloaded);  // 다운로드 완료 → 큐에 넣기
}
```

**`BlockingQueue(3)`의 의미:**
큐의 최대 크기가 3입니다.
임베딩보다 다운로드가 빠른 경우 큐가 가득 차면 다운로드 스레드가 자동으로 대기합니다.
메모리에 너무 많은 배치가 쌓이는 것을 방지합니다.

**최종 결과:**
- 100개 처리에 약 4-5초
- 다운로드와 임베딩이 겹쳐서 실행되어 전체 색인 시간 단축

**남은 한계:**
결국 ONNX CPU 연산이 병목입니다.
GPU가 있거나 Apple Silicon MPS를 활용하면 훨씬 빨라질 수 있지만, CPU 환경에서는 이 정도가 현실적인 한계입니다.
색인은 한 번만 하는 작업이기 때문에 현재 속도로도 충분합니다.

---

## 2. Elasticsearch 연동 방식 변경

ES Java 클라이언트를 어떻게 사용할지 처음부터 최종까지 변경 과정입니다.

---

### 1단계: ElasticsearchClient 직접 사용

처음에는 `ElasticsearchClient`를 직접 주입받아서 모든 ES 작업을 처리했습니다.

```java
// 인덱스 생성
esClient.indices().create(request);

// 색인
Map<String, Object> doc = new HashMap<>();
doc.put("name", name);
doc.put("name_vector", nameVector);
// ...
BulkRequest.Builder br = new BulkRequest.Builder();
br.operations(op -> op.index(i -> i.index(index).id(pid).document(doc)));
esClient.bulk(br.build());

// 검색
SearchResponse<Map> response = esClient.search(request, Map.class);
```

**문제점:**
- 색인 시 `Map<String, Object>`로 문서를 직접 만들어야 함
- 필드 이름 오타가 컴파일 타임에 잡히지 않음
- Bulk 색인 코드가 복잡하고 장황함
- 인덱스 매핑을 Java 코드로 직접 작성해야 해서 복잡함

---

### 2단계: @Document + Repository 패턴 도입

Spring Data Elasticsearch의 `@Document`와 `ElasticsearchRepository`를 도입했습니다.

```java
// 엔티티 선언
@Document(indexName = "products")
@Setting(settingPath = "elasticsearch/settings.json")
@Mapping(mappingPath = "elasticsearch/mappings.json")
public record Product(@Id String pid, @Field(type = FieldType.Text) String name, ...) {}

// Repository 선언
public interface ProductRepository extends ElasticsearchRepository<Product, String> {}

// 색인 (훨씬 간단해짐)
productRepository.saveAll(batch);

// 카운트
productRepository.count();
```

**개선된 점:**

| 항목 | 변경 전 | 변경 후 |
|------|--------|--------|
| 색인 | `BulkRequest` 직접 구성 | `saveAll()` 한 줄 |
| 매핑 | Java 빌더 코드 | JSON 파일 + `@Field` 어노테이션 |
| 카운트 | `esClient.count()` | `repository.count()` |
| 타입 안전성 | `Map<String, Object>` | `Product` record |

**주의사항 - 검색 결과 역직렬화 문제:**

`Product.class`로 검색 결과를 역직렬화하려고 했지만 오류가 발생했습니다.

```
JsonpMappingException: Error deserializing Hit
hits.hits[0]._source에서 Jackson 오류
```

원인은 ES가 반환하는 `dense_vector` 필드(`name_vector`, `image_vector`)를 Java `float[]`로 바로 매핑하지 못하기 때문입니다.

해결 방법으로 검색 결과는 `Map.class`로 받아서 수동으로 `ProductResult`로 변환하는 방식을 채택했습니다.

```java
// 색인: Product 엔티티 사용 (벡터 포함)
productRepository.saveAll(batch);

// 검색: Map으로 받아서 수동 변환 (벡터 제외)
var response = esClient.search(request, Map.class);
parseResults(response.hits().hits());
```

**최종 구조:**
- 색인(쓰기): `ProductRepository.saveAll()` 사용
- 기본 조회(`count`, `exists`): `ProductRepository` 사용
- 검색(KNN + 집계): `ElasticsearchClient` 직접 사용

두 방식을 혼합해서 각각의 장점을 취했습니다.
Repository는 간단한 CRUD에, 직접 클라이언트는 복잡한 KNN 쿼리에 사용합니다.

---

## 3. DTO를 record로 선언한 이유

처음에는 `@Getter`, `@Builder`, `@AllArgsConstructor`가 붙은 일반 클래스로 DTO를 만들었습니다.

```java
// 변경 전
@Getter
@Builder
@AllArgsConstructor
public class SearchResponse {
    private int total;
    private List<ProductResult> results;
    private Aggregations aggregations;
}
```

이후 Java 16에서 정식 출시된 `record`로 변경했습니다.

```java
// 변경 후
public record SearchResponse(int total, List<ProductResult> results, Aggregations aggregations) {
    public static final SearchResponse EMPTY = new SearchResponse(0, List.of(), new Aggregations(null, null, Map.of()));
}
```

**record를 선택한 이유:**
- Lombok 없이도 생성자, getter, `equals()`, `hashCode()`, `toString()`이 자동 생성
- 불변 객체라서 값이 외부에서 변경될 위험 없음
- `@ConfigurationProperties`와 생성자 바인딩이 자연스럽게 동작
- setter가 없어서 Spring이 강제로 값을 변경하는 상황을 방지
- 코드가 훨씬 짧고 명확함

**setter 제거가 중요한 이유:**
Spring의 `@ConfigurationProperties`는 기본적으로 setter를 통해 값을 바인딩합니다.
record는 setter가 없기 때문에 생성자 바인딩을 사용합니다.
이 방식이 더 안전하고 명확합니다.
`@EnableConfigurationProperties(AppConfig.class)` 선언이 필요합니다.

---

## 4. SearchParams DTO 도입 이유

처음에는 검색 파라미터를 메서드 인자로 직접 전달했습니다.

```java
// 변경 전
public SearchResponse search(String query, String imageUrl, String site, String broadcastDate)
public SearchRequest buildTextQuery(float[] vector, String query, String index, String site, String broadcastDate)
```

파라미터가 4-5개가 되면서 문제가 생겼습니다.
- 메서드 호출 시 순서를 혼동하기 쉬움
- 새로운 필터 조건이 추가되면 모든 메서드 시그니처를 변경해야 함
- 코드 가독성이 낮음

`SearchParams` record로 묶었습니다.

```java
// 변경 후
public record SearchParams(String query, String imageUrl, String site, String broadcastDate) {}

public SearchResponse search(SearchParams params)
public SearchRequest buildTextQuery(float[] vector, String index, SearchParams params)
```

새로운 파라미터가 추가되어도 `SearchParams`만 수정하면 됩니다.

---

## 5. SearchException을 RuntimeException으로 만든 이유

Java의 예외는 두 종류입니다.

**Checked Exception:**
- `Exception`을 상속
- 메서드 시그니처에 `throws` 선언 필수
- 호출하는 모든 메서드가 처리하거나 전파해야 함
- 예: `IOException`, `OrtException`

**Unchecked Exception (RuntimeException):**
- `RuntimeException`을 상속
- `throws` 선언 불필요
- 필요한 곳에서만 처리하면 됨
- 예: `NullPointerException`, `IllegalArgumentException`

ES 검색 오류는 `SearchService`에서 발생하지만, 실제 처리(Circuit Breaker, 캐시 폴백)는 `SearchController`에서 합니다.
Checked Exception으로 만들면 중간에 있는 모든 메서드가 `throws`를 선언해야 합니다.
`RuntimeException`으로 만들면 실제로 처리할 곳(`SearchController`)에서만 catch하면 됩니다.

```java
// SearchException을 RuntimeException으로
public class SearchException extends RuntimeException {
    public SearchException(String message, Throwable cause) {
        super(message, cause);
    }
}

// SearchService - throws 선언 불필요
public SearchResponse search(SearchParams params) {
    try { ... }
    catch (Exception e) { throw new SearchException("검색 실패", e); }
}

// SearchController - SearchException만 잡으면 됨
try {
    SearchResponse result = searchService.search(params);
    ...
} catch (SearchException e) {
    circuitBreaker.recordFailure();
    ...
}
```

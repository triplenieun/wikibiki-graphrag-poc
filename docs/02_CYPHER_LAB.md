# Cypher를 직접 읽고 실행하기

먼저 [README](../README.md)의 설치와 `seed_graph`를 완료하세요. Neo4j Browser에서 `neo4j` 데이터베이스에 연결한 상태로 진행합니다. 각 코드 블록은 따로 실행합니다.

## 1. 가장 짧은 조회

```cypher
MATCH (service:Lab:Service)
RETURN service.id, service.name
ORDER BY service.id;
```

| 부분 | 의미 |
| --- | --- |
| `MATCH` | 다음 패턴과 일치하는 데이터를 찾기 |
| `(service:Lab:Service)` | `Lab`과 `Service` 라벨을 가진 노드를 `service`라는 변수로 부르기 |
| `RETURN` | 결과로 보여줄 값 선택 |
| `service.name` | 찾은 노드의 `name` 속성 |
| `ORDER BY` | 결과 순서 지정 |

예상 결과는 `auth-service`, `notification-service`, `order-service`, `payment-service` 4행입니다. `ORDER BY`가 없으면 표시 순서는 보장되지 않습니다.

`service`라는 변수명은 개발자가 정합니다. 노드의 라벨 `Service`나 속성명 `name`과 구분하세요. Cypher의 라벨·관계 유형·속성명은 정확한 대소문자를 사용합니다. [Cypher 이름 규칙](https://neo4j.com/docs/cypher-manual/current/syntax/naming/)

## 2. 실습 데이터 개수 확인

```cypher
MATCH (n:Lab)
RETURN count(n) AS node_count;
```

처음 제공된 예제만 적재했다면 `11`입니다.

```cypher
MATCH (:Lab)-[r]->(:Lab)
RETURN type(r) AS relationship_type, count(r) AS relationship_count
ORDER BY relationship_type;
```

| relationship_type | relationship_count |
| --- | ---: |
| `DEPENDS_ON` | 4 |
| `DESCRIBES` | 4 |
| `OWNED_BY` | 4 |

여기서 `count`는 개수, `type(r)`은 관계 유형입니다. `seed_graph`를 한 번 더 실행한 후 같은 쿼리로 개수가 늘어나지 않는지 확인해도 좋습니다. 직접 데이터를 추가했다면 전체 개수는 달라질 수 있습니다.

전체 그래프는 다음 쿼리의 **Graph** 보기에서 확인합니다.

```cypher
MATCH (a:Lab)-[r]->(b:Lab)
RETURN a, r, b;
```

## 3. 서비스에서 담당팀 찾기

```cypher
MATCH (service:Lab:Service)-[:OWNED_BY]->(team:Lab:Team)
RETURN service.name AS service_name, team.name AS team_name
ORDER BY service.id;
```

`-[:OWNED_BY]->`는 “왼쪽 서비스의 담당팀이 오른쪽 팀이다”라는 연결입니다. 관계 변수를 사용하지 않아 대괄호 안의 변수명은 생략했습니다. `AS`는 결과 열에 읽기 쉬운 이름을 붙입니다.

예상 결과:

| service_name | team_name |
| --- | --- |
| 인증 서비스 | 플랫폼팀 |
| 알림 서비스 | 플랫폼팀 |
| 주문 서비스 | 커머스팀 |
| 결제 서비스 | 결제팀 |

이 쿼리는 `OWNED_BY` 관계가 있는 서비스만 반환합니다. 팀이 없는 서비스도 표시하려면 서비스 조회 후 `OPTIONAL MATCH`로 팀을 연결합니다.

```cypher
MATCH (service:Lab:Service)
OPTIONAL MATCH (service)-[:OWNED_BY]->(team:Lab:Team)
RETURN service.name AS service_name, team.name AS team_name
ORDER BY service.id;
```

`OPTIONAL MATCH`는 관계가 없을 때도 이미 찾은 서비스 행을 유지하고, 없는 쪽 값을 `null`로 둡니다. 관계형 DB의 외부 조인과 비슷하게 이해할 수 있습니다. [OPTIONAL MATCH 공식 설명](https://neo4j.com/docs/cypher-manual/current/clauses/optional-match/)

## 4. 질문의 근거 묶기: 주문 서비스의 팀과 문서

[queries/03_service_context.cypher](../queries/03_service_context.cypher)를 열고 한 개의 쿼리 전체를 실행합니다. 핵심 패턴은 다음과 같습니다.

```cypher
MATCH (requested:Lab:Service {id: 'order-service'})
      -[:DEPENDS_ON*0..1]->(service:Lab:Service)
RETURN DISTINCT service.id AS service_id, service.name AS service_name
ORDER BY service_id;
```

`*0..1`은 관계를 **0개 또는 1개** 따라간다는 뜻입니다.

- 0개: 출발점인 주문 서비스 자체
- 1개: 주문 서비스가 직접 사용하는 인증·결제 서비스

알림 서비스는 주문 서비스의 직접 의존 대상이 아니므로 포함되지 않습니다. 같은 인증 서비스를 사용한다는 이유만으로 이 조회의 대상이 되지는 않습니다.

전체 파일의 쿼리는 각 서비스에 팀과 문서를 추가로 연결합니다. 예상 결과의 핵심 값은 다음과 같습니다.

| service_id | 담당팀 | 문서 ID |
| --- | --- | --- |
| `auth-service` | 플랫폼팀 | `auth-guide` |
| `order-service` | 커머스팀 | `order-guide` |
| `payment-service` | 결제팀 | `payment-guide` |

다음 문법도 함께 사용합니다.

- `WITH`: 중간 조회 결과를 다음 단계로 전달합니다.
- `DISTINCT`: 같은 대상을 중복 반환하지 않게 합니다.
- `collect(...)`: 여러 값을 리스트로 묶습니다.
- `document { .id, .title, .source }`: 문서 노드에서 해당 속성만 결과 객체에 담습니다.

문서의 `source`는 **저장소 기준 파일 경로**입니다. Neo4j가 이 경로를 자동으로 열지는 않습니다. 이 프로젝트에서는 Python 적재 코드가 파일을 직접 읽어 `body` 속성에 저장합니다. Cypher 연습 파일은 화면을 간결하게 유지하기 위해 제목·경로만 반환하고, Django의 `context` 명령과 API는 `body` 원문까지 반환합니다. 편집기에서 원본 파일을 열어 비교해 보세요.

## 5. 역방향 탐색: 인증 서비스의 영향 후보

[queries/04_impact.cypher](../queries/04_impact.cypher)의 첫 쿼리를 실행합니다. 핵심 관계는 다음처럼 **인증 서비스에 도착하는 방향**입니다.

```cypher
MATCH path = (affected:Lab:Service)-[:DEPENDS_ON*1..5]->
             (target:Lab:Service {id: 'auth-service'})
WHERE affected <> target
  AND all(node IN nodes(path) WHERE node:Lab AND node:Service)
RETURN affected.id AS affected_id, min(length(path)) AS minimum_hops
ORDER BY minimum_hops, affected_id;
```

- `path = ...`: 찾은 전체 경로를 변수에 담습니다.
- `*1..5`: 의존 관계를 1개부터 최대 5개까지 따라갑니다.
- `nodes(path)`: 경로 안의 노드 목록입니다.
- `all(...)`: 경로의 모든 노드가 실습 서비스인지 확인합니다.
- `length(path)`: 경로에 포함된 관계의 개수입니다.
- `min(...)`: 여러 경로가 있으면 가장 짧은 홉 수를 구합니다.

예상 결과:

| affected_id | minimum_hops |
| --- | ---: |
| `notification-service` | 1 |
| `order-service` | 1 |
| `payment-service` | 1 |

주문은 인증에 직접 의존하므로 최소 거리는 1홉입니다. 주문 → 결제 → 인증이라는 2홉 경로도 존재합니다. 같은 파일의 두 번째 쿼리를 실행하면 두 경로를 비교할 수 있습니다.

이 결과를 “세 서비스 모두 장애가 발생했다”라고 읽으면 안 됩니다. 저장된 의존 관계가 보여주는 **영향 후보**입니다. 우회 경로, 캐시, 호출 조건, 관계 누락 등 실제 운영 상황은 추가 확인이 필요합니다. 또한 현재 조회 범위인 5홉 바깥은 검사하지 않습니다.

## 6. 데이터는 어떻게 넣었을까?

실제 적재는 `seed_graph` 관리 명령이 처리합니다. 다음 Cypher는 문법을 설명하기 위한 예입니다.

```cypher
MERGE (service:Lab:Service {id: 'auth-service'})
SET service.name = '인증 서비스';
```

`MERGE`는 주어진 패턴이 있으면 사용하고, 없으면 생성합니다. 여기서는 ID가 같은 노드를 찾아 이름을 갱신합니다. `CREATE`는 새 노드를 생성하므로 같은 코드를 반복하면 중복 데이터가 생길 수 있습니다. [MERGE 공식 설명](https://neo4j.com/docs/cypher-manual/current/clauses/merge/)

다만 `MERGE`가 모든 데이터 정리를 자동으로 해주지는 않습니다. 원본에서 사라진 관계 삭제나 이름이 다른 동일 개체 통합은 별도 정책이 필요합니다. `seed_graph`를 반복 실행하면 샘플 속성은 갱신되지만, 제거된 원본 항목까지 DB에서 삭제하지는 않습니다. 예를 들어 서비스의 `owner_id`를 바꾸면 새 팀 관계를 만들고 이전 팀 관계는 남깁니다. 현재 조회 코드와 기대 결과는 제공된 예제처럼 서비스마다 담당팀이 하나라는 전제를 사용합니다.

Python 코드에서는 값과 쿼리 문자열을 분리해 **파라미터**로 전달합니다.

```python
query = "MATCH (s:Lab:Service {id: $service_id}) RETURN s.name AS name"
parameters = {"service_id": "auth-service"}
```

`$service_id`는 Python 문자열 치환이 아니라 Neo4j가 받는 질의 파라미터입니다. 사용자 입력을 f-string으로 Cypher에 직접 끼워 넣지 않습니다. 프로젝트의 조회 코드를 읽을 때 이 구분을 확인하세요.

## 7. 직접 풀어보기

1. 플랫폼팀이 담당하는 서비스 이름을 조회하세요. 예상: 인증, 알림.
2. 결제 서비스가 직접 의존하는 서비스를 조회하세요. 예상: 인증.
3. 인증 서비스를 설명하는 문서의 제목과 원본 경로를 조회하세요. 예상: `auth-guide` 문서 1개.
4. 주문 서비스에서 인증 서비스로 이어지는 두 경로의 길이를 조회하세요. 예상: 1, 2.
5. `context` 조회의 출발점을 `payment-service`로 바꾸면 어떤 서비스가 나올지 예상하고 실행하세요. 예상: 결제, 인증.

추가 문제와 주석 처리된 답안은 [queries/05_practice.cypher](../queries/05_practice.cypher)에 있습니다. 답안을 실행하려면 해당 답안 블록의 `//` 주석을 제거한 부분만 복사하세요. 처음에는 데이터를 바꾸기보다, 질문을 관계의 방향으로 바꿔 표현하는 연습에 집중하면 좋습니다.

## 쿼리 파일 안내

| 파일 | 사용하는 시점 |
| --- | --- |
| [00_constraints.cypher](../queries/00_constraints.cypher) | 제약 조건 생성 문법을 읽을 때. `seed_graph`가 이미 생성합니다. |
| [01_explore.cypher](../queries/01_explore.cypher) | 전체 그래프와 데이터 개수 확인 |
| [02_services_and_teams.cypher](../queries/02_services_and_teams.cypher) | 서비스·팀 조회와 관계 방향 비교 |
| [03_service_context.cypher](../queries/03_service_context.cypher) | 질문에 필요한 관련 팀·문서 모으기 |
| [04_impact.cypher](../queries/04_impact.cypher) | 의존성의 역방향 탐색과 경로 비교 |
| [05_practice.cypher](../queries/05_practice.cypher) | 직접 풀어보는 문제와 답안 |

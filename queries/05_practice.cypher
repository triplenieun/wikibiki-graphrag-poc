// 연습문제: 먼저 직접 쿼리를 작성한 뒤 주석 처리된 답안과 비교하세요.
// 답안의 각 줄에서 //를 제거한 블록 하나만 Browser에 붙여 넣으면 됩니다.
// 예제 데이터가 그대로 적재되어 있다는 기준입니다.

// 문제 1. 모든 서비스의 id와 이름을 조회하세요. 예상: 4행.
// MATCH (service:Lab:Service)
// RETURN service.id AS id, service.name AS name
// ORDER BY id;

// 문제 2. 결제 서비스의 담당팀을 찾으세요. 예상: 결제팀.
// MATCH (:Lab:Service {id: 'payment-service'})-[:OWNED_BY]->(team:Lab:Team)
// RETURN team.name AS team_name;

// 문제 3. 인증 서비스를 설명하는 문서의 제목과 경로를 찾으세요.
// 예상: 인증 서비스 확인 가이드, docs/samples/auth-guide.md.
// MATCH (document:Lab:Document)-[:DESCRIBES]->(:Lab:Service {id: 'auth-service'})
// RETURN document.title AS title, document.source AS source;

// 문제 4. 플랫폼팀 담당 서비스의 관련 문서를 찾으세요. 예상: 인증/알림 문서 2행.
// MATCH (document:Lab:Document)-[:DESCRIBES]->(service:Lab:Service)
//       -[:OWNED_BY]->(:Lab:Team {id: 'platform-team'})
// RETURN service.name AS service_name, document.title AS title,
//        document.source AS source
// ORDER BY service.id;

// 문제 5. 각 서비스의 직접 의존 서비스 수를 세세요.
// 예상: auth 0, notification 1, order 2, payment 1 (id 기준).
// 힌트: OPTIONAL MATCH와 count(dependency)를 사용하면 의존성이 0개인 행도 나옵니다.
// count(*)는 행을 세므로 OPTIONAL MATCH 뒤의 0개 관계를 세는 데 부적절합니다.
// MATCH (service:Lab:Service)
// OPTIONAL MATCH (service)-[:DEPENDS_ON]->(dependency:Lab:Service)
// RETURN service.id AS service_id, count(DISTINCT dependency) AS dependency_count
// ORDER BY service_id;

// 문제 6. 주문 서비스에서 인증 서비스까지의 경로가 왜 두 개인지 설명해 보세요.
// 답: order -> auth, order -> payment -> auth 두 경로가 저장되어 있습니다.
// queries/04_impact.cypher의 두 번째 쿼리로 확인할 수 있습니다.

// 문제 7. 인증 서비스 장애의 영향 후보에 주문 서비스가 몇 번 나와야 할까요?
// 답: 서비스 목록이라면 한 번입니다. 경로 목록이라면 두 경로가 나올 수 있습니다.
// 반환하려는 대상(서비스/경로)이 무엇인지 먼저 결정해야 합니다.

// 문제 8. 조회 결과에 없는 서비스는 인증 서비스 장애의 영향이 없다고 단정할 수 있나요?
// 답: 아니요. 관계 데이터가 빠졌거나 조회 범위인 5홉 밖에 있을 수 있습니다.
// 저장된 의존성만으로 실제 장애 전파까지 확정할 수도 없습니다.

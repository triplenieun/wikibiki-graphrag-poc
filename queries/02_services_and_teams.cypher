// 각 블록을 하나씩 실행하세요. 이 파일의 쿼리는 데이터를 수정하지 않습니다.

// 1. 모든 서비스와 담당팀: 서비스 4개가 나옵니다.
MATCH (service:Lab:Service)-[:OWNED_BY]->(team:Lab:Team)
RETURN service.id AS service_id, service.name AS service_name,
       team.name AS team_name
ORDER BY service_id;

// 2. 플랫폼팀 담당 서비스: 인증 서비스, 알림 서비스입니다.
// 관계는 Service -> Team으로 저장됩니다. 팀을 오른쪽에 놓고 조회합니다.
MATCH (service:Lab:Service)-[:OWNED_BY]->(team:Lab:Team {id: 'platform-team'})
RETURN team.name AS team_name, service.name AS service_name
ORDER BY service.id;

// 3. 주문 서비스가 직접 의존하는 서비스: 인증 서비스, 결제 서비스입니다.
MATCH (service:Lab:Service {id: 'order-service'})
      -[:DEPENDS_ON]->(dependency:Lab:Service)
RETURN service.name AS service_name, dependency.name AS dependency_name
ORDER BY dependency.id;

// 4. 반대로 인증 서비스에 직접 의존하는 서비스는 무엇일까요?
// 결과: 알림 서비스, 주문 서비스, 결제 서비스 (id 기준 정렬).
MATCH (dependent:Lab:Service)-[:DEPENDS_ON]->(target:Lab:Service {id: 'auth-service'})
RETURN dependent.id AS dependent_id, dependent.name AS dependent_name,
       target.name AS dependency_name
ORDER BY dependent_id;

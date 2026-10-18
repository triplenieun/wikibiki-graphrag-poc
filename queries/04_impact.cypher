// 질문: "인증 서비스를 사용하는 서비스와 그 간접 사용자는 누구인가?"
// DEPENDS_ON 화살표가 인증 서비스로 들어오는 방향을 확인하세요.
// *1..5는 관계를 최소 1개, 최대 5개 따라가는 경로입니다.
// 모든 경로의 노드가 Lab:Service인지 확인해 실습 서비스만 탐색합니다.
// 같은 서비스가 여러 경로로 연결되어도 서비스별 한 행으로 묶습니다.
// 순환 관계가 있더라도 인증 서비스 자기 자신은 영향 후보에서 제외합니다.
// 결과는 영향 가능성입니다. 실제 장애 여부/영향 범위를 확정하지 않습니다.
// 결과가 없더라도 5홉 밖 경로나 기록되지 않은 의존성이 없다는 뜻은 아닙니다.

MATCH path = (affected:Lab:Service)-[:DEPENDS_ON*1..5]->
             (target:Lab:Service {id: 'auth-service'})
WHERE affected <> target
  AND all(node IN nodes(path) WHERE node:Lab AND node:Service)
WITH affected, min(length(path)) AS minimum_hops
OPTIONAL MATCH (affected)-[:OWNED_BY]->(team:Lab:Team)
RETURN affected.id AS affected_id,
       affected.name AS affected_name,
       minimum_hops,
       collect(DISTINCT team.name) AS owner_teams
ORDER BY minimum_hops, affected_id;

// 예상: notification-service, order-service, payment-service 각 1행, 최소 홉 수 모두 1.
// order -> payment -> auth의 2홉 경로도 있지만 order -> auth가 있으므로 최소는 1입니다.

// 추가 관찰: 인증 서비스로 이어지는 경로를 직접 확인합니다.
// 주문 서비스의 직접 경로(1홉)와 결제 서비스를 거치는 경로(2홉)를 비교하세요.
MATCH path = (service:Lab:Service {id: 'order-service'})
             -[:DEPENDS_ON*1..5]->(target:Lab:Service {id: 'auth-service'})
WHERE all(node IN nodes(path) WHERE node:Lab AND node:Service)
RETURN [node IN nodes(path) | node.name] AS service_path,
       length(path) AS hops
ORDER BY hops;

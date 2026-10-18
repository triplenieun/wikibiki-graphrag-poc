// 질문: "주문 서비스와 직접 의존 서비스의 담당팀, 관련 문서는 무엇인가?"
// 0홉은 주문 서비스 자체, 1홉은 바로 연결된 의존 서비스입니다.
// 예제에서는 주문/인증/결제 3개 서비스가 나옵니다. 알림 서비스는 제외됩니다.
// OPTIONAL MATCH는 팀/문서가 없더라도 이미 찾은 서비스 행을 남겨 둡니다.
// DISTINCT는 같은 서비스나 문서가 중복 표시되는 것을 방지합니다.
// source는 저장소 기준의 문서 경로입니다. Neo4j가 원문을 읽어오는 것은 아닙니다.

MATCH (requested:Lab:Service {id: 'order-service'})
      -[:DEPENDS_ON*0..1]->(service:Lab:Service)
WITH DISTINCT requested, service
OPTIONAL MATCH (service)-[:OWNED_BY]->(team:Lab:Team)
OPTIONAL MATCH (document:Lab:Document)-[:DESCRIBES]->(service)
RETURN service.id AS service_id,
       service.name AS service_name,
       CASE WHEN service = requested THEN '요청한 서비스'
            ELSE '직접 의존 서비스' END AS context_role,
       collect(DISTINCT team.name) AS owner_teams,
       collect(DISTINCT document { .id, .title, .source }) AS documents
ORDER BY service_id;

// Neo4j Browser에서 세미콜론으로 끝나는 블록을 하나씩 복사해 실행하세요.
// 처음에는 표(Table)와 그래프(Graph) 보기의 차이를 살펴보세요.

// 1. 실습 노드와 관계를 그래프로 보기. 고립된 노드도 표시합니다.
MATCH (n:Lab)
OPTIONAL MATCH (n)-[r]->(m:Lab)
RETURN n, r, m;

// 2. 노드 수: 새 실습 DB에 예제만 적재했다면 11입니다.
MATCH (n:Lab)
RETURN count(n) AS node_count;

// 3. 관계 수: 예제만 적재했다면 12입니다.
// 화살표 방향을 명시해 관계를 한 방향으로만 셉니다.
MATCH (:Lab)-[r]->(:Lab)
RETURN count(r) AS relationship_count;

// 4. 관계 종류별 수: DEPENDS_ON 4, DESCRIBES 4, OWNED_BY 4입니다.
MATCH (:Lab)-[r]->(:Lab)
RETURN type(r) AS relationship_type, count(r) AS relationship_count
ORDER BY relationship_type;

// 5. 노드의 라벨과 속성 보기. 라벨 배열의 순서는 보장되지 않습니다.
MATCH (n:Lab)
RETURN n.id AS id, labels(n) AS labels, properties(n) AS properties
ORDER BY id;

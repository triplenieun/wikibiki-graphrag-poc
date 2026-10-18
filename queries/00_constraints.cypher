// Lab 노드의 id를 고유하게 만듭니다. 같은 id를 두 번 만들 수 없습니다.
// 데이터 적재 명령도 이 제약조건을 생성합니다. 반복 실행해도 안전합니다.
// 모든 실습 노드는 Lab 라벨과 역할 라벨(Service/Team/Document)을 함께 갖습니다.
CREATE CONSTRAINT lab_node_id IF NOT EXISTS
FOR (n:Lab) REQUIRE n.id IS UNIQUE;

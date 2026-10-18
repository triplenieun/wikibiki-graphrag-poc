"""Load synthetic fixtures, then write all fixture data in one transaction."""
import json
from pathlib import Path

from django.conf import settings

from graphlab.db import graph_session, run, write as write_transaction

CONSTRAINT = "CREATE CONSTRAINT lab_node_id IF NOT EXISTS FOR (n:Lab) REQUIRE n.id IS UNIQUE"


def load_sample():
    root = Path(settings.BASE_DIR)
    data = json.loads((root / "data/sample_graph.json").read_text(encoding="utf-8-sig"))
    all_ids = [row["id"] for key in ("teams", "services", "documents") for row in data[key]]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("예제 데이터의 id는 모든 노드에서 고유해야 합니다.")
    teams = {row["id"] for row in data["teams"]}
    services = {row["id"] for row in data["services"]}
    for service in data["services"]:
        if service["owner_id"] not in teams:
            raise ValueError("서비스의 owner_id가 존재하지 않습니다.")
    for edge in data["dependencies"]:
        if edge["source_id"] not in services or edge["target_id"] not in services:
            raise ValueError("의존 관계가 존재하지 않는 서비스를 참조합니다.")
    for doc in data["documents"]:
        if doc["service_id"] not in services:
            raise ValueError("문서의 service_id가 존재하지 않습니다.")
        source = (root / doc["source"]).resolve()
        if not source.is_relative_to((root / "docs/samples").resolve()):
            raise ValueError("문서 source는 docs/samples 안의 경로여야 합니다.")
        doc["body"] = source.read_text(encoding="utf-8-sig")
    return data


def seed_graph():
    data = load_sample()

    def write(tx):
        run(tx, """
            UNWIND $rows AS row
            MERGE (t:Lab {id: row.id})
            SET t:Team, t.name = row.name
        """, rows=data["teams"])
        run(tx, """
            UNWIND $rows AS row
            MERGE (s:Lab {id: row.id})
            SET s:Service, s.name = row.name, s.description = row.description,
                s.description_source = 'seed'
            WITH s, row
            MATCH (t:Lab:Team {id: row.owner_id})
            MERGE (s)-[r:OWNED_BY]->(t)
            SET r.managed_by_documents = false
        """, rows=data["services"])
        run(tx, """
            UNWIND $rows AS row
            MERGE (d:Lab {id: row.id})
            SET d:Document, d.title = row.title, d.source = row.source, d.body = row.body
            WITH d, row
            MATCH (s:Lab:Service {id: row.service_id})
            MERGE (d)-[:DESCRIBES]->(s)
        """, rows=data["documents"])
        run(tx, """
            UNWIND $rows AS row
            MATCH (a:Lab:Service {id: row.source_id}), (b:Lab:Service {id: row.target_id})
            MERGE (a)-[r:DEPENDS_ON]->(b)
            SET r.managed_by_documents = false
        """, rows=data["dependencies"])

    with graph_session() as session:
        # Schema statements run separately from the fixture data transaction.
        session.run(CONSTRAINT).consume()
        write_transaction(session, write)
    return {
        "teams": len(data["teams"]), "services": len(data["services"]),
        "documents": len(data["documents"]), "dependencies": len(data["dependencies"]),
    }

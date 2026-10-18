"""Opt-in atomic writes against Neo4j; only UUID-scoped fixtures are removed.

NEO4J_INTEGRATION=1 explicitly enables these tests on the configured lab DB.
They never touch seed IDs or remove the shared ingestion lock/schema.
"""
import os
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.test import SimpleTestCase

from graphlab import graphrag, ingestion
from graphlab.db import graph_session, run, write


@skipUnless(os.getenv("NEO4J_INTEGRATION") == "1", "Set NEO4J_INTEGRATION=1 for a dedicated Neo4j lab database.")
class DocumentIngestionIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.prefix = "it-" + uuid4().hex
        self.document = {"id": self.prefix + "-doc", "title": "통합 등록 검증", "body": "신규 서비스는 연결 서비스에 의존하고 검증팀이 담당한다.", "source": "통합 테스트"}
        self.nodes = [
            {"id": self.prefix + "-service", "kind": "Service", "name": self.prefix + " 신규 서비스", "description": "통합 테스트 서비스"},
            {"id": self.prefix + "-dependency", "kind": "Service", "name": self.prefix + " 연결 서비스", "description": ""},
            {"id": self.prefix + "-team", "kind": "Team", "name": self.prefix + " 검증팀", "description": ""},
        ]
        self.edges = [
            {"source_id": self.document["id"], "type": "DESCRIBES", "target_id": self.nodes[0]["id"], "evidence": self.document["body"]},
            {"source_id": self.nodes[0]["id"], "type": "DEPENDS_ON", "target_id": self.nodes[1]["id"], "evidence": self.document["body"]},
            {"source_id": self.nodes[0]["id"], "type": "OWNED_BY", "target_id": self.nodes[2]["id"], "evidence": self.document["body"]},
        ]
        self.owned_ids = [self.document["id"], *[node["id"] for node in self.nodes]]
        self.payload = {"review_token": signing.dumps(self.document, salt=ingestion.SALT), "nodes": self.nodes, "relations": self.edges}

    def tearDown(self):
        with graph_session() as session:
            def cleanup(tx):
                run(tx, "MATCH (a:Lab:Assertion) WHERE a.document_id IN $ids DETACH DELETE a", ids=self.owned_ids)
                run(tx, "MATCH (n:Lab) WHERE n.id IN $ids DETACH DELETE n", ids=self.owned_ids)
            write(session, cleanup)

    def test_approved_document_and_relations_are_immediately_retrievable_and_idempotent(self):
        first = ingestion.save(self.payload)
        second = ingestion.save(self.payload)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        evidence = graphrag.retrieve("신규 서비스 담당팀?", service_id=self.nodes[0]["id"])
        self.assertIn(self.document["id"], [source["document_id"] for source in evidence["sources"]])
        self.assertIn(self.document["body"], [source["body"] for source in evidence["sources"]])
        self.assertIn({"source": self.nodes[0]["id"], "target": self.nodes[1]["id"], "type": "DEPENDS_ON"}, evidence["graph"]["edges"])
        self.assertTrue(any(self.nodes[2]["name"] in fact for fact in evidence["facts"]))
        with graph_session() as session:
            assertions = session.execute_read(lambda tx: run(tx, "MATCH (a:Lab:Assertion {document_id:$id}) RETURN a.evidence AS evidence", id=self.document["id"]))
        self.assertEqual(len(assertions), 3)
        self.assertTrue(all(row["evidence"] == self.document["body"] for row in assertions))

    def test_existing_owner_conflict_rolls_back_all_document_data(self):
        owner = self.prefix + "-old-team"
        self.owned_ids.append(owner)
        with graph_session() as session:
            write(session, lambda tx: run(tx, "CREATE (s:Lab:Service {id:$id, name:$name})-[:OWNED_BY]->(:Lab:Team {id:$owner, name:'기존 팀'})", id=self.nodes[0]["id"], name=self.nodes[0]["name"], owner=owner))
        with self.assertRaises(ingestion.ReviewConflict):
            ingestion.save(self.payload)
        with graph_session() as session:
            rows = session.execute_read(lambda tx: run(tx, "MATCH (n:Lab) WHERE n.id IN $ids RETURN n.id AS id ORDER BY id", ids=self.owned_ids))
        self.assertEqual({row["id"] for row in rows}, {owner, self.nodes[0]["id"]})

    def test_document_describing_multiple_services_is_one_source_with_all_edges(self):
        self.edges.append({"source_id": self.document["id"], "type": "DESCRIBES", "target_id": self.nodes[1]["id"], "evidence": self.document["body"]})
        ingestion.save(self.payload)
        evidence = graphrag.retrieve("문서 확인", service_id=self.nodes[0]["id"])
        sources = [row for row in evidence["sources"] if row["document_id"] == self.document["id"]]
        self.assertEqual(len(sources), 1)
        self.assertEqual(set(sources[0]["service_ids"]), {self.nodes[0]["id"], self.nodes[1]["id"]})
        described = [edge for edge in evidence["graph"]["edges"] if edge["type"] == "DESCRIBES" and edge["source"] == self.document["id"]]
        self.assertEqual(len(described), 2)
        from graphlab.repository import service_context
        documents = service_context(self.nodes[0]["id"])["documents"]
        self.assertEqual(len([doc for doc in documents if doc["id"] == self.document["id"]]), 1)

    def test_error_after_document_creation_rolls_back_nodes_edges_and_document(self):
        class DeliberateFailure(Exception):
            pass

        def fail_assertion(tx, query, **kwargs):
            if "MERGE (a:Lab:Assertion" in query:
                raise DeliberateFailure("simulated mid-transaction failure")
            return run(tx, query, **kwargs)

        with patch("graphlab.ingestion.run", side_effect=fail_assertion), self.assertRaises(DeliberateFailure):
            ingestion.save(self.payload)
        with graph_session() as session:
            rows = session.execute_read(lambda tx: run(tx, "MATCH (n:Lab) WHERE n.id IN $ids RETURN count(n) AS count", ids=self.owned_ids))
        self.assertEqual(rows, [{"count": 0}])

    def test_existing_node_metadata_is_not_overwritten_and_document_id_collision_rejected(self):
        with graph_session() as session:
            write(session, lambda tx: run(tx, "CREATE (:Lab:Service {id:$id,name:$name,description:'원본 설명'})", id=self.nodes[0]["id"], name=self.nodes[0]["name"]))
        ingestion.save(self.payload)
        with graph_session() as session:
            rows = session.execute_read(lambda tx: run(tx, "MATCH (n:Lab {id:$id}) RETURN n.description AS description", id=self.nodes[0]["id"]))
        self.assertEqual(rows[0]["description"], "원본 설명")
        self.payload["nodes"][0]["description"] = "다르게 승인한 내용"
        with self.assertRaises(ingestion.ReviewConflict):
            ingestion.save(self.payload)

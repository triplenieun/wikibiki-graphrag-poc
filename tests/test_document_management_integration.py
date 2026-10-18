"""Opt-in lifecycle tests; cleanup touches only test-generated UUID identities."""
import copy
import os
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.test import SimpleTestCase

from graphlab import document_management as management, graphrag, ingestion
from graphlab.db import graph_session, run, write


@skipUnless(os.getenv("NEO4J_INTEGRATION") == "1", "Set NEO4J_INTEGRATION=1 for the Neo4j lab.")
class DocumentManagementIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.prefix = "life-" + uuid4().hex
        self.document = {"id": self.prefix + "-doc", "title": self.prefix + " 검증 문서", "body": "검증 서비스는 연결 서비스를 호출하고 최초팀이 담당한다.", "source": "통합 검증"}
        self.nodes = [
            {"id": self.prefix + "-service", "kind": "Service", "name": self.prefix + " 검증 서비스", "description": self.document["body"]},
            {"id": self.prefix + "-dependency", "kind": "Service", "name": self.prefix + " 연결 서비스", "description": ""},
            {"id": self.prefix + "-team", "kind": "Team", "name": self.prefix + " 최초팀", "description": ""},
        ]
        self.edges = [
            {"source_id": self.document["id"], "type": "DESCRIBES", "target_id": self.nodes[0]["id"], "evidence": self.document["body"]},
            {"source_id": self.nodes[0]["id"], "type": "DEPENDS_ON", "target_id": self.nodes[1]["id"], "evidence": self.document["body"]},
            {"source_id": self.nodes[0]["id"], "type": "OWNED_BY", "target_id": self.nodes[2]["id"], "evidence": self.document["body"]},
        ]
        self.owned = [self.document["id"], *[node["id"] for node in self.nodes]]
        self.create_payload = {"review_token": signing.dumps(self.document, salt=ingestion.SALT), "nodes": self.nodes, "relations": self.edges}
        ingestion.save(self.create_payload)

    def tearDown(self):
        with graph_session() as session:
            def cleanup(tx):
                run(tx, "MATCH (a:Lab:Assertion) WHERE a.document_id IN $ids DETACH DELETE a", ids=self.owned)
                run(tx, "MATCH (n:Lab) WHERE n.id IN $ids DETACH DELETE n", ids=self.owned)
            write(session, cleanup)

    def query(self, statement, **params):
        with graph_session() as session:
            return session.execute_read(lambda tx: run(tx, statement, **params))

    def modify_graph(self, statement, **params):
        with graph_session() as session:
            return write(session, lambda tx: run(tx, statement, **params))

    def draft(self, body=None, nodes=None, edges=None):
        before = management.detail(self.document["id"])
        signed = {**self.document, "body": body or self.document["body"], "_operation": "update", "_base_version": before["document"]["version"]}
        changed_edges = copy.deepcopy(self.edges if edges is None else edges)
        if body:
            for edge in changed_edges:
                edge["evidence"] = body
        return {"review_token": signing.dumps(signed, salt=ingestion.SALT), "nodes": copy.deepcopy(self.nodes if nodes is None else nodes), "relations": changed_edges}

    def second_document(self):
        second = {**self.document, "id": self.prefix + "-second", "title": self.prefix + " 두 번째 문서"}
        self.owned.append(second["id"])
        edges = [{**edge, "source_id": second["id"] if edge["type"] == "DESCRIBES" else edge["source_id"]} for edge in self.edges]
        ingestion.save({"review_token": signing.dumps(second, salt=ingestion.SALT), "nodes": self.nodes, "relations": edges})
        return second

    def test_update_replaces_original_text_and_unsupported_facts_in_retrieval(self):
        previous = management.detail(self.document["id"])
        body = "검증 서비스는 현재 문서 보관을 담당한다."
        approved = self.draft(body=body, nodes=self.nodes[:1], edges=self.edges[:1])
        changed = management.update(self.document["id"], approved)
        self.assertNotEqual(changed["document"]["version"], previous["document"]["version"])
        result = graphrag.retrieve("검증 문서", service_id=self.nodes[0]["id"])
        source = next(item for item in result["sources"] if item["document_id"] == self.document["id"])
        self.assertEqual(source["body"], body)
        self.assertFalse(any(edge["type"] in ("OWNED_BY", "DEPENDS_ON") for edge in result["graph"]["edges"]))
        self.assertEqual(self.query("MATCH (a:Lab:Assertion {document_id:$id}) RETURN count(a) AS n", id=self.document["id"]), [{"n": 1}])
        retry = management.update(self.document["id"], approved)
        self.assertEqual(retry["document"]["version"], changed["document"]["version"])
        with self.assertRaises(ingestion.ReviewConflict):
            management.delete(self.document["id"], {"version": previous["document"]["version"]})

    def test_delete_removes_document_only_supported_facts_and_prevents_resurrection(self):
        version = management.detail(self.document["id"])["document"]["version"]
        result = management.delete(self.document["id"], {"version": version})
        self.assertTrue(result["deleted"])
        self.assertTrue(management.delete(self.document["id"], {"version": version})["deleted"])
        with self.assertRaises(management.DocumentNotFound):
            management.detail(self.document["id"])
        with self.assertRaises(ingestion.ReviewConflict):
            ingestion.save(self.create_payload)
        evidence = graphrag.retrieve("검증 문서", service_id=self.nodes[0]["id"])
        self.assertNotIn(self.document["id"], [source["document_id"] for source in evidence["sources"]])
        self.assertFalse(any(edge["source"] == self.nodes[0]["id"] for edge in evidence["graph"]["edges"]))
        self.assertEqual(self.query("MATCH (n:Lab) WHERE n.id IN $ids RETURN count(n) AS n", ids=[n["id"] for n in self.nodes]), [{"n": 3}])
        self.assertEqual(set(self.query("MATCH (d:Lab:DocumentTombstone {id:$id}) RETURN keys(d) AS keys", id=self.document["id"])[0]["keys"]), {"id", "deleted_version", "deleted_at"})

    def test_shared_facts_survive_first_delete_and_disappear_after_last_support(self):
        second = self.second_document()
        for document in (self.document, second):
            version = management.detail(document["id"])["document"]["version"]
            management.delete(document["id"], {"version": version})
            rows = self.query("MATCH (:Lab:Service {id:$id})-[r:DEPENDS_ON|OWNED_BY]->() RETURN count(r) AS n", id=self.nodes[0]["id"])
            self.assertEqual(rows[0]["n"], 2 if document is self.document else 0)

    def test_manual_and_legacy_relationships_are_preserved_with_warning(self):
        for marker in ("REMOVE r.managed_by_documents", "SET r.managed_by_documents=false"):
            with self.subTest(marker=marker):
                self.modify_graph("MATCH (:Lab:Service {id:$id})-[r:DEPENDS_ON|OWNED_BY]->() " + marker, id=self.nodes[0]["id"])
                detail = management.detail(self.document["id"])
                self.assertTrue(detail["warnings"])
        result = management.delete(self.document["id"], {"version": detail["document"]["version"]})
        self.assertTrue(result["warnings"])
        self.assertEqual(self.query("MATCH (:Lab:Service {id:$id})-[r:DEPENDS_ON|OWNED_BY]->() RETURN count(r) AS n", id=self.nodes[0]["id"])[0]["n"], 2)

    def test_owner_can_change_only_when_no_other_document_supports_old_owner(self):
        second = self.second_document()
        replacement = {"id": self.prefix + "-new-team", "kind": "Team", "name": self.prefix + " 변경팀", "description": ""}
        self.owned.append(replacement["id"])
        nodes = self.nodes[:2] + [replacement]
        edges = self.edges[:2] + [{**self.edges[2], "target_id": replacement["id"]}]
        draft = self.draft(body="검증 서비스는 연결 서비스를 호출하고 변경팀이 담당한다.", nodes=nodes, edges=edges)
        old_version = management.detail(self.document["id"])["document"]["version"]
        with self.assertRaises(ingestion.ReviewConflict):
            management.update(self.document["id"], draft)
        self.assertEqual(management.detail(self.document["id"])["document"]["version"], old_version)
        self.assertEqual(self.query("MATCH (a:Lab:Assertion {document_id:$id}) RETURN count(a) AS n", id=self.document["id"])[0]["n"], 3)
        management.delete(second["id"], {"version": management.detail(second["id"])["document"]["version"]})
        management.update(self.document["id"], draft)
        self.assertEqual(self.query("MATCH (:Lab:Service {id:$id})-[:OWNED_BY]->(t) RETURN t.id AS id", id=self.nodes[0]["id"]), [{"id": replacement["id"]}])

    def test_stale_update_and_delete_are_rejected_and_seed_docs_are_read_only(self):
        stale = self.draft()
        management.update(self.document["id"], self.draft(body="검증 서비스의 새 근거이며 연결 서비스를 호출하고 최초팀이 담당한다."))
        with self.assertRaises(ingestion.ReviewConflict):
            management.update(self.document["id"], stale)
        seed_id = self.prefix + "-seed"
        self.owned.append(seed_id)
        self.modify_graph("CREATE (:Lab:Document {id:$id,title:'읽기 전용',body:'내용',source:''})", id=seed_id)
        seed = management.detail(seed_id)
        self.assertFalse(seed["can_manage"])
        self.assertIsNone(seed["review_token"])
        with self.assertRaises(ingestion.ReviewConflict):
            management.delete(seed_id, {"version": seed["document"]["version"]})

    def test_transaction_failure_restores_old_assertions_relationships_and_body(self):
        before = management.detail(self.document["id"])
        class DeliberateFailure(Exception):
            pass
        def fail_assertion(tx, query, **params):
            if "MERGE (a:Lab:Assertion" in query:
                raise DeliberateFailure("test rollback")
            return run(tx, query, **params)
        with patch("graphlab.document_management.run", side_effect=fail_assertion), self.assertRaises(DeliberateFailure):
            management.update(self.document["id"], self.draft(body="수정된 문서에서 검증 서비스는 연결 서비스를 호출하고 최초팀이 담당한다."))
        after = management.detail(self.document["id"])
        self.assertEqual(after["document"]["version"], before["document"]["version"])
        self.assertEqual(after["relations"], before["relations"])

    def test_list_pagination_search_and_detail_manual_review_token(self):
        self.second_document()
        first = management.listing(self.prefix, 0, 1)
        self.assertEqual(first["total"], 2)
        self.assertTrue(first["has_more"])
        self.assertNotIn("body", first["documents"][0])
        second = management.listing(self.prefix, 1, 1)
        self.assertFalse(second["has_more"])
        self.assertNotEqual(first["documents"][0]["id"], second["documents"][0]["id"])
        detail = management.detail(self.document["id"])
        result = management.update(self.document["id"], detail)
        self.assertEqual(result["document"]["body"], self.document["body"])

    def test_document_summaries_never_survive_as_independent_llm_facts(self):
        def no_summary_evidence(service_ids, summaries):
            for service_id in service_ids:
                for intent in ("context", "impact"):
                    evidence = graphrag.retrieve("검증", service_id=service_id, intent=intent)
                    self.assertEqual(evidence["service"]["description"], "")
                    for summary in summaries:
                        self.assertFalse(any(summary in fact for fact in evidence["facts"]))
                    # Both service resolution and scoped path rows feed LLM
                    # context, so neither may carry a cached document summary.
                    for trace in evidence["trace"][:2]:
                        for row in trace["rows"]:
                            if row["service"]["id"] in service_ids:
                                self.assertEqual(row["service"]["description"], "")
        primary = self.nodes[0]["id"]
        old_summary = self.document["body"]
        self.assertEqual(self.query("MATCH (s:Lab:Service {id:$id}) RETURN s.description_source AS origin,s.description AS description", id=primary),
                         [{"origin": "document", "description": old_summary}])
        no_summary_evidence([primary], [old_summary])

        dependency = {"id": self.prefix + "-replacement", "kind": "Service", "name": self.prefix + " 새 연결 서비스", "description": "과거 요약: 새 연결 서비스는 변경팀이 담당합니다."}
        team = {"id": self.prefix + "-replacement-team", "kind": "Team", "name": self.prefix + " 변경팀", "description": "문서에서 생성한 담당팀 요약"}
        self.owned.extend([dependency["id"], team["id"]])
        body = "검증 서비스는 새 연결 서비스를 호출하고 새 연결 서비스는 변경팀이 담당한다."
        edges = [self.edges[0], {**self.edges[1], "target_id": dependency["id"]},
                 {**self.edges[2], "source_id": dependency["id"], "target_id": team["id"]}]
        management.update(self.document["id"], self.draft(body=body, nodes=[self.nodes[0], dependency, team], edges=edges))
        for node in (dependency, team):
            self.assertEqual(self.query("MATCH (n:Lab {id:$id}) RETURN n.description_source AS origin,n.description AS description", id=node["id"]),
                             [{"origin": "document", "description": node["description"]}])
        no_summary_evidence([primary, dependency["id"]], [old_summary, dependency["description"]])
        management.delete(self.document["id"], {"version": management.detail(self.document["id"])["document"]["version"]})
        no_summary_evidence([primary, dependency["id"]], [old_summary, dependency["description"]])

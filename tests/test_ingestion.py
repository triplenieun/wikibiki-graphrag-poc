"""Document review trust boundaries and provider contracts without network."""
import copy
import json
from unittest.mock import patch

from django.core import signing
from django.test import SimpleTestCase, override_settings

from graphlab import ingestion, llm


DOCUMENT = {"id": "doc-unit", "title": "주문 처리", "body": "주문 서비스는 결제 서비스에 의존하며 커머스팀이 담당한다.", "source": "직접 입력"}
NODES = [
    {"id": "order-service", "kind": "Service", "name": "주문 서비스", "description": ""},
    {"id": "payment-service", "kind": "Service", "name": "결제 서비스", "description": ""},
    {"id": "commerce-team", "kind": "Team", "name": "커머스팀", "description": ""},
]
EDGES = [
    {"source_id": DOCUMENT["id"], "type": "DESCRIBES", "target_id": "order-service", "evidence": DOCUMENT["body"]},
    {"source_id": "order-service", "type": "DEPENDS_ON", "target_id": "payment-service", "evidence": DOCUMENT["body"]},
    {"source_id": "order-service", "type": "OWNED_BY", "target_id": "commerce-team", "evidence": DOCUMENT["body"]},
]


def payload():
    return {"review_token": signing.dumps(DOCUMENT, salt=ingestion.SALT, compress=True),
            "nodes": copy.deepcopy(NODES), "relations": copy.deepcopy(EDGES)}


class ReviewValidationTests(SimpleTestCase):
    def test_canonical_names_reuse_database_nodes_and_preserve_metadata(self):
        existing = [{**NODES[0], "id": "original-order", "description": "DB 설명", "labels": ["Lab", "Service"]}]
        nodes, edges, warnings = ingestion.normalize_review(DOCUMENT, NODES, EDGES, existing)
        node = next(n for n in nodes if n["kind"] == "Service" and n["name"] == "주문 서비스")
        self.assertEqual(node["id"], "original-order")
        self.assertEqual(node["description"], "DB 설명")
        self.assertTrue(node["existing"])
        self.assertTrue(warnings)
        self.assertEqual(next(e for e in edges if e["type"] == "DESCRIBES")["target_id"], "original-order")

    def test_rejects_missing_doc_link_hallucinated_evidence_and_wrong_direction(self):
        variations = [EDGES[1:], [{**EDGES[0], "evidence": "없는 근거"}],
                      [{**EDGES[0], "target_id": "commerce-team"}],
                      [{**EDGES[0], "type": "DELETE"}],
                      [{**EDGES[0], "source_id": "MATCH (n) DELETE n"}]]
        for edges in variations:
            with self.subTest(edges=edges), self.assertRaises(ingestion.ReviewError):
                ingestion.normalize_review(DOCUMENT, NODES, edges, [])

    def test_rejects_orphans_duplicate_ids_oversize_and_label_conflicts(self):
        orphan = {"id": "orphan", "kind": "Service", "name": "고립", "description": ""}
        for nodes in (NODES + [orphan], NODES + [NODES[0]], NODES * 11):
            with self.subTest(nodes=len(nodes)), self.assertRaises(ingestion.ReviewError):
                ingestion.normalize_review(DOCUMENT, nodes, EDGES, [])
        with self.assertRaises(ingestion.ReviewConflict):
            ingestion.normalize_review(DOCUMENT, NODES, EDGES, [{**NODES[0], "labels": ["Lab", "Service", "Document"]}])

    def test_evidence_keeps_original_substring_and_duplicate_edges_collapse(self):
        _, edges, _ = ingestion.normalize_review(DOCUMENT, NODES, EDGES + EDGES, [])
        self.assertEqual(len(edges), 3)
        self.assertTrue(all(edge["evidence"] in DOCUMENT["body"] for edge in edges))

    def test_one_service_cannot_have_two_owners(self):
        nodes = NODES + [{"id": "other-team", "kind": "Team", "name": "다른 팀", "description": ""}]
        with self.assertRaises(ingestion.ReviewConflict):
            ingestion.normalize_review(DOCUMENT, nodes, EDGES + [{**EDGES[-1], "target_id": "other-team"}], [])

    def test_forged_or_expired_token_cannot_open_a_transaction(self):
        with patch("graphlab.ingestion.graph_session") as connect:
            for token in (None, "forged", payload()["review_token"] + "changed"):
                with self.subTest(token=str(token)[:10]), self.assertRaises(ingestion.ReviewError):
                    ingestion.save({**payload(), "review_token": token})
            with patch("django.core.signing.time.time", return_value=1000):
                old_token = signing.dumps(DOCUMENT, salt=ingestion.SALT)
            with patch("django.core.signing.time.time", return_value=5000), self.assertRaisesRegex(ingestion.ReviewError, "1시간"):
                ingestion.save({**payload(), "review_token": old_token})
            connect.assert_not_called()

    def test_document_limits_fail_before_database_or_provider(self):
        with patch("graphlab.ingestion.graph_session") as connect, patch("graphlab.llm._request") as request:
            for data in ({"title": "", "body": "본문"}, {"title": "문서", "body": "가" * 12001}, {"title": "문서", "body": []}):
                with self.subTest(data=str(data)[:20]), self.assertRaises(ingestion.ReviewError):
                    ingestion.extract(data)
            connect.assert_not_called()
            request.assert_not_called()


class ExtractionProviderTests(SimpleTestCase):
    @override_settings(LLM_PROVIDER="litellm", LITELLM_MODEL="internal-model", LLM_EXTRACTION_MAX_TOKENS=3000)
    @patch("graphlab.ingestion.graph_session")
    @patch("graphlab.ingestion.read", return_value=[])
    @patch("graphlab.ingestion.document_input", return_value=DOCUMENT)
    @patch("graphlab.llm._request")
    def test_litellm_extracts_bounded_json_and_signs_original_document(self, request, doc, read, connect):
        request.return_value = {"choices": [{"message": {"content": json.dumps({"nodes": NODES, "relations": EDGES})}, "finish_reason": "stop"}]}
        result = ingestion.extract(DOCUMENT)
        self.assertEqual(result["provider"], "litellm")
        self.assertEqual(result["model"], "internal-model")
        self.assertEqual(ingestion._review_document(result["review_token"]), DOCUMENT)
        self.assertEqual(request.call_args.args[0], "/chat/completions")
        sent = request.call_args.args[1]
        self.assertEqual(sent["model"], "internal-model")
        self.assertEqual(sent["max_tokens"], 3000)
        self.assertNotIn("response_format", sent)
        self.assertIn(DOCUMENT["body"], sent["messages"][1]["content"])
        prompt_data = json.loads(sent["messages"][1]["content"])
        self.assertEqual(prompt_data["document"], {"id": DOCUMENT["id"], "body": DOCUMENT["body"]})
        self.assertNotIn("title", prompt_data["document"])
        self.assertNotIn("source", prompt_data["document"])
        # Metadata is still preserved in the returned/signed original document.
        self.assertEqual(result["document"]["title"], DOCUMENT["title"])
        self.assertEqual(result["document"]["source"], DOCUMENT["source"])

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_MODEL="qwen3.5:4b")
    @patch("graphlab.ingestion.graph_session")
    @patch("graphlab.ingestion.read", return_value=[])
    @patch("graphlab.ingestion.document_input", return_value=DOCUMENT)
    @patch("graphlab.llm._request")
    def test_ollama_uses_json_mode_and_invalid_output_never_becomes_a_fake_draft(self, request, doc, read, connect):
        for content in ('```json\n{}\n```', '{"nodes":[],"relations":[],"cypher":"DELETE"}',
                        json.dumps({"nodes": NODES, "relations": [{**EDGES[0], "type": "EXECUTE"}]})):
            request.return_value = {"message": {"content": content}}
            with self.subTest(content=content[:40]), self.assertRaises(llm.LLMError):
                ingestion.extract(DOCUMENT)
        self.assertEqual(request.call_args.args[0], "/api/chat")
        self.assertEqual(request.call_args.args[1]["format"], "json")
        self.assertFalse(request.call_args.args[1]["think"])

    @override_settings(LLM_PROVIDER="ollama")
    @patch("graphlab.ingestion.graph_session")
    @patch("graphlab.ingestion.read", return_value=[])
    @patch("graphlab.ingestion.document_input", return_value=DOCUMENT)
    @patch("graphlab.llm._request")
    def test_correctable_model_mistakes_remain_visible_but_cannot_be_saved(self, request, doc, read, connect):
        bad_edges = [EDGES[0], {**EDGES[1], "source_id": DOCUMENT["id"]},
                     {**EDGES[2], "evidence": "원문에 없는 근거 문장"}]
        request.return_value = {"message": {"content": json.dumps({"nodes": NODES, "relations": bad_edges})}}
        draft = ingestion.extract(DOCUMENT)
        self.assertTrue(any("시작·도착" in warning for warning in draft["warnings"]))
        self.assertTrue(any("근거 문장" in warning for warning in draft["warnings"]))
        wrong_edge = next(edge for edge in draft["relations"] if edge["type"] == "DEPENDS_ON")
        self.assertEqual(wrong_edge["source_id"], DOCUMENT["id"])
        self.assertTrue(any(edge["evidence"] == "원문에 없는 근거 문장" for edge in draft["relations"]))
        with patch("graphlab.ingestion.write") as write, self.assertRaises(ingestion.ReviewError):
            ingestion.save(draft)
        write.assert_not_called()
        # Human-corrected endpoints/evidence pass the same strict validation.
        _, corrected, _ = ingestion.normalize_review(DOCUMENT, draft["nodes"], EDGES, [])
        self.assertEqual(len(corrected), 3)

    @override_settings(LLM_PROVIDER="ollama")
    @patch("graphlab.ingestion.graph_session")
    @patch("graphlab.ingestion.read", return_value=[])
    @patch("graphlab.llm._request", return_value={"message": {"content": '{"nodes":[],"relations":[]}'}})
    def test_no_facts_is_editable_empty_preview_with_warning(self, request, read, connect):
        result = ingestion.extract(DOCUMENT)
        self.assertEqual(result["nodes"], [])
        self.assertTrue(result["warnings"])
        with self.assertRaisesRegex(ingestion.ReviewError, "DESCRIBES"):
            ingestion.save(result)


class SaveTransactionTests(SimpleTestCase):
    @patch("graphlab.ingestion.graph_session")
    @patch("graphlab.ingestion.write", side_effect=lambda session, callback: callback(object()))
    @patch("graphlab.ingestion.run")
    def test_changed_owner_aborts_before_document_or_graph_writes(self, run, write, connect):
        run.side_effect = [[], [], [], [], [{"id": "other-owner"}]]
        with self.assertRaisesRegex(ingestion.ReviewConflict, "기존 담당팀"):
            ingestion.save(payload())
        queries = [call.args[1] for call in run.call_args_list]
        self.assertFalse(any("CREATE (d:Lab:Document" in query for query in queries))
        self.assertFalse(any("ON CREATE SET n:Service" in query for query in queries))

    @patch("graphlab.ingestion.graph_session")
    @patch("graphlab.ingestion.write", side_effect=lambda session, callback: callback(object()))
    @patch("graphlab.ingestion.run")
    def test_same_draft_retry_is_idempotent_but_changed_approval_conflicts(self, run, write, connect):
        approved = payload()
        hashes = {"document": DOCUMENT, "nodes": sorted(approved["nodes"], key=lambda n: n["id"]),
                  "relations": sorted(approved["relations"], key=lambda e: (e["source_id"], e["type"], e["target_id"], e["evidence"]))}
        saved = {"labels": ["Lab", "Document"], "document_hash": ingestion._hash(DOCUMENT),
                 "review_hash": ingestion._hash(hashes), "service_ids": ["order-service"]}
        run.side_effect = [[], [saved]]
        result = ingestion.save(approved)
        self.assertFalse(result["created"])
        self.assertEqual(run.call_count, 2)
        run.reset_mock(side_effect=True)
        run.side_effect = [[], [saved]]
        approved["nodes"][0]["description"] = "다른 승인 내용"
        with self.assertRaises(ingestion.ReviewConflict):
            ingestion.save(approved)


class DocumentEndpointTests(SimpleTestCase):
    def test_csrf_is_required_for_extract_and_save(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        for path in ("extract", "save"):
            response = client.post(f"/api/documents/{path}/", data="{}", content_type="application/json")
            self.assertEqual(response.status_code, 403)

    @patch("graphlab.ingestion.extract")
    def test_api_validates_payload_and_sanitizes_provider_failures(self, extract):
        for body in ("[]", "invalid"):
            response = self.client.post("/api/documents/extract/", data=body, content_type="application/json")
            self.assertEqual(response.status_code, 400)
        extract.assert_not_called()
        extract.side_effect = llm.LLMError("모델 연결을 확인하세요.")
        response = self.client.post("/api/documents/extract/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "llm_unavailable")

    @patch("graphlab.ingestion.save", side_effect=ingestion.ReviewConflict("이미 저장됨"))
    def test_save_conflict_is_http409(self, save):
        response = self.client.post("/api/documents/save/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 409)

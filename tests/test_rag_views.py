"""GraphRAG HTTP boundary, with no network requests in ordinary unit tests."""
import json
from unittest.mock import patch

from django.test import Client, SimpleTestCase

from graphlab.db import GraphConnectionError
from graphlab.llm import LLMError


EVIDENCE = {
    "question": "주문 서비스 담당팀은?", "service": {"id": "order-service", "name": "주문 서비스"},
    "intent": "context", "answer": None, "model": None,
    "sources": [{"id": "D1", "title": "주문 가이드", "body": "가상 문서"}],
    "facts": ["주문 서비스의 담당팀은 커머스팀입니다."],
    "graph": {"nodes": [], "edges": []}, "trace": [], "scope": "context", "retrieval_ms": 1,
}


class GraphRagHttpTests(SimpleTestCase):
    def post(self, path="retrieve", payload=None, client=None):
        return (client or self.client).post(
            f"/api/graphrag/{path}/",
            data=json.dumps(payload if payload is not None else {"question": "주문 서비스 담당팀은?"}),
            content_type="application/json",
        )

    def test_page_loads_offline_without_database_or_llm(self):
        response = self.client.get("/graphrag/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GraphRAG")
        self.assertIn("csrftoken", response.cookies)

    def test_post_requires_csrf_cookie_and_token(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=client).status_code, 403)
        page = client.get("/graphrag/")
        token = page.cookies["csrftoken"].value
        with patch("graphlab.rag_views.graphrag.retrieve", return_value=EVIDENCE):
            response = client.post(
                "/api/graphrag/retrieve/", data=json.dumps({"question": "주문 담당팀"}),
                content_type="application/json", HTTP_X_CSRFTOKEN=token,
            )
        self.assertEqual(response.status_code, 200)

    def test_invalid_payload_does_not_query_database(self):
        with patch("graphlab.rag_views.graphrag.retrieve") as retrieve:
            for payload in ([], {"question": ""}, {"question": 1}, {"question": "x" * 2001},
                            {"question": "hello", "intent": "delete"},
                            {"question": "hello", "service_id": []}):
                with self.subTest(payload=str(payload)[:70]):
                    self.assertEqual(self.post(payload=payload).status_code, 400)
            retrieve.assert_not_called()
        response = self.client.post("/api/graphrag/retrieve/", "{", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @patch("graphlab.rag_views.llm.generate_answer")
    @patch("graphlab.rag_views.graphrag.retrieve", return_value=EVIDENCE)
    def test_retrieval_only_never_calls_llm(self, retrieve, generate):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["answer"])
        generate.assert_not_called()

    @patch("graphlab.rag_views.llm.generate_answer")
    @patch("graphlab.rag_views.graphrag.retrieve", return_value=EVIDENCE)
    def test_answer_uses_server_retrieval_not_browser_supplied_evidence(self, retrieve, generate):
        generate.return_value = {"answer": "커머스팀입니다. [G]", "model": "test-local-model"}
        response = self.post("ask", {
            "question": "주문 담당팀", "service_id": "order-service", "intent": "context",
            "sources": [{"body": "browser forged"}], "model": "do-not-use",
            "base_url": "https://do-not-call.example/",
        })
        self.assertEqual(response.status_code, 200)
        retrieve.assert_called_once_with("주문 담당팀", service_id="order-service", intent="context")
        generate.assert_called_once_with(EVIDENCE)
        self.assertEqual(response.json()["model"], "test-local-model")

    @patch("graphlab.rag_views.llm.generate_answer", side_effect=LLMError("모델 연결을 확인하세요."))
    @patch("graphlab.rag_views.graphrag.retrieve", return_value=EVIDENCE)
    def test_llm_failure_preserves_actual_evidence_without_fake_answer(self, retrieve, generate):
        response = self.post("ask")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["retrieval"], EVIDENCE)
        self.assertEqual(response.json()["code"], "llm_unavailable")

    @patch("graphlab.rag_views.graphrag.retrieve", side_effect=GraphConnectionError("DB 연결 실패"))
    def test_database_unavailable(self, retrieve):
        self.assertEqual(self.post().status_code, 503)

    def test_query_endpoints_reject_get(self):
        for path in ("ask", "retrieve"):
            self.assertEqual(self.client.get(f"/api/graphrag/{path}/").status_code, 405)

    @patch("graphlab.rag_views.llm.status", return_value={"ok": False, "provider": "litellm", "model": "internal-model"})
    @patch("graphlab.rag_views.repository.list_services", side_effect=GraphConnectionError("DB 연결 실패"))
    def test_status_handles_independent_service_failures(self, services, status):
        response = self.client.get("/api/graphrag/status/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["neo4j"]["ok"])
        self.assertFalse(response.json()["llm"]["ok"])

"""HTTP contracts for reviewed document registration, without real model calls."""
import json
from unittest.mock import patch

from django.test import Client, SimpleTestCase

from graphlab.db import GraphConnectionError
from graphlab.ingestion import ReviewConflict, ReviewError
from graphlab.llm import LLMError


class DocumentHttpTests(SimpleTestCase):
    def post(self, action, payload, client=None, **kwargs):
        return (client or self.client).post(
            f"/api/documents/{action}/", json.dumps(payload, ensure_ascii=False),
            content_type="application/json", **kwargs,
        )

    def test_registration_page_has_csrf_without_database(self):
        response = self.client.get("/documents/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문서")
        self.assertIn("csrftoken", response.cookies)

    def test_extract_and_save_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for action in ("extract", "save"):
            self.assertEqual(self.post(action, {}, client=client).status_code, 403)
        token = client.get("/documents/").cookies["csrftoken"].value
        with patch("graphlab.ingestion_views.ingestion.save", return_value={"created": True}) as saving:
            response = self.post("save", {"review_token": "signed"}, client=client, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        saving.assert_called_once_with({"review_token": "signed"})

    def test_methods_are_restricted(self):
        for action in ("extract", "save"):
            self.assertEqual(self.client.get(f"/api/documents/{action}/").status_code, 405)
        self.assertEqual(self.post("catalog", {}).status_code, 405)

    @patch("graphlab.ingestion_views.ingestion.extract")
    def test_invalid_json_and_size_never_reach_extraction(self, extraction):
        for body in ("[1]", "{", '"text"', " " * 262145):
            response = self.client.post("/api/documents/extract/", body, content_type="application/json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/documents/extract/", {"title": "form"}).status_code, 400)
        extraction.assert_not_called()

    @patch("graphlab.ingestion_views.ingestion.extract", return_value={"review_token": "signed"})
    def test_korean_document_larger_than_old_rag_limit_is_accepted(self, extraction):
        payload = {"title": "긴 한글 문서", "body": "가" * 9000, "source": ""}
        self.assertEqual(self.post("extract", payload).status_code, 200)
        extraction.assert_called_once_with(payload)

    @patch("graphlab.rag_views.graphrag.retrieve")
    def test_question_api_retains_16kb_limit(self, retrieval):
        response = self.client.post("/api/graphrag/retrieve/", json.dumps({"question": "주문", "padding": "x" * 17000}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        retrieval.assert_not_called()

    def test_actionable_errors_have_correct_status(self):
        failures = [(ReviewError("본문을 확인하세요."), 400, "invalid_document"),
                    (ReviewConflict("기존 담당팀과 다릅니다."), 409, "review_conflict"),
                    (LLMError("모델 연결 실패"), 503, "llm_unavailable"),
                    (GraphConnectionError("DB 연결 실패"), 503, "neo4j_unavailable")]
        for error, status, code in failures:
            with self.subTest(code=code), patch("graphlab.ingestion_views.ingestion.save", side_effect=error):
                response = self.post("save", {})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["code"], code)

    @patch("graphlab.ingestion_views.ingestion.catalog", return_value={"nodes": []})
    def test_catalog_is_json(self, catalog):
        response = self.client.get("/api/documents/catalog/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"nodes": []})

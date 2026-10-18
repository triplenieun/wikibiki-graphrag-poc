"""HTTP contracts without a running Neo4j server."""
from unittest.mock import patch

from django.test import SimpleTestCase

from graphlab.db import GraphConnectionError


class GraphApiTests(SimpleTestCase):
    def test_index_is_available_without_database(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/services/order-service/context/", response.json()["routes"])

    @patch("graphlab.views.repository.list_services")
    def test_services_returns_unicode_json(self, query):
        query.return_value = [{"id": "order-service", "name": "주문 서비스"}]
        response = self.client.get("/api/services/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"services": query.return_value})
        self.assertIn("주문 서비스", response.content.decode("utf-8"))
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_read_endpoints_reject_post_without_querying_database(self):
        for path, operation in (
            ("/", "list_services"),
            ("/api/services/", "list_services"),
            ("/api/services/order-service/context/", "service_context"),
            ("/api/services/auth-service/impact/", "service_impact"),
        ):
            with self.subTest(path=path), patch(f"graphlab.views.repository.{operation}") as query:
                response = self.client.post(path)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "GET")
                query.assert_not_called()

    def test_missing_service_is_404_for_context_and_impact(self):
        for suffix, operation in (("context", "service_context"), ("impact", "service_impact")):
            with self.subTest(suffix=suffix), patch(
                f"graphlab.views.repository.{operation}", return_value=None
            ) as query:
                response = self.client.get(f"/api/services/missing-service/{suffix}/")
                self.assertEqual(response.status_code, 404)
                self.assertIn("error", response.json())
                query.assert_called_once_with("missing-service")

    @patch("graphlab.views.repository.service_context")
    def test_context_preserves_retrieved_sources(self, query):
        query.return_value = {
            "service": {"id": "order-service"},
            "documents": [{"source": "docs/samples/order-guide.md", "body": "가상 문서"}],
        }
        response = self.client.get("/api/services/order-service/context/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), query.return_value)

    def test_database_failure_is_json_503(self):
        for path, operation in (
            ("/api/services/", "list_services"),
            ("/api/services/order-service/context/", "service_context"),
            ("/api/services/auth-service/impact/", "service_impact"),
        ):
            with self.subTest(path=path), patch(
                f"graphlab.views.repository.{operation}",
                side_effect=GraphConnectionError("Neo4j 연결을 확인하세요."),
            ):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"error": "Neo4j 연결을 확인하세요."})

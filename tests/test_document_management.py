"""HTTP and signed review boundaries without a running graph or model."""
from unittest.mock import patch

from django.core import signing
from django.test import Client, SimpleTestCase

from graphlab import document_management as management, ingestion
from tests.test_ingestion import DOCUMENT, EDGES, NODES, payload


class ManagementBoundaryTests(SimpleTestCase):
    def test_update_tokens_cannot_create_and_create_tokens_cannot_update(self):
        signed = {**DOCUMENT, "_operation": "update", "_base_version": "a" * 64}
        update_payload = {"review_token": signing.dumps(signed, salt=ingestion.SALT), "nodes": NODES, "relations": EDGES}
        with patch("graphlab.ingestion.graph_session") as create_db, patch("graphlab.document_management.graph_session") as update_db:
            with self.assertRaises(ingestion.ReviewError):
                ingestion.save(update_payload)
            with self.assertRaises(ingestion.ReviewError):
                management.update(DOCUMENT["id"], payload())
            with self.assertRaises(ingestion.ReviewError):
                management.update("different-document", update_payload)
            create_db.assert_not_called()
            update_db.assert_not_called()

    def test_invalid_versions_and_pagination_fail_before_database(self):
        with patch("graphlab.document_management.graph_session") as connect:
            for value in (None, 1, "a", "z" * 64):
                with self.subTest(value=value), self.assertRaises(ingestion.ReviewError):
                    management.delete("doc-unit", {"version": value})
            for offset, limit in (("-1", "50"), ("0", "101"), ("x", "50"), ("0", "0")):
                with self.subTest(offset=offset, limit=limit), self.assertRaises(ingestion.ReviewError):
                    management.listing("", offset, limit)
            connect.assert_not_called()

    @patch("graphlab.document_management.detail", return_value={"document": {"can_manage": True, "version": "a" * 64}, "warnings": []})
    @patch("graphlab.ingestion.extract")
    def test_stale_extract_is_rejected_without_model_call(self, extract, detail):
        with self.assertRaises(ingestion.ReviewConflict):
            management.extract_update("doc-unit", {**DOCUMENT, "version": "b" * 64})
        extract.assert_not_called()

    @patch("graphlab.document_management.detail", return_value={"document": {"can_manage": True, "version": "a" * 64}, "warnings": ["preserved"]})
    @patch("graphlab.ingestion.extract", return_value={"warnings": []})
    def test_update_extract_uses_existing_id_and_version(self, extract, detail):
        submitted = {**DOCUMENT, "version": "a" * 64}
        result = management.extract_update("doc-unit", submitted)
        extract.assert_called_once_with(submitted, document_id="doc-unit", base_version="a" * 64)
        self.assertEqual(result["warnings"], ["preserved"])


class ManagementHttpTests(SimpleTestCase):
    def test_management_get_and_post_methods_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for action in ("extract", "update", "delete"):
            path = f"/api/documents/doc-unit/{action}/"
            self.assertEqual(client.get(path).status_code, 405)
            self.assertEqual(client.post(path, "{}", content_type="application/json").status_code, 403)
        for path in ("/api/documents/", "/api/documents/doc-unit/"):
            self.assertEqual(self.client.post(path, "{}", content_type="application/json").status_code, 405)

    @patch("graphlab.document_management.listing", return_value={"documents": [], "total": 0, "has_more": False})
    def test_list_passes_query_and_pagination(self, listing):
        response = self.client.get("/api/documents/?q=hello&offset=2&limit=10")
        self.assertEqual(response.status_code, 200)
        listing.assert_called_once_with("hello", "2", "10")

    @patch("graphlab.document_management.detail", side_effect=management.DocumentNotFound("문서가 없습니다."))
    def test_missing_document_is_404(self, detail):
        response = self.client.get("/api/documents/missing/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "document_not_found")

    @patch("graphlab.document_management.delete", side_effect=ingestion.ReviewConflict("문서가 변경되었습니다."))
    def test_delete_conflict_is_409(self, delete):
        response = self.client.post("/api/documents/doc-unit/delete/", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 409)
        delete.assert_called_once_with("doc-unit", {})

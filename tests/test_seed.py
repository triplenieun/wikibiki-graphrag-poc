"""Validate references and document boundaries before any database write."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from graphlab.seed import load_sample, seed_graph


class FixtureValidationTests(SimpleTestCase):
    def setUp(self):
        # Keep temporary files in the checkout for restricted/offline workspaces.
        tests_directory = Path(__file__).resolve().parent
        directory = TemporaryDirectory(prefix=".fixture-", dir=tests_directory)
        self.root = Path(directory.name).resolve()
        if not self.root.is_relative_to(tests_directory):
            raise RuntimeError("Temporary fixture must remain inside tests/.")
        self.addCleanup(directory.cleanup)
        (self.root / "data").mkdir()
        (self.root / "docs/samples").mkdir(parents=True)
        (self.root / "docs/samples/example.md").write_text("# 가상 운영 문서\n", encoding="utf-8")
        self.fixture = {
            "teams": [{"id": "test-team", "name": "테스트팀"}],
            "services": [
                {"id": "service-a", "name": "A", "description": "가상", "owner_id": "test-team"},
                {"id": "service-b", "name": "B", "description": "가상", "owner_id": "test-team"},
            ],
            "documents": [{"id": "test-doc", "title": "예제", "source": "docs/samples/example.md", "service_id": "service-a"}],
            "dependencies": [{"source_id": "service-a", "target_id": "service-b"}],
        }
        settings_context = override_settings(BASE_DIR=self.root)
        settings_context.enable()
        self.addCleanup(settings_context.disable)

    def write_fixture(self):
        (self.root / "data/sample_graph.json").write_text(json.dumps(self.fixture), encoding="utf-8")

    def test_valid_fixture_includes_original_document_body(self):
        self.write_fixture()
        loaded = load_sample()
        self.assertEqual(loaded["documents"][0]["body"], "# 가상 운영 문서\n")

    def test_duplicate_id_across_node_types_is_rejected(self):
        self.fixture["documents"][0]["id"] = "test-team"
        self.write_fixture()
        with self.assertRaisesMessage(ValueError, "고유"):
            load_sample()

    def test_unknown_team_is_rejected_before_database_access(self):
        self.fixture["services"][0]["owner_id"] = "missing-team"
        self.write_fixture()
        with patch("graphlab.seed.graph_session") as session:
            with self.assertRaisesMessage(ValueError, "owner_id"):
                seed_graph()
            session.assert_not_called()

    def test_missing_dependency_endpoints_are_rejected(self):
        for endpoint in ("source_id", "target_id"):
            with self.subTest(endpoint=endpoint):
                original = self.fixture["dependencies"][0][endpoint]
                self.fixture["dependencies"][0][endpoint] = "missing-service"
                self.write_fixture()
                with self.assertRaisesMessage(ValueError, "의존 관계"):
                    load_sample()
                self.fixture["dependencies"][0][endpoint] = original

    def test_document_must_describe_an_existing_service(self):
        self.fixture["documents"][0]["service_id"] = "missing-service"
        self.write_fixture()
        with self.assertRaisesMessage(ValueError, "service_id"):
            load_sample()

    def test_document_path_cannot_escape_sample_directory(self):
        for source in ("README.md", "docs/samples/../../../outside.md"):
            with self.subTest(source=source):
                self.fixture["documents"][0]["source"] = source
                self.write_fixture()
                with self.assertRaisesMessage(ValueError, "docs/samples"):
                    load_sample()

"""Command-line validation and readable failures need no database."""
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from graphlab.db import GraphConnectionError


class CommandTests(SimpleTestCase):
    def test_context_and_impact_require_service_id(self):
        for query in ("context", "impact"):
            with self.subTest(query=query), patch("graphlab.management.commands.graph_query.repository") as repository:
                with self.assertRaisesMessage(CommandError, "--service-id"):
                    call_command("graph_query", query, stdout=StringIO())
                repository.service_context.assert_not_called()
                repository.service_impact.assert_not_called()

    @patch("graphlab.management.commands.graph_query.repository.list_services")
    def test_services_prints_valid_json(self, query):
        query.return_value = [{"id": "order-service", "name": "주문 서비스"}]
        output = StringIO()
        call_command("graph_query", "services", stdout=output)
        self.assertEqual(json.loads(output.getvalue()), {"services": query.return_value})
        self.assertIn("주문 서비스", output.getvalue())

    @patch("graphlab.management.commands.graph_query.repository.service_context", return_value=None)
    def test_unknown_service_is_a_command_error(self, query):
        with self.assertRaisesMessage(CommandError, "missing-service"):
            call_command("graph_query", "context", service_id="missing-service", stdout=StringIO())

    def test_connection_failures_become_command_errors(self):
        for command, target, args in (
            ("check_neo4j", "graphlab.management.commands.check_neo4j.check_connection", ()),
            ("seed_graph", "graphlab.management.commands.seed_graph.seed_graph", ()),
            ("graph_query", "graphlab.management.commands.graph_query.repository.list_services", ("services",)),
        ):
            with self.subTest(command=command), patch(target, side_effect=GraphConnectionError("연결 설정 확인")):
                with self.assertRaisesMessage(CommandError, "연결 설정 확인"):
                    call_command(command, *args, stdout=StringIO())

    @patch("graphlab.management.commands.seed_graph.seed_graph", side_effect=ValueError("잘못된 owner_id"))
    def test_invalid_fixture_is_a_readable_command_error(self, seed):
        with self.assertRaisesMessage(CommandError, "잘못된 owner_id"):
            call_command("seed_graph", stdout=StringIO())

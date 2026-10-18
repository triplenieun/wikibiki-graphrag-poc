"""Connection failures must be actionable without exposing secrets."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from neo4j.exceptions import ServiceUnavailable

from graphlab.db import GraphConnectionError, check_connection


class ConnectionTests(SimpleTestCase):
    @override_settings(NEO4J_PASSWORD="")
    @patch("graphlab.db.GraphDatabase.driver")
    def test_missing_password_fails_before_opening_connection(self, driver):
        with self.assertRaisesMessage(GraphConnectionError, "NEO4J_PASSWORD"):
            check_connection()
        driver.assert_not_called()

    @override_settings(NEO4J_PASSWORD="private-test-password")
    @patch("graphlab.db.GraphDatabase.driver")
    def test_driver_exception_message_does_not_leak_credentials(self, driver):
        for failure in (
            ServiceUnavailable("bolt://neo4j:private-test-password@localhost:7687"),
            ValueError("invalid private-test-password URI"),
            OSError("connection failed: private-test-password"),
        ):
            with self.subTest(error=type(failure).__name__):
                driver.side_effect = failure
                with self.assertRaises(GraphConnectionError) as raised:
                    check_connection()
                self.assertNotIn("private-test-password", str(raised.exception))
                self.assertIn("docker compose ps", str(raised.exception))

    @override_settings(NEO4J_PASSWORD="private-test-password")
    @patch("graphlab.db.GraphDatabase.driver")
    def test_query_time_failure_has_same_safe_message(self, driver):
        session = driver.return_value.__enter__.return_value.session.return_value.__enter__.return_value
        session.execute_read.side_effect = ServiceUnavailable("private-test-password")
        with self.assertRaises(GraphConnectionError) as raised:
            check_connection()
        self.assertNotIn("private-test-password", str(raised.exception))
        driver.return_value.__exit__.assert_called_once()

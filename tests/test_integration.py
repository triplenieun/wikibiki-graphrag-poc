"""Opt-in tests: write fictional fixtures to a dedicated Neo4j lab database.

Set NEO4J_INTEGRATION=1 only with a disposable, isolated lab database. These
tests seed the documented Lab IDs twice and update their fictional properties.
They do not delete nodes, relationships, or the database. Django's test database
machinery does not isolate Neo4j; the configured NEO4J_DATABASE is used directly.
"""
import os
from unittest import skipUnless

from django.test import SimpleTestCase

from graphlab.db import graph_session, run
from graphlab.repository import list_services, service_context, service_impact
from graphlab.seed import load_sample, seed_graph


@skipUnless(os.getenv("NEO4J_INTEGRATION") == "1", "Set NEO4J_INTEGRATION=1 for a dedicated Neo4j lab database.")
class Neo4jIntegrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first_seed = seed_graph()
        cls.second_seed = seed_graph()
        fixture = load_sample()
        cls.fixture_ids = [row["id"] for key in ("teams", "services", "documents") for row in fixture[key]]

    def test_seeding_twice_keeps_eleven_nodes_and_twelve_relationships(self):
        expected = {"teams": 3, "services": 4, "documents": 4, "dependencies": 4}
        self.assertEqual(self.first_seed, expected)
        self.assertEqual(self.second_seed, expected)
        with graph_session() as session:
            counts = session.execute_read(lambda tx: run(tx, """
                MATCH (n:Lab) WHERE n.id IN $ids
                WITH count(n) AS nodes
                MATCH (a:Lab)-[r]->(b:Lab)
                WHERE a.id IN $ids AND b.id IN $ids
                RETURN nodes, count(r) AS relationships
            """, ids=self.fixture_ids))
        self.assertEqual(counts, [{"nodes": 11, "relationships": 12}])

    def test_services_have_four_unique_ids_and_owners(self):
        services = [row for row in list_services() if row["id"] in self.fixture_ids]
        self.assertEqual(
            [row["id"] for row in services],
            ["auth-service", "notification-service", "order-service", "payment-service"],
        )
        self.assertTrue(all(service["owner"]["id"] for service in services))

    def test_order_context_follows_dependencies_and_collects_three_sources(self):
        context = service_context("order-service")
        self.assertEqual(context["service"]["id"], "order-service")
        self.assertEqual(context["owner"]["id"], "commerce-team")
        self.assertEqual([row["id"] for row in context["dependencies"] if row["id"] in self.fixture_ids], ["auth-service", "payment-service"])
        fixture_docs = [row for row in context["documents"] if row["id"] in self.fixture_ids]
        self.assertEqual([row["id"] for row in fixture_docs], ["auth-guide", "order-guide", "payment-guide"])
        self.assertTrue(all(doc["body"] and doc["source"].startswith("docs/samples/") for doc in fixture_docs))

    def test_auth_impact_returns_dependents_once_at_shortest_distance(self):
        impact = service_impact("auth-service")
        self.assertEqual(
            [(service["id"], service["hops"]) for service in impact["affected_services"] if service["id"] in self.fixture_ids],
            [("notification-service", 1), ("order-service", 1), ("payment-service", 1)],
        )
        self.assertEqual(impact["max_hops"], 5)

    def test_unknown_service_returns_none_and_http_404(self):
        self.assertIsNone(service_context("missing-lab-service"))
        self.assertIsNone(service_impact("missing-lab-service"))
        for suffix in ("context", "impact"):
            with self.subTest(suffix=suffix):
                response = self.client.get(f"/api/services/missing-lab-service/{suffix}/")
                self.assertEqual(response.status_code, 404)

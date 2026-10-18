"""검색 대상의 모호성, 실제 Cypher 추적, 그래프의 출처를 검증한다."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from graphlab import graphrag


SERVICES = [
    {"id": "order-service", "name": "주문 서비스", "description": "주문 접수"},
    {"id": "auth-service", "name": "인증 서비스", "description": "인증 확인"},
]


class GraphRagTests(SimpleTestCase):
    def test_service_aliases_and_explicit_selection(self):
        for question in ("주문 담당팀?", "order-service 담당팀?", "order 담당팀?", "주문 서비스 설명"):
            with self.subTest(question=question):
                self.assertEqual(graphrag.resolve_service(question, "", SERVICES)["id"], "order-service")
        self.assertEqual(graphrag.resolve_service("주문에서 인증 문제", "auth-service", SERVICES)["id"], "auth-service")

    def test_ambiguous_unknown_and_substring_services_rejected(self):
        for question, selected in (("주문에서 인증 문제", ""), ("담당팀?", ""), ("authorization?", ""), ("주문?", "missing")):
            with self.subTest(question=question), self.assertRaises(graphrag.RetrievalError):
                graphrag.resolve_service(question, selected, SERVICES)

    def test_validation_happens_before_database_call(self):
        with patch("graphlab.graphrag.graph_session") as connect:
            for question, selected, intent in (("", "", "auto"), ("a" * 2001, "", "auto"), (None, "", "auto"), ("주문?", [], "auto"), ("주문?", "", "write")):
                with self.subTest(question=str(question)[:20]), self.assertRaises(graphrag.RetrievalError):
                    graphrag.retrieve(question, selected, intent)
            connect.assert_not_called()

    def test_auto_intent_preserves_explicit_choice(self):
        self.assertEqual(graphrag.resolve_intent("인증 장애 영향 범위?", "auto"), "impact")
        self.assertEqual(graphrag.resolve_intent("인증 담당팀?", "auto"), "context")
        self.assertEqual(graphrag.resolve_intent("장애 영향?", "context"), "context")

    @override_settings(NEO4J_PASSWORD="test-only")
    @patch("graphlab.db.GraphDatabase.driver")
    @patch("graphlab.graphrag.read", side_effect=lambda session, callback: callback(object()))
    @patch("graphlab.graphrag.run", return_value=[{"service": service} for service in SERVICES])
    def test_ambiguous_question_is_not_rewrapped_as_database_failure(self, run, read, driver):
        # Use the real graph_session context manager: it catches ValueError for
        # connection configuration, so user validation must use its own type.
        with self.assertRaisesRegex(graphrag.RetrievalError, "여러 서비스"):
            graphrag.retrieve("주문과 인증 담당팀?")

    @patch("graphlab.graphrag.graph_session")
    @patch("graphlab.graphrag.read", side_effect=lambda session, callback: callback(object()))
    @patch("graphlab.graphrag.run")
    def test_context_uses_db_rows_and_exact_executed_queries(self, run, read, connect):
        run.side_effect = [
            [{"service": service} for service in SERVICES],
            [{"service": SERVICES[0], "hops": 0, "dependencies": []},
             {"service": SERVICES[1], "hops": 1, "dependencies": [{"source": "order-service", "target": "auth-service", "type": "DEPENDS_ON"}]}],
            [{"service_id": "auth-service", "team": {"id": "live-team", "name": "실제 DB 팀"}}],
            [{"document_id": "live-doc", "title": "DB 문서", "source": "docs/live.md", "body": "실시간 문서 본문", "service_id": "auth-service", "truncated": False}],
        ]
        result = graphrag.retrieve("주문 서비스 담당팀?", intent="context")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["sources"][0]["id"], "D1")
        self.assertEqual(result["sources"][0]["body"], "실시간 문서 본문")
        self.assertIn({"id": "live-team", "label": "실제 DB 팀", "kind": "Team"}, result["graph"]["nodes"])
        self.assertIn({"source": "live-doc", "target": "auth-service", "type": "DESCRIBES"}, result["graph"]["edges"])
        self.assertEqual(len(result["trace"]), 4)
        for call, trace in zip(run.call_args_list, result["trace"]):
            self.assertEqual(trace["cypher"], call.args[1])
            self.assertEqual(trace["parameters"], call.kwargs)
        self.assertEqual(run.call_args_list[1].kwargs, {"service_id": "order-service"})
        self.assertNotIn("주문 서비스 담당팀?", run.call_args_list[1].args[1])

    @patch("graphlab.graphrag.graph_session")
    @patch("graphlab.graphrag.read", side_effect=lambda session, callback: callback(object()))
    @patch("graphlab.graphrag.run")
    def test_impact_preserves_dependency_direction_and_distinguishes_potential(self, run, read, connect):
        run.side_effect = [
            [{"service": service} for service in SERVICES],
            [{"service": SERVICES[1], "hops": 0, "dependencies": []},
             {"service": SERVICES[0], "hops": 1, "dependencies": [{"source": "order-service", "target": "auth-service", "type": "DEPENDS_ON"}]}],
            [], [],
        ]
        result = graphrag.retrieve("인증 장애 영향?", "auth-service")
        self.assertEqual(result["intent"], "impact")
        self.assertEqual(run.call_args_list[1].args[1], graphrag.IMPACT)
        self.assertIn("실제 장애 발생 여부는 확인되지 않았습니다", " ".join(result["facts"]))
        self.assertEqual(result["graph"]["edges"], [{"source": "order-service", "target": "auth-service", "type": "DEPENDS_ON"}])

    @patch("graphlab.graphrag.graph_session")
    @patch("graphlab.graphrag.read", side_effect=lambda session, callback: callback(object()))
    @patch("graphlab.graphrag.run")
    def test_snapshot_is_live_and_bounded(self, run, read, connect):
        run.side_effect = [[{"id": f"service-{i}", "label": f"현재 서비스 {i}", "kind": "Service"} for i in range(201)], []]
        result = graphrag.graph_snapshot()
        self.assertEqual(len(result["nodes"]), 200)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(run.call_args_list[1].kwargs["node_ids"]), 200)

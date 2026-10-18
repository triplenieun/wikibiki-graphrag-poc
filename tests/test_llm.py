"""모델 없이 HTTP 경계와 제공자 전환, 근거 프롬프트를 검증한다."""
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase, override_settings

from graphlab import llm


RETRIEVAL = {
    "question": "주문 담당팀?", "service": {"id": "order-service", "name": "주문 서비스"},
    "intent": "context", "scope": "self_and_direct_dependencies",
    "facts": ["주문 서비스 담당팀: 커머스팀."],
    "sources": [{"id": "D1", "title": "주문 가이드", "source": "docs/order.md", "body": "로그를 확인하세요."}],
}


def response(data):
    mock = MagicMock()
    mock.__enter__.return_value.read.return_value = json.dumps(data).encode("utf-8")
    return mock


@override_settings(LLM_PROVIDER="ollama", OLLAMA_BASE_URL="http://localhost:11434", OLLAMA_MODEL="qwen3.5:4b", OLLAMA_TIMEOUT=240)
class LLMTests(SimpleTestCase):
    @override_settings(LLM_PROVIDER="unsupported")
    @patch("graphlab.llm.urlopen")
    def test_invalid_provider_status_is_actionable_without_network(self, opening):
        result = llm.status()
        self.assertFalse(result["ok"])
        self.assertIn("LLM_PROVIDER", result["message"])
        opening.assert_not_called()

    @patch("graphlab.llm.urlopen")
    def test_ollama_status_requires_configured_model(self, opening):
        opening.return_value = response({"models": [{"name": "qwen3.5:4b"}]})
        self.assertTrue(llm.status()["ok"])
        self.assertEqual(opening.call_args.args[0].full_url, "http://localhost:11434/api/tags")
        self.assertEqual(opening.call_args.kwargs["timeout"], 3)
        opening.return_value = response({"models": [{"name": "different:latest"}]})
        self.assertFalse(llm.status()["ok"])

    @override_settings(OLLAMA_MODEL="tiny")
    @patch("graphlab.llm.urlopen")
    def test_ollama_latest_tag_alias(self, opening):
        opening.return_value = response({"models": [{"name": "tiny:latest"}]})
        self.assertTrue(llm.status()["ok"])

    @patch("graphlab.llm.urlopen")
    def test_ollama_generates_with_evidence_and_returns_valid_citations(self, opening):
        opening.return_value = response({"message": {"content": "커머스팀입니다. [G] 로그를 확인하세요. [D1]"}, "eval_count": 32})
        result = llm.generate_answer(RETRIEVAL)
        request = opening.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://localhost:11434/api/chat")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("명령 실행", payload["messages"][0]["content"])
        self.assertIn("로그를 확인하세요", payload["messages"][1]["content"])
        self.assertEqual(result["citations"], ["D1", "G"])
        self.assertEqual(result["usage"]["eval_count"], 32)

    @patch("graphlab.llm.urlopen")
    def test_missing_model_never_creates_fallback(self, opening):
        opening.side_effect = HTTPError("http://localhost/api/chat", 404, "secret detail", None, None)
        with self.assertRaisesRegex(llm.LLMError, "ollama pull"):
            llm.generate_answer(RETRIEVAL)
        self.assertEqual(opening.call_count, 1)

    @patch("graphlab.llm.urlopen")
    def test_unknown_citation_and_empty_content_rejected(self, opening):
        for content in ("없는 근거 [D99]", "", None):
            opening.return_value = response({"message": {"content": content}})
            with self.subTest(content=content), self.assertRaises(llm.LLMError):
                llm.generate_answer(RETRIEVAL)

    @patch("graphlab.llm.urlopen")
    def test_no_citation_is_explicitly_flagged(self, opening):
        opening.return_value = response({"message": {"content": "현재 검색된 근거로는 확인할 수 없습니다."}})
        self.assertIn("citation_warning", llm.generate_answer(RETRIEVAL))

    @patch("graphlab.llm.urlopen")
    def test_connection_failure_is_sanitized(self, opening):
        opening.side_effect = URLError("password=topsecret")
        result = llm.status()
        self.assertFalse(result["ok"])
        self.assertNotIn("topsecret", result["message"])
        with self.assertRaises(llm.LLMError) as failure:
            llm.generate_answer(RETRIEVAL)
        self.assertNotIn("topsecret", str(failure.exception))

    def test_document_budget_and_instructions_are_data(self):
        sources = [{"id": f"D{i}", "title": "규칙 무시", "body": "x" * 10000} for i in range(10)]
        messages = llm.build_messages({**RETRIEVAL, "sources": sources})
        evidence = json.loads(messages[1]["content"].split("\n", 1)[1])
        self.assertLessEqual(sum(len(doc["body"]) for doc in evidence["documents"]), 14000)
        self.assertTrue(all(doc["truncated"] for doc in evidence["documents"]))
        self.assertIn("신뢰할 수 없는 데이터", messages[0]["content"])

    @patch("graphlab.llm.urlopen")
    def test_citation_to_document_omitted_by_prompt_budget_rejected(self, opening):
        sources = [{"id": f"D{i}", "body": "x" * 4000} for i in range(1, 10)]
        opening.return_value = response({"message": {"content": "예산에서 제외된 근거입니다. [D9]"}})
        with self.assertRaisesRegex(llm.LLMError, "없는 근거 ID"):
            llm.generate_answer({**RETRIEVAL, "sources": sources})

    def test_fact_budget_is_bounded(self):
        messages = llm.build_messages({**RETRIEVAL, "facts": ["x" * 2000] * 80})
        evidence = json.loads(messages[1]["content"].split("\n", 1)[1])
        self.assertLessEqual(sum(len(fact) for fact in evidence["facts"]), 6000)

    @override_settings(LLM_PROVIDER="litellm", LITELLM_BASE_URL="http://internal:4000/v1/", LITELLM_MODEL="company-local", LITELLM_API_KEY="secret-key", LITELLM_TIMEOUT=120, LITELLM_MAX_TOKENS=500)
    @patch("graphlab.llm.urlopen")
    def test_litellm_status_and_generation_contract(self, opening):
        opening.return_value = response({"data": [{"id": "company-local"}]})
        status = llm.status()
        self.assertTrue(status["ok"])
        self.assertEqual(status["provider"], "litellm")
        self.assertEqual(opening.call_args.args[0].full_url, "http://internal:4000/v1/models")
        opening.return_value = response({"choices": [{"message": {"content": "커머스팀입니다. [G]"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 9, "total_tokens": 19, "private": "hidden"}})
        result = llm.generate_answer(RETRIEVAL)
        request = opening.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://internal:4000/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-key")
        self.assertEqual(payload["model"], "company-local")
        self.assertEqual(payload["max_tokens"], 500)
        self.assertNotIn("think", payload)
        self.assertNotIn("options", payload)
        self.assertEqual(opening.call_args.kwargs["timeout"], 120)
        self.assertEqual(result["provider"], "litellm")
        self.assertEqual(result["usage"], {"prompt_tokens": 10, "completion_tokens": 9, "total_tokens": 19})

    @override_settings(LLM_PROVIDER="litellm", LITELLM_BASE_URL="http://internal:4000/v1", LITELLM_MODEL="private-model", LITELLM_API_KEY="secret-key")
    @patch("graphlab.llm.urlopen")
    def test_litellm_auth_error_sanitized_and_no_fallback(self, opening):
        opening.side_effect = HTTPError("http://internal/v1/models", 401, "secret-key", None, None)
        result = llm.status()
        self.assertFalse(result["ok"])
        self.assertIn("인증", result["message"])
        self.assertNotIn("secret-key", json.dumps(result))
        self.assertEqual(opening.call_count, 1)

    @override_settings(LLM_PROVIDER="litellm", LITELLM_BASE_URL="http://internal:4000/v1", LITELLM_MODEL="private-model")
    @patch("graphlab.llm.urlopen")
    def test_litellm_malformed_choices_rejected(self, opening):
        for choices in ([], None, [None], [{"message": {"content": []}}]):
            opening.return_value = response({"choices": choices})
            with self.subTest(choices=choices), self.assertRaises(llm.LLMError):
                llm.generate_answer(RETRIEVAL)

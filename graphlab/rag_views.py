"""GraphRAG HTML and JSON endpoints. Provider secrets remain on the server."""
import json

from django.core.exceptions import RequestDataTooBig
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from graphlab import graphrag, llm, repository
from graphlab.db import GraphConnectionError
from graphlab.views import json_response


@require_GET
@ensure_csrf_cookie
def page(request):
    return render(request, "graphlab/graphrag.html")


@require_GET
def status(request):
    try:
        services = repository.list_services()
        neo4j = {"ok": True, "message": f"서비스 {len(services)}개 연결됨"}
    except GraphConnectionError as exc:
        services = []
        neo4j = {"ok": False, "message": str(exc)}
    return json_response({"neo4j": neo4j, "llm": llm.status(), "services": services})


@require_GET
def graph(request):
    try:
        return json_response(graphrag.graph_snapshot())
    except GraphConnectionError as exc:
        return json_response({"error": str(exc), "code": "neo4j_unavailable"}, status=503)


def parse_question(request):
    if request.content_type != "application/json":
        raise ValueError("Content-Type: application/json 형식으로 질문을 보내세요.")
    try:
        if len(request.body) > 16384:
            raise RequestDataTooBig()
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError, RequestDataTooBig) as exc:
        raise ValueError("올바른 JSON 질문을 보내세요. 요청은 16KB 이하로 제한됩니다.") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON 객체 형식으로 질문을 보내세요.")
    question = payload.get("question", "")
    service_id = payload.get("service_id", "")
    intent = payload.get("intent", "auto")
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        raise ValueError("질문은 1~2,000자의 문자열로 입력하세요.")
    if not isinstance(service_id, str) or len(service_id) > 100:
        raise ValueError("서비스 ID를 확인하세요.")
    if intent not in ("auto", "context", "impact"):
        raise ValueError("조회 방식은 auto, context, impact 중 하나입니다.")
    return question.strip(), service_id.strip(), intent


def answer_response(request, generate):
    try:
        question, service_id, intent = parse_question(request)
        evidence = graphrag.retrieve(question, service_id=service_id, intent=intent)
    except (ValueError, graphrag.RetrievalError) as exc:
        return json_response({"error": str(exc), "code": "invalid_question"}, status=400)
    except GraphConnectionError as exc:
        return json_response({"error": str(exc), "code": "neo4j_unavailable"}, status=503)
    if not generate:
        return json_response(evidence)
    try:
        generation = llm.generate_answer(evidence)
    except llm.LLMError as exc:
        return json_response({
            "error": str(exc), "code": "llm_unavailable", "retrieval": evidence,
        }, status=503)
    return json_response({**evidence, **generation})


@require_POST
def retrieve(request):
    return answer_response(request, generate=False)


@require_POST
def ask(request):
    return answer_response(request, generate=True)


def csrf_failure(request, reason=""):
    return json_response({
        "error": "페이지를 새로고침한 뒤 다시 시도하세요. 요청 확인 토큰이 일치하지 않습니다.",
        "code": "csrf_failed",
    }, status=403)

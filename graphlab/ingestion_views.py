"""JSON boundaries for document extraction and explicitly reviewed writes."""
import json

from django.core.exceptions import RequestDataTooBig
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from graphlab import ingestion, llm
from graphlab.db import GraphConnectionError
from graphlab.views import json_response


@require_GET
@ensure_csrf_cookie
def page(request):
    return render(request, "graphlab/documents.html")


def _payload(request):
    if request.content_type != "application/json":
        raise ingestion.ReviewError("Content-Type: application/json 형식으로 보내세요.")
    try:
        if len(request.body) > 256 * 1024:
            raise ingestion.ReviewError("문서 등록 요청은 256KB 이하로 제한됩니다.")
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError, RequestDataTooBig) as exc:
        raise ingestion.ReviewError("유효한 256KB 이하 JSON 객체를 보내세요.") from exc
    if not isinstance(data, dict):
        raise ingestion.ReviewError("JSON 객체 형식으로 보내세요.")
    return data


def _respond(callback):
    try:
        return json_response(callback())
    except ingestion.ReviewConflict as exc:
        return json_response({"error": str(exc), "code": "review_conflict"}, status=409)
    except ingestion.ReviewError as exc:
        return json_response({"error": str(exc), "code": "invalid_document"}, status=400)
    except llm.LLMError as exc:
        return json_response({"error": str(exc), "code": "llm_unavailable"}, status=503)
    except GraphConnectionError as exc:
        return json_response({"error": str(exc), "code": "neo4j_unavailable"}, status=503)


@require_GET
def catalog(request):
    return _respond(ingestion.catalog)


@require_POST
def extract(request):
    return _respond(lambda: ingestion.extract(_payload(request)))


@require_POST
def save(request):
    return _respond(lambda: ingestion.save(_payload(request)))

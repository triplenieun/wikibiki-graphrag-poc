from django.http import JsonResponse
from django.views.decorators.http import require_GET

from graphlab import repository
from graphlab.db import GraphConnectionError


def json_response(data, status=200):
    response = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})
    # Graph/document mutations must be visible on the very next request.
    response["Cache-Control"] = "no-store"
    return response


def graph_response(operation):
    try:
        result = operation()
    except GraphConnectionError as exc:
        return json_response({"error": str(exc)}, status=503)
    if result is None:
        return json_response({"error": "해당 서비스를 찾을 수 없습니다."}, status=404)
    return json_response(result)


@require_GET
def index(request):
    return json_response({
        "project": "Django + Neo4j 입문 실습",
        "guide": "README.md",
        "routes": [
            "/graphrag/",
            "/documents/",
            "/api/services/",
            "/api/services/order-service/context/",
            "/api/services/auth-service/impact/",
        ],
    })


@require_GET
def services(request):
    return graph_response(lambda: {"services": repository.list_services()})


@require_GET
def context(request, service_id):
    return graph_response(lambda: repository.service_context(service_id))


@require_GET
def impact(request, service_id):
    return graph_response(lambda: repository.service_impact(service_id))

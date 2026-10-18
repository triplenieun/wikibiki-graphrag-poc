from django.urls import path

from graphlab import rag_views, views

urlpatterns = [
    path("", views.index, name="index"),
    path("graphrag/", rag_views.page, name="graphrag"),
    path("api/graph/", rag_views.graph, name="graph"),
    path("api/graphrag/status/", rag_views.status, name="graphrag-status"),
    path("api/graphrag/retrieve/", rag_views.retrieve, name="graphrag-retrieve"),
    path("api/graphrag/ask/", rag_views.ask, name="graphrag-ask"),
    path("api/services/", views.services, name="services"),
    path("api/services/<slug:service_id>/context/", views.context, name="context"),
    path("api/services/<slug:service_id>/impact/", views.impact, name="impact"),
]

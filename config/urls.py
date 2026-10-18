from django.urls import path

from graphlab import ingestion_views, rag_views, views

urlpatterns = [
    path("", views.index, name="index"),
    path("graphrag/", rag_views.page, name="graphrag"),
    path("documents/", ingestion_views.page, name="documents"),
    path("api/documents/catalog/", ingestion_views.catalog, name="documents-catalog"),
    path("api/documents/extract/", ingestion_views.extract, name="documents-extract"),
    path("api/documents/save/", ingestion_views.save, name="documents-save"),
    path("api/graph/", rag_views.graph, name="graph"),
    path("api/graphrag/status/", rag_views.status, name="graphrag-status"),
    path("api/graphrag/retrieve/", rag_views.retrieve, name="graphrag-retrieve"),
    path("api/graphrag/ask/", rag_views.ask, name="graphrag-ask"),
    path("api/services/", views.services, name="services"),
    path("api/services/<slug:service_id>/context/", views.context, name="context"),
    path("api/services/<slug:service_id>/impact/", views.impact, name="impact"),
]

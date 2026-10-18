from django.urls import path

from graphlab import ingestion_views, rag_views, views

urlpatterns = [
    path("", views.index, name="index"),
    path("graphrag/", rag_views.page, name="graphrag"),
    path("documents/", ingestion_views.page, name="documents"),
    path("documents/manage/", ingestion_views.manage_page, name="documents-manage"),
    path("api/documents/", ingestion_views.listing, name="documents-list"),
    path("api/documents/catalog/", ingestion_views.catalog, name="documents-catalog"),
    path("api/documents/extract/", ingestion_views.extract, name="documents-extract"),
    path("api/documents/save/", ingestion_views.save, name="documents-save"),
    path("api/documents/<slug:document_id>/", ingestion_views.detail, name="document-detail"),
    path("api/documents/<slug:document_id>/extract/", ingestion_views.extract_update, name="document-extract-update"),
    path("api/documents/<slug:document_id>/update/", ingestion_views.update, name="document-update"),
    path("api/documents/<slug:document_id>/delete/", ingestion_views.delete, name="document-delete"),
    path("api/graph/", rag_views.graph, name="graph"),
    path("api/graphrag/status/", rag_views.status, name="graphrag-status"),
    path("api/graphrag/retrieve/", rag_views.retrieve, name="graphrag-retrieve"),
    path("api/graphrag/ask/", rag_views.ask, name="graphrag-ask"),
    path("api/services/", views.services, name="services"),
    path("api/services/<slug:service_id>/context/", views.context, name="context"),
    path("api/services/<slug:service_id>/impact/", views.impact, name="impact"),
]

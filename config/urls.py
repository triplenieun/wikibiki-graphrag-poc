from django.urls import path

from graphlab import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/services/", views.services, name="services"),
    path("api/services/<slug:service_id>/context/", views.context, name="context"),
    path("api/services/<slug:service_id>/impact/", views.impact, name="impact"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("events/", views.home, name="home"),
]

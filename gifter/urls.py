from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("events/", views.home, name="home"),
    path("events/new/", views.event_create, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("wishes/", views.wishlist, name="wishlist"),
    path("wishes/new/", views.wish_create, name="wish_create"),
    path("invite/<slug:token>/", views.invite, name="invite"),
    path("privacy/", views.privacy, name="privacy"),
]

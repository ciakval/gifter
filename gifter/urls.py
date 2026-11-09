from django.urls import path

from . import claim_views, views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("events/", views.home, name="home"),
    path("events/new/", views.event_create, name="event_create"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("events/<int:pk>/share-all/", views.event_share_all, name="event_share_all"),
    path(
        "events/<int:pk>/wishes/<int:wish_pk>/claim/",
        claim_views.wish_claim,
        name="wish_claim",
    ),
    path(
        "events/<int:pk>/wishes/<int:wish_pk>/chip-in/",
        claim_views.wish_chip_in,
        name="wish_chip_in",
    ),
    path("claims/<int:wish_pk>/purchased/", claim_views.claim_purchased, name="claim_purchased"),
    path("claims/<int:wish_pk>/release/", claim_views.claim_release, name="claim_release"),
    path("claims/<int:wish_pk>/leave/", claim_views.chip_in_leave, name="chip_in_leave"),
    path("wishes/", views.wishlist, name="wishlist"),
    path("wishes/new/", views.wish_create, name="wish_create"),
    path("wishes/<int:pk>/edit/", views.wish_edit, name="wish_edit"),
    path("wishes/<int:pk>/delete/", views.wish_delete, name="wish_delete"),
    path("invite/<slug:token>/", views.invite, name="invite"),
    path("privacy/", views.privacy, name="privacy"),
]

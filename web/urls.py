"""
URL configuration for the Gifter project.

Google sign-in lives under accounts/ (allauth); everything else is the gifter app.
"""

from django.urls import include, path

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("", include("gifter.urls")),
]

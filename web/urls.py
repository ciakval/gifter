"""
URL configuration for the Gifter project.

Google sign-in lives under accounts/ (allauth); everything else is the gifter app.

Route order is load-bearing: the two login redirects must come BEFORE the allauth and admin
includes, otherwise those packages' own login pages would answer first.
"""

from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.generic import RedirectView

# Every password-style login page ends up at the Google landing page, keeping ?next=.
# login_not_required: otherwise LoginRequiredMiddleware would redirect this redirect view itself.
to_landing = login_not_required(
    RedirectView.as_view(pattern_name="landing", query_string=True)
)

urlpatterns = [
    path("accounts/login/", to_landing),
    path("accounts/", include("allauth.urls")),
    path("gifter-admin/login/", to_landing),
    path("gifter-admin/", admin.site.urls),
    path("", include("gifter.urls")),
]

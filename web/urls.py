"""
URL configuration for the Gifter project.

Google is the only way in (AUTH-01), and that is enforced here: instead of including every
route the sign-in library offers, accounts/ lists exactly the routes Google-only sign-in needs.
Everything else under accounts/ is deliberately 404 (alternative token sign-in endpoint,
connected-accounts page, legacy aliases, inactive page, email, password, code and session
routes). Adding a route means updating the URL-table test in gifter/tests/test_lockdown.py.

Why each allowlisted route exists:
- accounts/login/            library code reverses the name account_login; it redirects to the
                             landing page and keeps ?next= (D-04)
- accounts/logout/           sign out (confirmation page, POST signs out)
- accounts/3rdparty/login/cancelled/ and .../error/
                             where a refused or failed Google sign-in ends
- accounts/3rdparty/signup/  finishes a Google sign-up that cannot complete automatically,
                             e.g. when the email already belongs to another user
- accounts/google/login/     starts Google sign-in (POST only; GET shows a confirmation page)
- accounts/google/login/callback/
                             where Google sends the browser back

Route order is load-bearing: the two login redirects must come BEFORE the admin include,
otherwise the admin's own login page would answer first.
"""

from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.generic import RedirectView

from allauth.account import views as account_views
from allauth.socialaccount import views as socialaccount_views
from allauth.socialaccount.providers.google import views as google_views

# Every password-style login page ends up at the Google landing page, keeping ?next=.
# login_not_required: otherwise LoginRequiredMiddleware would redirect this redirect view itself.
to_landing = login_not_required(
    RedirectView.as_view(pattern_name="landing", query_string=True)
)

urlpatterns = [
    path("accounts/login/", to_landing, name="account_login"),
    path("accounts/logout/", account_views.logout, name="account_logout"),
    path(
        "accounts/3rdparty/login/cancelled/",
        socialaccount_views.login_cancelled,
        name="socialaccount_login_cancelled",
    ),
    path(
        "accounts/3rdparty/login/error/",
        socialaccount_views.login_error,
        name="socialaccount_login_error",
    ),
    path(
        "accounts/3rdparty/signup/",
        socialaccount_views.signup,
        name="socialaccount_signup",
    ),
    path("accounts/google/login/", google_views.oauth2_login, name="google_login"),
    path(
        "accounts/google/login/callback/",
        google_views.oauth2_callback,
        name="google_callback",
    ),
    path("gifter-admin/login/", to_landing),
    path("gifter-admin/", admin.site.urls),
    path("", include("gifter.urls")),
]

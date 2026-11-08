"""
Google is the only door (Phase 1, plan 01-02): password-style routes are closed or redirected.

Run with: DEBUG=1 uv run python manage.py test
"""

from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver

from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from gifter.tests.test_auth import (
    GOOGLE_LOGIN_URL,
    GOOGLE_USERINFO,
    GoogleRoundTripMixin,
    fake_get_access_token,
)


def make_user(username, email="", **extra):
    user = get_user_model().objects.create_user(username=username, email=email, **extra)
    user.set_unusable_password()
    user.save()
    return user


class LoginRedirectTests(TestCase):
    def test_accounts_login_redirects_to_landing_keeping_next(self):
        response = self.client.get("/accounts/login/?next=/events/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/?next=/events/")

    def test_accounts_login_post_does_not_sign_in(self):
        response = self.client.post("/accounts/login/", {"login": "a", "password": "b"})
        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_login_redirects_to_landing_keeping_next(self):
        response = self.client.get("/gifter-admin/login/?next=/gifter-admin/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/?next=/gifter-admin/")

    def test_closed_routes_are_404(self):
        for path in ("/accounts/signup/", "/accounts/password/reset/", "/admin/", "/login/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


class AdminAccessTests(TestCase):
    def test_anonymous_admin_ends_on_landing_with_next(self):
        response = self.client.get("/gifter-admin/", follow=True)
        self.assertEqual(response.status_code, 200)
        # LoginRequiredMiddleware percent-encodes next; the landing view decodes it.
        self.assertEqual(unquote(response.redirect_chain[-1][0]), "/?next=/gifter-admin/")
        self.assertTemplateUsed(response, "gifter/landing.html")

    def test_staff_reaches_admin(self):
        staff = make_user("boss", "boss@example.com", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/gifter-admin/").status_code, 200)

    def test_non_staff_bounced_without_loop(self):
        self.client.force_login(make_user("anna", "anna@example.com"))
        response = self.client.get("/gifter-admin/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.redirect_chain), 4)
        self.assertEqual(response.redirect_chain[-1][0], "/events/")


class LogoutTests(TestCase):
    def test_get_logout_does_not_sign_out(self):
        self.client.force_login(make_user("anna", "anna@example.com"))
        response = self.client.get("/accounts/logout/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_logout_signs_out(self):
        self.client.force_login(make_user("anna", "anna@example.com"))
        self.client.post("/accounts/logout/")
        self.assertNotIn("_auth_user_id", self.client.session)


class PromoteStaffTests(TestCase):
    def test_promotes_case_insensitively(self):
        user = make_user("anna", "anna@example.com")
        call_command("promote_staff", "ANNA@example.com", stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_unknown_email_fails(self):
        with self.assertRaises(CommandError):
            call_command("promote_staff", "nobody@example.invalid", stdout=StringIO())


ALLOWED_ACCOUNTS_ROUTES = {
    "accounts/login/",
    "accounts/logout/",
    "accounts/3rdparty/login/cancelled/",
    "accounts/3rdparty/login/error/",
    "accounts/3rdparty/signup/",
    "accounts/google/login/",
    "accounts/google/login/callback/",
}


def walk_routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from walk_routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield route


class AccountsUrlTableTests(TestCase):
    def test_accounts_routes_are_exactly_the_allowlist(self):
        found = {route for route in walk_routes(get_resolver().url_patterns) if route.startswith("accounts/")}
        self.assertEqual(found, ALLOWED_ACCOUNTS_ROUTES)

    def test_closed_routes_are_404_for_anonymous_and_signed_in(self):
        paths = [
            "/accounts/",
            "/accounts/google/login/token/",
            "/accounts/3rdparty/",
            "/accounts/social/login/cancelled/",
            "/accounts/social/login/error/",
            "/accounts/social/signup/",
            "/accounts/social/connections/",
            "/accounts/inactive/",
            "/accounts/signup/",
            "/accounts/email/",
            "/accounts/password/change/",
            "/accounts/password/set/",
            "/accounts/password/reset/",
            "/accounts/reauthenticate/",
            "/accounts/confirm-email/",
            "/accounts/login/code/",
            "/accounts/sessions/",
            "/accounts/2fa/",
        ]
        for signed_in in (False, True):
            if signed_in:
                self.client.force_login(make_user("anna", "anna@example.com"))
            for path in paths:
                with self.subTest(path=path, signed_in=signed_in):
                    self.assertEqual(self.client.get(path).status_code, 404)

    def test_one_tap_token_post_is_404(self):
        response = self.client.post("/accounts/google/login/token/", {"credential": "x"})
        self.assertEqual(response.status_code, 404)

    def test_get_google_login_shows_confirmation_and_never_redirects(self):
        response = self.client.get(GOOGLE_LOGIN_URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("accounts.google.com", response.get("Location", ""))


def fake_other_complete_login(self, request, app, token, **kwargs):
    data = dict(GOOGLE_USERINFO, sub="9999999999", email="eve@example.com", given_name="Eve")
    return self.get_provider().sociallogin_from_response(request, data)


class AdapterFlowTests(GoogleRoundTripMixin, TestCase):
    def test_inactive_account_ends_on_landing_with_message(self):
        self.sign_in()
        user = get_user_model().objects.get()
        self.client.post("/accounts/logout/")
        user.is_active = False
        user.save()

        callback = self.sign_in()
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        page = self.client.get("/")
        self.assertContains(page, "This Gifter account is switched off")

    def test_connect_by_signed_in_user_adds_nothing_and_returns_to_events(self):
        self.sign_in()
        self.assertEqual(SocialAccount.objects.count(), 1)

        authorize = self.client.post(GOOGLE_LOGIN_URL, {"process": "connect"})
        self.assertEqual(authorize.status_code, 302)

        state = parse_qs(urlparse(authorize["Location"]).query)["state"][0]
        with (
            mock.patch.object(OAuth2Client, "get_access_token", fake_get_access_token),
            mock.patch.object(GoogleOAuth2Adapter, "complete_login", fake_other_complete_login),
        ):
            callback = self.client.get(
                "/accounts/google/login/callback/", {"code": "dummy-code", "state": state}
            )
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/events/")
        self.assertEqual(SocialAccount.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.filter(user=get_user_model().objects.get()).count(), 1)

    def test_email_conflict_reaches_the_signup_page(self):
        make_user("existing", "anna@example.com")
        callback = self.sign_in()
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/accounts/3rdparty/signup/")
        page = self.client.get("/accounts/3rdparty/signup/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "/static/vendor/bootstrap/bootstrap.min.css")

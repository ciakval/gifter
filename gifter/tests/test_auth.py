"""
Walking-skeleton tests for Google sign-in (Phase 1, plan 01-01).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test
"""

import re
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.test import TestCase
from django.urls import reverse

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

GOOGLE_LOGIN_URL = "/accounts/google/login/"
GOOGLE_CALLBACK_URL = "/accounts/google/login/callback/"

GOOGLE_USERINFO = {
    "sub": "1234567890",
    "email": "anna@example.com",
    "email_verified": True,
    "given_name": "Anna",
    "family_name": "Novak",
    "name": "Anna Novak",
}


def fake_get_access_token(self, code, pkce_code_verifier=None, extra_data=None):
    return {
        "access_token": "fake-access-token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "id_token": "fake-id-token",
    }


def fake_complete_login(self, request, app, token, **kwargs):
    return self.get_provider().sociallogin_from_response(request, dict(GOOGLE_USERINFO))


class GoogleRoundTripMixin:
    """Drive the whole OAuth dance against a mocked Google."""

    def start_login(self, next_value=None):
        data = {} if next_value is None else {"next": next_value}
        response = self.client.post(GOOGLE_LOGIN_URL, data)
        self.assertEqual(response.status_code, 302)
        return response

    def finish_login(self, authorize_response):
        query = parse_qs(urlparse(authorize_response["Location"]).query)
        state = query["state"][0]
        with (
            mock.patch.object(OAuth2Client, "get_access_token", fake_get_access_token),
            mock.patch.object(GoogleOAuth2Adapter, "complete_login", fake_complete_login),
        ):
            return self.client.get(GOOGLE_CALLBACK_URL, {"code": "dummy-code", "state": state})

    def sign_in(self, next_value=None):
        return self.finish_login(self.start_login(next_value))


class LandingTests(TestCase):
    def test_landing_anonymous(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        form = re.search(r'<form[^>]*method="post"[^>]*>', html)
        self.assertIsNotNone(form, "landing page has no POST form")
        self.assertIn('action="/accounts/google/login/"', form.group(0))
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertRegex(html, r'<input[^>]*type="hidden"[^>]*name="next"')
        self.assertIn("Sign in with Google", html)

    def test_landing_hides_user_data(self):
        get_user_model().objects.create(username="zdenka", first_name="Zdenka")
        response = self.client.get("/")
        self.assertNotContains(response, "Zdenka")

    def test_no_third_party_assets(self):
        user = get_user_model().objects.create(username="anna", first_name="Anna")
        pages = [self.client.get("/").content.decode()]
        self.client.force_login(user)
        pages.append(self.client.get(reverse("home")).content.decode())
        for html in pages:
            self.assertIsNone(re.search(r'(?:src|href)\s*=\s*["\']?https?://', html, re.IGNORECASE))


class AccessControlTests(TestCase):
    def test_protected_redirects_with_next(self):
        response = self.client.get("/events/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/?next=/events/")

    def test_unresolvable_path_404(self):
        self.assertEqual(self.client.get("/login/").status_code, 404)
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_signed_in_landing_redirects_home(self):
        user = get_user_model().objects.create(username="anna", first_name="Anna")
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/events/")


class GoogleSignInTests(GoogleRoundTripMixin, TestCase):
    def test_google_round_trip_returns_to_next(self):
        authorize = self.start_login("/events/")
        location = urlparse(authorize["Location"])
        self.assertEqual(location.netloc, "accounts.google.com")
        query = parse_qs(location.query)
        self.assertTrue(query["redirect_uri"][0].endswith(GOOGLE_CALLBACK_URL))
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(set(query["scope"][0].split()), {"openid", "email", "profile"})

        callback = self.finish_login(authorize)
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/events/")

        page = self.client.get("/events/")
        self.assertContains(page, "Hi Anna")
        user = get_user_model().objects.get(first_name="Anna")
        self.assertEqual(user.last_name, "Novak")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_empty_next_lands_home(self):
        callback = self.sign_in("")
        self.assertEqual(callback["Location"], reverse("home"))

    def test_absent_next_lands_home(self):
        callback = self.sign_in(None)
        self.assertEqual(callback["Location"], reverse("home"))

    def test_offsite_next_rejected(self):
        callback = self.sign_in("https://evil.example/")
        self.assertEqual(callback["Location"], reverse("home"))

    def test_session_cookie_90_days(self):
        callback = self.sign_in("/events/")
        self.assertEqual(int(callback.cookies["sessionid"]["max-age"]), 7776000)

    def test_post_logout(self):
        self.sign_in("/events/")
        response = self.client.post("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        after = self.client.get("/events/")
        self.assertEqual(after.status_code, 302)
        self.assertEqual(after["Location"], "/?next=/events/")


class UserModelInvariantTests(TestCase):
    def test_user_model_invariant(self):
        user_model = get_user_model()
        self.assertEqual(user_model._meta.label, "gifter.User")
        offenders = []
        for model in apps.get_models():
            for field in model._meta.get_fields():
                related = getattr(field, "related_model", None)
                if not field.is_relation or related is None or isinstance(related, str):
                    continue
                if related is not user_model and issubclass(related, AbstractBaseUser):
                    offenders.append(f"{model._meta.label}.{field.name} -> {related._meta.label}")
        self.assertEqual(offenders, [])

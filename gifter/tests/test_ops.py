"""Launch hardening (Phase 4, plan 04-05): health check, no-store on signed-in pages, dry-run kit."""

from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext


class HealthzTests(TestCase):
    def test_anonymous_get_is_ok_plain_text_uncached_and_cookieless(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(len(response.cookies), 0)
        self.assertIn("no-store", response["Cache-Control"])

    def test_head_is_ok_and_post_is_not_allowed(self):
        self.assertEqual(self.client.head("/healthz").status_code, 200)
        self.assertEqual(self.client.post("/healthz").status_code, 405)

    def test_signed_in_get_is_ok(self):
        user = get_user_model().objects.create_user(username="h", password="x")
        self.client.force_login(user)
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_database_failure_is_503_without_error_text(self):
        with mock.patch("gifter.views.connection") as conn:
            conn.cursor.side_effect = DatabaseError("secret-db-detail")
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"unavailable")
        self.assertNotIn(b"secret-db-detail", response.content)

    def test_trailing_slash_is_not_the_health_path(self):
        self.assertNotEqual(self.client.get("/healthz/").status_code, 200)

    def test_route_name_resolves_without_slash(self):
        self.assertEqual(reverse("healthz"), "/healthz")


class NoStoreTests(TestCase):
    def test_signed_in_pages_and_redirects_are_private_no_store(self):
        user = get_user_model().objects.create_user(username="n", password="x")
        self.client.force_login(user)
        page = self.client.get(reverse("home"))
        self.assertEqual(page.status_code, 200)
        redirect = self.client.get(reverse("landing"))
        self.assertEqual(redirect.status_code, 302)
        for response in (page, redirect):
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("private", response["Cache-Control"])

    def test_anonymous_public_pages_are_not_no_store(self):
        for name in ("landing", "privacy"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("no-store", response.get("Cache-Control", ""))


class DryRunKitTests(TestCase):
    LABELS = ["Sign in with Google", "Join", "Add wish", "I'll get this", "Release", "My claims"]

    def test_czech_message_quotes_the_real_czech_button_labels(self):
        path = Path(__file__).resolve().parents[2] / "docs" / "dry-run.md"
        text = path.read_text(encoding="utf-8")
        with translation.override("cs"):
            for label in self.LABELS:
                czech = gettext(label)
                self.assertNotEqual(czech, label, label)
                self.assertIn(czech, text, label)

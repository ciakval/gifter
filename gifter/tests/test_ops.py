"""Launch hardening (Phase 4, plan 04-05): health check, no-store on signed-in pages, dry-run kit."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


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

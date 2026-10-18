"""
Google is the only door (Phase 1, plan 01-02): password-style routes are closed or redirected.

Run with: DEBUG=1 uv run python manage.py test
"""

from io import StringIO
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


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

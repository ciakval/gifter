"""
allauth's own pages render inside Gifter's layout and lead back to sign-in (Phase 1, plan 01-02).

Run with: DEBUG=1 uv run python manage.py test
"""

from django.contrib.auth import get_user_model
from django.test import TestCase


class AllauthPageTests(TestCase):
    def test_logout_confirmation_uses_gifter_layout(self):
        user = get_user_model().objects.create_user(username="anna", email="anna@example.com")
        self.client.force_login(user)
        response = self.client.get("/accounts/logout/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/vendor/bootstrap/bootstrap.min.css")
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, 'method="post"')
        self.assertNotContains(response, "Menu:")
        self.assertNotContains(response, "Change Password")

    def test_cancelled_page_has_try_again_link(self):
        response = self.client.get("/accounts/3rdparty/login/cancelled/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "socialaccount/login_cancelled.html")
        self.assertContains(response, "/static/vendor/bootstrap/bootstrap.min.css")
        self.assertContains(response, '<a class="btn btn-primary btn-lg" href="/">Try again</a>', html=True)
        self.assertNotContains(response, "Menu:")

    def test_bogus_callback_renders_error_page_with_try_again(self):
        response = self.client.get("/accounts/google/login/callback/?code=x&state=bogus")
        self.assertTemplateUsed(response, "socialaccount/authentication_error.html")
        self.assertContains(response, "/static/vendor/bootstrap/bootstrap.min.css", status_code=response.status_code)
        self.assertContains(
            response,
            '<a class="btn btn-primary btn-lg" href="/">Try again</a>',
            html=True,
            status_code=response.status_code,
        )
        self.assertNotContains(response, "Menu:", status_code=response.status_code)

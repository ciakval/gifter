"""
Public privacy page tests (Phase 1, plan 01-06, AUTH-01).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_privacy
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from allauth.socialaccount.models import SocialToken

from gifter.tests.test_auth import GoogleRoundTripMixin

PRIVACY_URL = "/privacy/"

REQUIRED_PHRASES = [
    "Privacy policy",
    "Google account ID",
    "profile picture",
    "never sees your Google password",
    "up to 90 days",
    "never sells or shares your data",
    "no advertising and no analytics",
    "European Union",
]


class PrivacyPageTests(TestCase):
    def test_anonymous_gets_page_without_redirect(self):
        response = self.client.get(PRIVACY_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "gifter/privacy.html")

    def test_page_contains_required_phrases(self):
        html = self.client.get(PRIVACY_URL).content.decode()
        for phrase in REQUIRED_PHRASES:
            self.assertIn(phrase, html)

    def test_signed_in_user_also_gets_page(self):
        user = get_user_model().objects.create(username="anna", first_name="Anna")
        self.client.force_login(user)
        self.assertEqual(self.client.get(PRIVACY_URL).status_code, 200)

    @override_settings(GIFTER_CONTACT_EMAIL="privacy@example.org")
    def test_contact_email_is_a_mailto_link(self):
        self.assertContains(self.client.get(PRIVACY_URL), 'href="mailto:privacy@example.org"')

    @override_settings(GIFTER_CONTACT_EMAIL="")
    def test_without_contact_email_asks_the_inviter(self):
        response = self.client.get(PRIVACY_URL)
        self.assertNotContains(response, "mailto:")
        self.assertContains(response, "ask the person who invited you")

    def test_page_hides_user_data(self):
        get_user_model().objects.create(username="zdenka", first_name="Zdenka")
        self.assertNotContains(self.client.get(PRIVACY_URL), "Zdenka")

    def test_no_third_party_assets_only_a_navigation_link(self):
        html = self.client.get(PRIVACY_URL).content.decode()
        asset_tags = re.findall(r"<(?:link|script|img)\b[^>]*>", html, re.IGNORECASE)
        for tag in asset_tags:
            self.assertIsNone(
                re.search(r'(?:src|href)\s*=\s*["\']?https?://', tag, re.IGNORECASE), tag
            )
        anchor = re.search(r'<a\b[^>]*href="https://policies\.google\.com/privacy"[^>]*>', html)
        self.assertIsNotNone(anchor, "missing link to Google's privacy policy")
        self.assertIn('rel="noopener noreferrer"', anchor.group(0))

    def test_does_not_describe_unbuilt_features(self):
        html = self.client.get(PRIVACY_URL).content.decode().lower()
        for word in ("claim", "chip", "member"):
            self.assertNotIn(word, html)


class NoStoredTokensTests(GoogleRoundTripMixin, TestCase):
    def test_setting_is_false(self):
        self.assertIs(settings.SOCIALACCOUNT_STORE_TOKENS, False)

    def test_sign_in_stores_no_social_token(self):
        response = self.sign_in("/events/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SocialToken.objects.count(), 0)

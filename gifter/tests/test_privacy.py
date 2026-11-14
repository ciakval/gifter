"""
Public privacy page tests (Phase 1, plan 01-06, AUTH-01).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_privacy
"""

import datetime
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import translation
from django.utils.formats import date_format

from allauth.socialaccount.models import SocialToken

from gifter.tests.test_auth import GoogleRoundTripMixin
from gifter.tests.test_inapp import MESSENGER_IOS
from gifter.views import PRIVACY_POLICY_UPDATED

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
    "invite link",
    "names of the other members",
    "keeps a copy",
    "seen only by you",
    "Claims and chip-ins",
    "never sees any of this",
    "share at least one event with them",
    "marks a wish as received",
    "keeps seeing it in their My claims",
    "remembers the language you picked",
    "for up to a year",
    "one-off copy",
    "deletes it by hand",
    "Discussions",
    "last opened each discussion",
    "no notifications or emails",
    "never sees the discussion",
    "not even that the discussion exists",
    "Nobody can edit a comment",
]

# Sentences that are only true once a nightly backup exists; shown only while
# DATA_DIR/nightly-backups-since holds a valid date (D-12, fail closed).
GATED_PHRASES = (
    "backed up every night",
    "deleted after 14 days",
    "at most 14 days later",
)
# Msgids whose Czech text is legitimately identical to the English one.
SAME_IN_CZECH = ("Cookies",)
GATED_MSGIDS = (
    "Gifter's database is also backed up every night to a separate folder on the same server. "
    "Each nightly backup is deleted after 14 days.",
    "Anything Gifter erases on request can stay in the nightly backups made before the erasure "
    "until those backups are deleted, at most 14 days later.",
)

# Fragments of three sentences that claims make untrue (D-17, T-03-17): the completeness
# sentence, the deleted-wish-gone-for-everyone sentence, and the unshared-seen-only-by-owner one.
RETIRED_PHRASES = (
    "is all Gifter stores",
    "every page for everyone",
    "have not shared into any event",
    "forgery, and short-lived ones",
)


class TempDataDirMixin:
    """Point DATA_DIR at a fresh empty directory so a local data/ never changes the outcome."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        override = override_settings(DATA_DIR=self.data_dir)
        override.enable()
        self.addCleanup(override.disable)

    def write_marker(self, text):
        (self.data_dir / "nightly-backups-since").write_text(text, encoding="utf-8")

    def get_page(self, **extra):
        return self.client.get(PRIVACY_URL, **extra).content.decode()


class PrivacyPageTests(TempDataDirMixin, TestCase):
    def test_policy_describes_claims(self):
        html = self.client.get(PRIVACY_URL).content.decode()
        for phrase in (
            "Claims and chip-ins",
            "never sees any of this",
            "share at least one event with them",
            "marks a wish as received",
            "keeps seeing it in their My claims",
        ):
            self.assertIn(phrase, html)

    def test_policy_drops_retired_statements(self):
        html = self.client.get(PRIVACY_URL).content.decode()
        for phrase in RETIRED_PHRASES:
            self.assertNotIn(phrase, html)

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


class NightlyBackupMarkerTests(TempDataDirMixin, TestCase):
    def test_without_marker_no_gated_sentence_and_no_14_days(self):
        html = self.get_page()
        for phrase in GATED_PHRASES:
            self.assertNotIn(phrase, html)
        self.assertNotIn("14 days", html)

    def test_without_marker_czech_has_no_gated_sentence(self):
        html = self.get_page(HTTP_ACCEPT_LANGUAGE="cs")
        with translation.override("cs"):
            for msgid in GATED_MSGIDS:
                self.assertNotIn(translation.gettext(msgid), html)

    def test_with_marker_all_gated_sentences_in_both_languages(self):
        self.write_marker("2026-11-12\n")
        html = self.get_page()
        for phrase in GATED_PHRASES:
            self.assertIn(phrase, html)
        czech = self.get_page(HTTP_ACCEPT_LANGUAGE="cs")
        with translation.override("cs"):
            for msgid in GATED_MSGIDS:
                translated = translation.gettext(msgid)
                self.assertNotEqual(translated, msgid)
                self.assertIn(translated, czech)

    def test_unusable_marker_counts_as_absent(self):
        for text in ("", "soon", "2026-13-40", "2026-1-2", "2026-11-12 junk"):
            with self.subTest(text=text):
                self.write_marker(text)
                response = self.client.get(PRIVACY_URL)
                self.assertEqual(response.status_code, 200)
                for phrase in GATED_PHRASES:
                    self.assertNotContains(response, phrase)

    def test_marker_is_read_per_request(self):
        for phrase in GATED_PHRASES:
            self.assertNotIn(phrase, self.get_page())
        self.write_marker("2026-11-12\n")
        for phrase in GATED_PHRASES:
            self.assertIn(phrase, self.get_page())

    def test_last_updated_is_the_later_of_constant_and_marker(self):
        self.write_marker("2099-01-02\n")
        with translation.override("en"):
            later = date_format(datetime.date(2099, 1, 2), "DATE_FORMAT")
            constant = date_format(PRIVACY_POLICY_UPDATED, "DATE_FORMAT")
        self.assertIn(later, self.get_page(HTTP_ACCEPT_LANGUAGE="en"))
        self.write_marker("2020-01-02\n")
        self.assertIn(constant, self.get_page(HTTP_ACCEPT_LANGUAGE="en"))

    def test_czech_page_is_fully_translated(self):
        self.write_marker("2026-11-12\n")
        source = (
            Path(settings.BASE_DIR) / "gifter" / "templates" / "gifter" / "privacy.html"
        ).read_text(encoding="utf-8")
        msgids = re.findall(r'\{% translate "((?:[^"\\]|\\.)*)" %\}', source)
        self.assertGreater(len(msgids), 20)
        html = self.get_page(HTTP_ACCEPT_LANGUAGE="cs")
        self.assertIn('lang="cs"', html)
        with translation.override("cs"):
            for msgid in msgids:
                translated = translation.gettext(msgid)
                if msgid not in SAME_IN_CZECH:
                    self.assertNotEqual(translated, msgid, msgid)
                    self.assertNotIn(msgid, html, msgid)
                self.assertIn(translated, html, msgid)


class NoStoredTokensTests(GoogleRoundTripMixin, TestCase):
    def test_setting_is_false(self):
        self.assertIs(settings.SOCIALACCOUNT_STORE_TOKENS, False)

    def test_sign_in_stores_no_social_token(self):
        response = self.sign_in("/events/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SocialToken.objects.count(), 0)


class FooterLinkTests(TestCase):
    """Every page extending gifter/base.html links to the policy (Google's app home page is /)."""

    def assertLinksToPrivacy(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/privacy/"')

    def test_landing_links_to_privacy(self):
        self.assertLinksToPrivacy(self.client.get("/"))

    def test_in_app_landing_links_to_privacy(self):
        response = self.client.get("/", HTTP_USER_AGENT=MESSENGER_IOS)
        self.assertContains(response, "Copy link")  # the in-app hint variant is rendered
        self.assertLinksToPrivacy(response)

    def test_home_links_to_privacy(self):
        user = get_user_model().objects.create(username="anna", first_name="Anna")
        self.client.force_login(user)
        self.assertLinksToPrivacy(self.client.get("/events/"))

    def test_allauth_page_links_to_privacy(self):
        user = get_user_model().objects.create(username="anna", first_name="Anna")
        self.client.force_login(user)
        self.assertLinksToPrivacy(self.client.get("/accounts/logout/"))

    def test_privacy_page_links_to_itself(self):
        self.assertLinksToPrivacy(self.client.get(PRIVACY_URL))

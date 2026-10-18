"""
In-app browser hint tests (Phase 1, plan 01-03, OPS-04).

Run with: DEBUG=1 uv run python manage.py test gifter.tests.test_inapp
"""

import re
from html import unescape

from django.test import SimpleTestCase, TestCase

from gifter.inapp import is_in_app_browser

MESSENGER_IOS = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 [FBAN/MessengerForiOS;FBAV/450.0.0.30.113;"
    "FBBV/565678;FBDV/iPhone14,5;FBMD/iPhone;FBSN/iOS;FBSV/17.5;FBSS/3;FBID/phone;"
    "FBLC/en_US;FBOP/5]"
)
FACEBOOK_ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.144 "
    "Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/440.0.0.33.113;]"
)
FACEBOOK_IOS = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/450.0.0.30.113;FBBV/565678]"
)
INSTAGRAM_IOS = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 Instagram 330.0.0.35.101 (iPhone14,5; "
    "iOS 17_5; en_US; en; scale=3.00; 1170x2532; 570000000)"
)
INSTAGRAM_ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A.230901.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.144 "
    "Mobile Safari/537.36 Instagram 330.0.0.38.89 Android (33/13; 420dpi)"
)
TIKTOK = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36 BytedanceWebview/d8a21c6"
)
TIKTOK_MUSICAL = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 musical_ly_33.0.0 JsSdk/2.0"
)
LINKEDIN = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 LinkedInApp/9.30.1234"
)
SNAPCHAT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 Snapchat/12.80.0.34 (like Safari/8618.2.12)"
)
ANDROID_WEBVIEW = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B Build/TP1A.220624.014; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.144 "
    "Mobile Safari/537.36"
)

CHROME_ANDROID = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.6099.144 Mobile Safari/537.36"
)
SAFARI_IOS = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
FIREFOX_DESKTOP = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"
)
CHROME_DESKTOP = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

IN_APP_AGENTS = {
    "messenger ios": MESSENGER_IOS,
    "facebook android": FACEBOOK_ANDROID,
    "facebook ios": FACEBOOK_IOS,
    "instagram ios": INSTAGRAM_IOS,
    "instagram android": INSTAGRAM_ANDROID,
    "tiktok bytedance": TIKTOK,
    "tiktok musical_ly": TIKTOK_MUSICAL,
    "linkedin": LINKEDIN,
    "snapchat": SNAPCHAT,
    "android webview": ANDROID_WEBVIEW,
}

NORMAL_AGENTS = {
    "chrome android": CHROME_ANDROID,
    "safari ios": SAFARI_IOS,
    "firefox desktop": FIREFOX_DESKTOP,
    "chrome desktop": CHROME_DESKTOP,
    "empty": "",
    "none": None,
}

GOOGLE_FORM_ACTION = "/accounts/google/login/"


class IsInAppBrowserTests(SimpleTestCase):
    def test_in_app_agents_detected(self):
        for name, agent in IN_APP_AGENTS.items():
            with self.subTest(name):
                self.assertTrue(is_in_app_browser(agent))

    def test_normal_agents_not_detected(self):
        for name, agent in NORMAL_AGENTS.items():
            with self.subTest(name):
                self.assertFalse(is_in_app_browser(agent))


class LandingHintTests(TestCase):
    def test_messenger_gets_hint_instead_of_form(self):
        response = self.client.get("/", HTTP_USER_AGENT=MESSENGER_IOS)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn(GOOGLE_FORM_ACTION, html)
        self.assertNotIn("<form", html)
        self.assertContains(response, "Open Gifter in your browser")
        self.assertContains(response, "Continue anyway")
        self.assertEqual(response.context["copy_url"], "http://testserver/")
        self.assertRegex(
            html, r'<input[^>]*type="text"[^>]*value="http://testserver/"[^>]*readonly'
        )

    def test_every_in_app_agent_gets_hint(self):
        for name, agent in IN_APP_AGENTS.items():
            with self.subTest(name):
                response = self.client.get("/", HTTP_USER_AGENT=agent)
                self.assertContains(response, "Open Gifter in your browser")
                self.assertNotContains(response, GOOGLE_FORM_ACTION)

    def test_next_survives_in_link_and_continue_anyway(self):
        response = self.client.get("/?next=/events/", HTTP_USER_AGENT=INSTAGRAM_IOS)
        copy_url = "http://testserver/?next=%2Fevents%2F"
        self.assertEqual(response.context["copy_url"], copy_url)
        self.assertNotIn("force", response.context["copy_url"])
        self.assertRegex(unescape(response.content.decode()), r'value="%s"' % re.escape(copy_url))
        force_url = response.context["force_url"]
        self.assertTrue(force_url.startswith("/?"))
        self.assertIn("force=1", force_url)
        self.assertIn("next=%2Fevents%2F", force_url)
        self.assertContains(response, 'href="%s"' % force_url.replace("&", "&amp;"))

    def test_continue_anyway_shows_normal_form(self):
        response = self.client.get(
            "/?force=1&next=/events/", HTTP_USER_AGENT=MESSENGER_IOS
        )
        self.assertContains(response, GOOGLE_FORM_ACTION)
        self.assertContains(response, 'name="next" value="/events/"')
        self.assertNotContains(response, "Open Gifter in your browser")

    def test_continue_anyway_link_leads_to_google_form(self):
        hint = self.client.get("/?next=/events/", HTTP_USER_AGENT=MESSENGER_IOS)
        response = self.client.get(
            hint.context["force_url"], HTTP_USER_AGENT=MESSENGER_IOS
        )
        self.assertContains(response, GOOGLE_FORM_ACTION)
        self.assertContains(response, 'name="next" value="/events/"')

    def test_normal_browsers_get_google_form(self):
        for name, agent in NORMAL_AGENTS.items():
            with self.subTest(name):
                kwargs = {} if agent is None else {"HTTP_USER_AGENT": agent}
                response = self.client.get("/", **kwargs)
                self.assertContains(response, GOOGLE_FORM_ACTION)
                self.assertNotContains(response, "Open Gifter in your browser")

    def test_hint_has_no_jargon(self):
        response = self.client.get("/", HTTP_USER_AGENT=MESSENGER_IOS)
        html = response.content.decode().lower()
        for word in ("webview", "user agent", "oauth", "disallowed_useragent"):
            with self.subTest(word):
                self.assertNotIn(word, html)

    def test_script_payload_in_next_is_escaped(self):
        payload = "%22%3E%3Cscript%3Ex%3C/script%3E"
        for agent in (MESSENGER_IOS, CHROME_ANDROID):
            with self.subTest(agent):
                response = self.client.get("/?next=" + payload, HTTP_USER_AGENT=agent)
                self.assertNotIn("<script>x</script>", response.content.decode())
        forced = self.client.get(
            "/?force=1&next=" + payload, HTTP_USER_AGENT=MESSENGER_IOS
        )
        self.assertNotIn("<script>x</script>", forced.content.decode())


class CopyLinkTests(TestCase):
    def test_copy_button_carries_landing_url(self):
        response = self.client.get("/", HTTP_USER_AGENT=MESSENGER_IOS)
        self.assertContains(response, "Copy link")
        self.assertContains(response, 'data-copy-url="http://testserver/"')
        self.assertContains(response, 'data-copied-label="Link copied"')
        self.assertRegex(response.content.decode(), r'<button type="button"[^>]*data-copy-url=')

    def test_copy_button_keeps_next_without_force(self):
        response = self.client.get("/?next=/events/", HTTP_USER_AGENT=INSTAGRAM_IOS)
        self.assertContains(response, 'data-copy-url="http://testserver/?next=%2Fevents%2F"')
        self.assertNotContains(response, 'data-copy-url="http://testserver/?force')

    def test_script_loaded_with_defer(self):
        response = self.client.get("/", HTTP_USER_AGENT=MESSENGER_IOS)
        self.assertRegex(
            response.content.decode(),
            r'<script src="/static/gifter/landing\.js" defer></script>',
        )

    def test_normal_browser_has_no_script_or_button(self):
        response = self.client.get("/", HTTP_USER_AGENT=CHROME_ANDROID)
        self.assertNotContains(response, "gifter/landing.js")
        self.assertNotContains(response, "Copy link")
        self.assertNotContains(response, "data-copy-url")

"""
The phone pass (plan 04-04, I18N-02, D-05, D-07): stock Bootstrap plus one small stylesheet.

Run with DEBUG=1:  DEBUG=1 uv run python manage.py test gifter.tests.test_phone

The tests pin markup and CSS, not rendering: every page carries the viewport tag and gifter.css
after the vendored Bootstrap, gifter.css sets 44px tap targets and no theme, groups of actions
stack below 576px, and no row or width can force horizontal scrolling at 360px.
"""

import re
from pathlib import Path

import gifter
from django.test import Client, TestCase, override_settings

from gifter.tests.test_events import make_user
from gifter.tests.test_inapp import MESSENGER_IOS
from gifter.tests.test_secrecy import Fixture, perform, probes

VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
GIFTER_DIR = Path(gifter.__file__).parent
TEMPLATES_DIR = GIFTER_DIR / "templates"
CSS_PATH = GIFTER_DIR / "static" / "gifter" / "gifter.css"
BOOTSTRAP_LINK = "vendor/bootstrap/bootstrap.min.css"
GIFTER_LINK = "gifter/gifter.css"


def strip_css_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def check_page(testcase, response, label):
    """A final 200 HTML page: viewport tag and gifter.css after Bootstrap."""
    if response.status_code != 200 or "text/html" not in response["Content-Type"]:
        return False
    body = response.content.decode("utf-8")
    testcase.assertEqual(body.count(VIEWPORT), 1, f"{label}: viewport tag")
    link = re.search(r'<link[^>]+href="[^"]*gifter/gifter(?:\.[0-9a-f]+)?\.css"', body)
    testcase.assertIsNotNone(link, f"{label}: gifter.css link")
    boot = body.find(BOOTSTRAP_LINK)
    testcase.assertTrue(0 <= boot < link.start(), f"{label}: gifter.css after Bootstrap")
    return True


class PhoneCrawlTests(TestCase):
    def test_every_get_probe_page(self):
        fx = Fixture()
        checked = 0
        for probe in probes(fx):
            if probe.method != "GET":
                continue
            response = perform(fx.gita, probe)
            checked += check_page(self, response, probe.label)
        self.assertGreater(checked, 5)

    def test_anonymous_pages(self):
        client = Client()
        for path, extra in (
            ("/", {}),
            ("/", {"HTTP_USER_AGENT": MESSENGER_IOS}),
            ("/privacy/", {}),
            ("/accounts/3rdparty/login/cancelled/", {}),
        ):
            response = client.get(path, follow=True, **extra)
            self.assertTrue(check_page(self, response, path), f"{path} did not return HTML 200")

    def test_empty_states(self):
        newbie = make_user("newbie", first_name="Newbie")
        client = Client()
        client.force_login(newbie)
        for path in ("/events/", "/wishes/", "/claims/"):
            response = client.get(path, follow=True)
            self.assertTrue(check_page(self, response, path), f"{path} did not return HTML 200")


@override_settings(LANGUAGE_CODE="cs")
class CzechPhoneCrawlTests(PhoneCrawlTests):
    pass


def rules_for(css, selector):
    """Declaration blocks of every rule whose selector list contains the selector."""
    blocks = []
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in [s.strip() for s in selectors.split(",")]:
            blocks.append(body)
    return blocks


class StylesheetTests(TestCase):
    def setUp(self):
        self.assertTrue(CSS_PATH.is_file(), "gifter.css missing")
        self.css = strip_css_comments(CSS_PATH.read_text(encoding="utf-8"))

    def test_tap_targets(self):
        for selector in (".btn", ".nav-link", "summary", ".form-check-label", "footer a"):
            blocks = rules_for(self.css, selector)
            self.assertTrue(
                any(re.search(r"min-height:\s*2\.75rem", b) for b in blocks),
                f"{selector} has no 44px min-height",
            )
        self.assertTrue(
            any(re.search(r"min-width:\s*2\.75rem", b) for b in rules_for(self.css, ".btn"))
        )

    def test_main_wraps(self):
        self.assertTrue(
            any(
                re.search(r"overflow-wrap:\s*anywhere", b) for b in rules_for(self.css, "main")
            )
        )

    def test_no_theme_no_reordering(self):
        for forbidden in (
            r"(?<![-\w])color\s*:",
            r"background",
            r"font-family",
            r"font\s*:",
            r"(?<![-\w])order\s*:",
            r"row-reverse",
            r"column-reverse",
            r"url\(",
            r"@import",
        ):
            self.assertIsNone(re.search(forbidden, self.css), f"gifter.css contains {forbidden}")


GROUP = "d-grid gap-2 d-sm-flex"
TEMPLATE_GROUPS = {
    "includes/owner_wish.html": [["Edit", "Delete", "Received"], ["Reopen"]],
    "includes/member_wish.html": [["Mark purchased", "Release"]],
    "my_claims.html": [["Mark purchased", "Release"], ["Remove from my claims"]],
    "event_detail.html": [["My wishlist", "Share all my wishes here"]],
    "wish_form.html": [["Save", "Add wish", "Cancel"]],
    "wish_confirm_delete.html": [["Delete", "Cancel"]],
}


def group_texts(source):
    """Texts of the buttons and links inside each element carrying the stacking classes."""
    result = []
    for match in re.finditer(r'class="[^"]*' + re.escape(GROUP) + r'[^"]*"', source):
        depth, end = 1, None
        # Walk to the matching close of the element (div or form) that opened the class.
        open_tag = source.rfind("<", 0, match.start())
        name = re.match(r"<(\w+)", source[open_tag:]).group(1)
        pattern = re.compile(rf"<(/?){name}\b")
        for tag in pattern.finditer(source, match.end()):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                end = tag.start()
                break
        inner = source[match.end():end]
        texts = re.findall(r"\{% translate \"([^\"]+)\" %\}", inner)
        result.append(texts)
    return result


class StackingGroupTests(TestCase):
    def test_every_template_has_a_stacking_group(self):
        for name in TEMPLATE_GROUPS:
            source = (TEMPLATES_DIR / "gifter" / name).read_text(encoding="utf-8")
            self.assertIn(GROUP, source, name)

    def test_order_is_kept(self):
        for name, expected_groups in TEMPLATE_GROUPS.items():
            source = (TEMPLATES_DIR / "gifter" / name).read_text(encoding="utf-8")
            found = group_texts(source)
            self.assertTrue(found, name)
            for expected in expected_groups:
                # a group matches when its action texts appear in the recorded wide-screen order
                self.assertTrue(
                    any(
                        [t for t in texts if t in expected] == [t for t in expected if t in texts]
                        and any(t in expected for t in texts)
                        for texts in found
                    ),
                    f"{name}: {expected} not found in order in {found}",
                )

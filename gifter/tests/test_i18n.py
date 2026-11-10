"""
Czech and English (Phase 4, plan 04-01, I18N-01, D-01..D-03).

The language lives only in Django's language cookie; the browser's Accept-Language is the default.
Czech is asserted by comparing against the catalogue inside translation.override("cs"), never by
hard-coding Czech words.

Run with: DEBUG=1 uv run python manage.py test gifter.tests.test_i18n
"""

import re

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase
from django.utils import translation
from django.utils.translation import gettext, ngettext

from gifter.tests.test_events import make_user


def czech(text):
    with translation.override("cs"):
        return gettext(text)


class SwitchTests(TestCase):
    def setUp(self):
        self.anna = make_user("anna", "Anna", "A", "anna@example.com")

    def test_catalogue_has_czech_for_my_wishlist(self):
        self.assertNotEqual(czech("My wishlist"), "My wishlist")

    def test_signed_in_page_holds_one_switch_form_in_the_top_bar(self):
        self.client.force_login(self.anna)
        html = self.client.get("/events/").content.decode()
        forms = re.findall(r'<form[^>]*action="/i18n/setlang/"[^>]*>.*?</form>', html, re.S)
        self.assertEqual(len(forms), 1)
        self.assertIn('name="next" value="/events/"', forms[0])
        buttons = re.findall(r'<button[^>]*name="language"[^>]*value="(\w+)"', forms[0])
        self.assertEqual(buttons, ["en", "cs"])
        nav = html[html.index('id="gifter-nav"') : html.index("</nav>")]
        self.assertIn("/i18n/setlang/", nav)
        footer = html[html.index("<footer") :]
        self.assertNotIn("/i18n/setlang/", footer)

    def test_anonymous_landing_shows_the_switch_in_the_footer(self):
        html = self.client.get("/").content.decode()
        footer = html[html.index("<footer") :]
        self.assertIn("/i18n/setlang/", footer)
        self.assertEqual(html.count("/i18n/setlang/"), 1)

    def test_post_sets_cookie_and_the_next_page_is_czech_then_back(self):
        self.client.force_login(self.anna)
        response = self.client.post("/i18n/setlang/", {"language": "cs", "next": "/events/"})
        self.assertRedirects(response, "/events/", fetch_redirect_response=False)
        cookie = response.cookies["django_language"]
        self.assertEqual(cookie.value, "cs")
        self.assertEqual(cookie["max-age"], 31536000)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        page = self.client.get("/events/")
        self.assertContains(page, '<html lang="cs">')
        self.assertContains(page, czech("My wishlist"))
        self.client.post("/i18n/setlang/", {"language": "en", "next": "/events/"})
        page = self.client.get("/events/")
        self.assertContains(page, '<html lang="en">')
        self.assertContains(page, ">My wishlist<")

    def test_anonymous_post_redirects_back_not_to_sign_in(self):
        response = self.client.post("/i18n/setlang/", {"language": "cs", "next": "/privacy/"})
        self.assertRedirects(response, "/privacy/", fetch_redirect_response=False)
        self.assertEqual(response.cookies["django_language"].value, "cs")

    def test_open_redirect_is_refused(self):
        response = self.client.post(
            "/i18n/setlang/", {"language": "cs", "next": "https://evil.example/"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")

    def test_unknown_or_missing_language_sets_no_cookie_but_redirects(self):
        for data in ({"language": "xx", "next": "/privacy/"}, {"next": "/privacy/"}):
            with self.subTest(data=data):
                response = self.client.post("/i18n/setlang/", data)
                self.assertRedirects(response, "/privacy/", fetch_redirect_response=False)
                self.assertNotIn("django_language", response.cookies)

    def test_get_never_sets_the_cookie(self):
        response = self.client.get("/i18n/setlang/?language=cs&next=/privacy/")
        self.assertNotIn("django_language", response.cookies)

    def test_choice_is_stored_nowhere_but_the_cookie(self):
        self.client.force_login(self.anna)
        before_user = get_user_model().objects.filter(pk=self.anna.pk).values().get()
        before_session = dict(self.client.session)
        self.client.post("/i18n/setlang/", {"language": "cs", "next": "/events/"})
        self.assertEqual(
            get_user_model().objects.filter(pk=self.anna.pk).values().get(), before_user
        )
        self.assertEqual(dict(self.client.session), before_session)


class BrowserDefaultTests(TestCase):
    def lang(self, **extra):
        html = self.client.get("/", **extra).content.decode()
        return re.search(r'<html lang="(\w+)"', html).group(1)

    def test_czech_browser_gets_czech(self):
        for header in ("cs", "cs-CZ", "de, en;q=0.5, cs;q=0.8"):
            with self.subTest(header=header):
                self.assertEqual(self.lang(HTTP_ACCEPT_LANGUAGE=header), "cs")

    def test_no_header_or_unsupported_header_is_english(self):
        self.assertEqual(self.lang(), "en")
        self.assertEqual(self.lang(HTTP_ACCEPT_LANGUAGE="de"), "en")

    def test_cookie_beats_the_browser_header(self):
        self.client.cookies["django_language"] = "en"
        self.assertEqual(self.lang(HTTP_ACCEPT_LANGUAGE="cs"), "en")


class EncodingTests(TestCase):
    def test_czech_page_is_utf8_with_plain_diacritics(self):
        response = self.client.get("/privacy/", HTTP_ACCEPT_LANGUAGE="cs")
        self.assertIn("charset=utf-8", response["Content-Type"].lower())
        html = response.content.decode("utf-8")
        self.assertIn('<meta charset="utf-8">', html)
        self.assertRegex(html, "[řčůěšž]")
        self.assertNotRegex(html, r"&[a-z]caron;|&#\d+;|Ã|Å™")


# --- Task 2: plurals and catalogue ---

PLURAL_HEADER = "nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2;"


def django_cs_plural_expression():
    """The plural equation of Django's own compiled cs catalogue (its header spans two .po lines)."""
    import gettext
    import pathlib

    import django

    mo = pathlib.Path(django.__file__).parent / "conf/locale/cs/LC_MESSAGES/django.mo"
    with mo.open("rb") as handle:
        header = gettext.GNUTranslations(handle).info()["plural-forms"]
    return re.search(r"plural=([^;]*);?", header).group(1)


class PluralTests(TestCase):
    def test_po_header_has_the_pinned_three_form_expression(self):
        import pathlib

        from django.conf import settings

        po = (pathlib.Path(settings.BASE_DIR) / "locale/cs/LC_MESSAGES/django.po").read_text(
            encoding="utf-8"
        )
        self.assertIn(f'"Plural-Forms: {PLURAL_HEADER}\\n"', po)

    def test_three_forms_agree_with_django_for_every_integer(self):
        from gettext import c2py

        ours = c2py("(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2")
        theirs = c2py(django_cs_plural_expression())
        mapping = {0: 0, 1: 1, 3: 2}
        for n in range(1001):
            self.assertNotEqual(theirs(n), 2, n)
            self.assertEqual(ours(n), mapping[theirs(n)], n)

    def member_count(self, n):
        template = Template(
            "{% load i18n %}{% blocktranslate count counter=n %}{{ counter }} member"
            "{% plural %}{{ counter }} members{% endblocktranslate %}"
        )
        return template.render(Context({"n": n}))

    def test_member_count_has_three_czech_forms(self):
        with translation.override("cs"):
            texts = {n: self.member_count(n) for n in (0, 1, 2, 4, 5, 11, 21)}
        bare = {n: re.sub(r"\d+", "", text) for n, text in texts.items()}
        self.assertEqual(len({bare[1], bare[2], bare[5]}), 3)
        self.assertEqual(bare[2], bare[4])
        self.assertEqual({bare[5], bare[11], bare[21], bare[0]}, {bare[5]})
        for text in texts.values():
            self.assertNotIn("member", text)

    def test_wish_share_message_is_translated_for_1_2_5(self):
        singular = "%(count)d wish is shared here now."
        plural = "%(count)d wishes are shared here now."
        with translation.override("cs"):
            for n in (1, 2, 5):
                text = ngettext(singular, plural, n) % {"count": n}
                self.assertNotEqual(text, (singular if n == 1 else plural) % {"count": n})
                self.assertIn(str(n), text)

    def test_django_own_czech_plurals_still_work(self):
        with translation.override("cs"):
            got = [ngettext("%(num)d minute", "%(num)d minutes", n) % {"num": n} for n in (1, 2, 5)]
        self.assertEqual(got, ["1 minuta", "2 minuty", "5 minut"])

"""
Google is the only door (Phase 1, plan 01-02): password-style routes are closed or redirected.

Run with: DEBUG=1 uv run python manage.py test
"""

from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from gifter.tests.test_auth import (
    GOOGLE_LOGIN_URL,
    GOOGLE_USERINFO,
    GoogleRoundTripMixin,
    fake_get_access_token,
)
from gifter.models import Claim, Contribution, Event, Membership, Wish
from gifter.tests.test_events import join, make_event
from gifter.tests.test_wishes import make_wish


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


def make_google_user(username, email, uid, verified=True):
    """A user as Google sign-in creates one: unusable password, primary email, Google account."""
    user = make_user(username, email)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=verified)
    SocialAccount.objects.create(
        user=user,
        provider="google",
        uid=uid,
        extra_data={"email": email, "email_verified": verified, "sub": uid},
    )
    return user


class PromoteStaffTests(TestCase):
    def run_command(self, email):
        out = StringIO()
        call_command("promote_staff", email, stdout=out)
        return out.getvalue()

    def assert_nobody_promoted(self):
        self.assertFalse(get_user_model().objects.filter(is_staff=True).exists())
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())

    def test_promotes_verified_google_email_case_insensitively_and_prints_uid(self):
        user = make_google_user("anna", "anna@example.com", "1234567890")
        output = self.run_command("ANNA@example.com")
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertIn("Google uid 1234567890", output)

    def test_unknown_email_fails(self):
        make_google_user("anna", "anna@example.com", "1")
        with self.assertRaises(CommandError):
            self.run_command("nobody@example.invalid")
        self.assert_nobody_promoted()

    def test_user_email_without_google_account_is_refused(self):
        make_user("anna", "anna@example.com")
        with self.assertRaises(CommandError):
            self.run_command("anna@example.com")
        self.assert_nobody_promoted()

    def test_unverified_google_email_is_refused(self):
        make_google_user("anna", "anna@example.com", "1", verified=False)
        with self.assertRaises(CommandError):
            self.run_command("anna@example.com")
        self.assert_nobody_promoted()

    def test_two_verified_google_accounts_with_same_email_are_refused(self):
        make_google_user("anna", "anna@example.com", "1")
        make_google_user("anna2", "ANNA@example.com", "2")
        with self.assertRaises(CommandError) as ctx:
            self.run_command("anna@example.com")
        self.assertIn("Nobody was promoted.", str(ctx.exception))
        self.assert_nobody_promoted()

    def test_user_with_two_google_accounts_is_refused(self):
        user = make_google_user("anna", "anna@example.com", "1")
        SocialAccount.objects.create(
            user=user,
            provider="google",
            uid="2",
            extra_data={"email": "anna@example.com", "email_verified": True},
        )
        with self.assertRaises(CommandError):
            self.run_command("anna@example.com")
        self.assert_nobody_promoted()


class DeleteUserCommandTests(TestCase):
    """manage.py delete_user: the operator's deletion route, which never shows claim counts."""

    def setUp(self):
        self.anna = make_google_user("anna", "anna@example.com", "1")
        self.bob = make_google_user("bob", "bob@example.com", "2")
        self.carl = make_user("carl")
        self.event = make_event(self.bob, name="Christmas")
        join(self.event, self.anna)
        join(self.event, self.carl)
        self.wish_a = make_wish(self.anna, name="Lamp", events=[self.event])
        self.wish_b = make_wish(self.bob, name="Hat", events=[self.event])

    def add_claims(self):
        claim = Claim.objects.create(wish=self.wish_a, claimer=self.bob)
        Contribution.objects.create(claim=claim, user=self.carl, note="from carl")
        Claim.objects.create(wish=self.wish_b, claimer=self.carl)

    def run_command(self, *args):
        out = StringIO()
        call_command("delete_user", *args, stdout=out)
        return out.getvalue()

    def in_rolled_back_state(self, claims, *args):
        sid = transaction.savepoint()
        try:
            if claims:
                self.add_claims()
            return self.run_command(*args)
        finally:
            transaction.savepoint_rollback(sid)

    def test_dry_run_names_the_account_and_deletes_nothing(self):
        output = self.run_command("bob")
        self.assertIn("bob", output)
        self.assertIn("bob@example.com", output)
        self.assertIn("Nothing was deleted", output)
        self.assertTrue(get_user_model().objects.filter(username="bob").exists())

    def test_yes_deletes_the_user_and_everything_tied_to_them(self):
        self.add_claims()
        output = self.run_command("bob", "--yes")
        self.assertIn("bob", output)
        User = get_user_model()
        self.assertFalse(User.objects.filter(username="bob").exists())
        self.assertFalse(SocialAccount.objects.filter(uid="2").exists())
        self.assertFalse(EmailAddress.objects.filter(email="bob@example.com").exists())
        self.assertFalse(Wish.objects.filter(pk=self.wish_b.pk).exists())
        self.assertFalse(Membership.objects.filter(user_id=self.bob.pk).exists())
        # Bob's claim on Anna's wish went with Carl's chip-in on it, and Carl's claim on Bob's
        # wish went with the wish.
        self.assertEqual(Claim.objects.count(), 0)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertTrue(User.objects.filter(username="anna").exists())
        self.assertTrue(User.objects.filter(username="carl").exists())
        self.assertTrue(Wish.objects.filter(pk=self.wish_a.pk).exists())
        event = Event.objects.get(pk=self.event.pk)
        self.assertIsNone(event.created_by)

    def test_output_is_identical_with_and_without_claims(self):
        for args in (("bob",), ("bob", "--yes")):
            with self.subTest(args=args):
                self.assertEqual(
                    self.in_rolled_back_state(False, *args),
                    self.in_rolled_back_state(True, *args),
                )

    def test_output_prints_no_number_that_depends_on_the_data(self):
        output = self.in_rolled_back_state(True, "bob", "--yes")
        self.assertNotRegex(output.replace("bob@example.com", ""), r"\d")

    def test_unknown_username_fails(self):
        before = get_user_model().objects.count()
        with self.assertRaises(CommandError) as ctx:
            self.run_command("nobody", "--yes")
        self.assertIn("Nobody was deleted", str(ctx.exception))
        self.assertEqual(get_user_model().objects.count(), before)

    def test_last_staff_account_is_refused(self):
        dave = make_user("dave", is_staff=True)
        for args in (("dave",), ("dave", "--yes")):
            with self.subTest(args=args):
                with self.assertRaises(CommandError) as ctx:
                    self.run_command(*args)
                self.assertIn("Nobody was deleted", str(ctx.exception))
                self.assertTrue(get_user_model().objects.filter(pk=dave.pk).exists())
        self.carl.is_staff = True
        self.carl.save()
        self.run_command("dave", "--yes")
        self.assertFalse(get_user_model().objects.filter(pk=dave.pk).exists())


class AdminLockdownTests(TestCase):
    def setUp(self):
        self.boss = make_user("boss", "boss@example.com", is_staff=True, is_superuser=True)
        self.client.force_login(self.boss)

    def test_social_app_and_token_pages_are_404(self):
        for path in (
            "/gifter-admin/socialaccount/socialapp/",
            "/gifter-admin/socialaccount/socialapp/add/",
            "/gifter-admin/socialaccount/socialtoken/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_social_account_and_email_address_are_view_only(self):
        make_google_user("anna", "anna@example.com", "1234567890")
        for path in (
            "/gifter-admin/socialaccount/socialaccount/",
            "/gifter-admin/account/emailaddress/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertNotContains(self.client.get("/gifter-admin/account/emailaddress/"), "make_verified")
        for path in (
            "/gifter-admin/socialaccount/socialaccount/add/",
            "/gifter-admin/account/emailaddress/add/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        account = SocialAccount.objects.get()
        address = EmailAddress.objects.get()
        for path in (
            f"/gifter-admin/socialaccount/socialaccount/{account.pk}/delete/",
            f"/gifter-admin/account/emailaddress/{address.pk}/delete/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        for path in (
            "/gifter-admin/socialaccount/socialaccount/",
            "/gifter-admin/account/emailaddress/",
        ):
            with self.subTest(path=path):
                self.assertNotContains(self.client.get(path), 'value="delete_selected"')

    def test_social_account_change_page_has_no_save_button(self):
        make_google_user("anna", "anna@example.com", "1234567890")
        account = SocialAccount.objects.get()
        page = self.client.get(f"/gifter-admin/socialaccount/socialaccount/{account.pk}/change/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'name="_save"')

    def test_user_delete_is_refused_and_not_offered(self):
        # Supersedes the 01-07 WR-04 must-have that an admin user deletion works (03-03, SECR-01):
        # the delete confirmation lists Claim rows, so people are deleted with delete_user.
        anna = make_google_user("anna", "anna@example.com", "1234567890")
        url = f"/gifter-admin/gifter/user/{anna.pk}/delete/"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
        listing = self.client.post(
            "/gifter-admin/gifter/user/",
            {"action": "delete_selected", "_selected_action": [anna.pk], "post": "yes"},
        )
        self.assertNotContains(listing, 'value="delete_selected"')
        self.assertTrue(get_user_model().objects.filter(pk=anna.pk).exists())
        self.assertEqual(SocialAccount.objects.count(), 1)
        self.assertEqual(EmailAddress.objects.count(), 1)
        self.assertNotContains(self.client.get("/gifter-admin/gifter/user/"), 'value="delete_selected"')
        self.assertNotContains(
            self.client.get(f"/gifter-admin/gifter/user/{anna.pk}/change/"), url
        )

    def test_dangerous_and_secret_models_are_not_registered(self):
        for model in (SocialApp, SocialToken, Wish, Claim, Contribution):
            with self.subTest(model=model.__name__):
                self.assertFalse(admin.site.is_registered(model))


ALLOWED_ACCOUNTS_ROUTES = {
    "accounts/login/",
    "accounts/logout/",
    "accounts/3rdparty/login/cancelled/",
    "accounts/3rdparty/login/error/",
    "accounts/3rdparty/signup/",
    "accounts/google/login/",
    "accounts/google/login/callback/",
}


def walk_routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from walk_routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            yield route


# Routes whose view opts out of LoginRequiredMiddleware (login_required = False). A new public
# route must be added here and to the probes in test_secrecy.py on purpose.
PUBLIC_ROUTES = {
    "",
    "healthz",
    "privacy/",
    "invite/<slug:token>/",
    "accounts/login/",
    "accounts/logout/",
    "accounts/3rdparty/login/cancelled/",
    "accounts/3rdparty/signup/",
    "accounts/google/login/",
    "accounts/google/login/callback/",
    "gifter-admin/login/",
    "i18n/setlang/",
}


def walk_public_routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from walk_public_routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern):
            if getattr(pattern.callback, "login_required", True) is False:
                yield route


class PublicRoutesTests(TestCase):
    def test_public_routes_are_exactly_the_allowlist(self):
        """A new public route must be added to PUBLIC_ROUTES and to the secrecy probes on purpose."""
        found = set(walk_public_routes(get_resolver().url_patterns))
        self.assertEqual(found, PUBLIC_ROUTES)


class AccountsUrlTableTests(TestCase):
    def test_accounts_routes_are_exactly_the_allowlist(self):
        found = {route for route in walk_routes(get_resolver().url_patterns) if route.startswith("accounts/")}
        self.assertEqual(found, ALLOWED_ACCOUNTS_ROUTES)

    def test_closed_routes_are_404_for_anonymous_and_signed_in(self):
        paths = [
            "/accounts/",
            "/accounts/google/login/token/",
            "/accounts/3rdparty/",
            "/accounts/social/login/cancelled/",
            "/accounts/social/login/error/",
            "/accounts/social/signup/",
            "/accounts/social/connections/",
            "/accounts/inactive/",
            "/accounts/signup/",
            "/accounts/email/",
            "/accounts/password/change/",
            "/accounts/password/set/",
            "/accounts/password/reset/",
            "/accounts/reauthenticate/",
            "/accounts/confirm-email/",
            "/accounts/login/code/",
            "/accounts/sessions/",
            "/accounts/2fa/",
        ]
        for signed_in in (False, True):
            if signed_in:
                self.client.force_login(make_user("anna", "anna@example.com"))
            for path in paths:
                with self.subTest(path=path, signed_in=signed_in):
                    self.assertEqual(self.client.get(path).status_code, 404)

    def test_one_tap_token_post_is_404(self):
        response = self.client.post("/accounts/google/login/token/", {"credential": "x"})
        self.assertEqual(response.status_code, 404)

    def test_get_google_login_shows_confirmation_and_never_redirects(self):
        response = self.client.get(GOOGLE_LOGIN_URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("accounts.google.com", response.get("Location", ""))


def fake_other_complete_login(self, request, app, token, **kwargs):
    data = dict(GOOGLE_USERINFO, sub="9999999999", email="eve@example.com", given_name="Eve")
    return self.get_provider().sociallogin_from_response(request, data)


class AdapterFlowTests(GoogleRoundTripMixin, TestCase):
    def test_inactive_account_ends_on_landing_with_message(self):
        self.sign_in()
        user = get_user_model().objects.get()
        self.client.post("/accounts/logout/")
        user.is_active = False
        user.save()

        callback = self.sign_in()
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/")
        self.assertNotIn("_auth_user_id", self.client.session)
        page = self.client.get("/")
        self.assertContains(page, "This Gifter account is switched off")

    def test_connect_by_signed_in_user_adds_nothing_and_returns_to_events(self):
        self.sign_in()
        self.assertEqual(SocialAccount.objects.count(), 1)

        authorize = self.client.post(GOOGLE_LOGIN_URL, {"process": "connect"})
        self.assertEqual(authorize.status_code, 302)

        state = parse_qs(urlparse(authorize["Location"]).query)["state"][0]
        with (
            mock.patch.object(OAuth2Client, "get_access_token", fake_get_access_token),
            mock.patch.object(GoogleOAuth2Adapter, "complete_login", fake_other_complete_login),
        ):
            callback = self.client.get(
                "/accounts/google/login/callback/", {"code": "dummy-code", "state": state}
            )
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/events/")
        self.assertEqual(SocialAccount.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.filter(user=get_user_model().objects.get()).count(), 1)

    def test_email_conflict_reaches_the_signup_page(self):
        make_user("existing", "anna@example.com")
        callback = self.sign_in()
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(callback["Location"], "/accounts/3rdparty/signup/")
        page = self.client.get("/accounts/3rdparty/signup/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "/static/vendor/bootstrap/bootstrap.min.css")

"""
The secrecy suite (Phase 3, plan 03-02, SECR-01, SECR-02, D-13 to D-16).

Core promise: the person whose wish it is (the giftee) never learns whether anyone claimed it,
who chipped in, or what they wrote. Run with DEBUG=1 (otherwise the production SSL redirect and
fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_secrecy

D-16: these tests run in the normal Django suite, and the deploy workflow's test job
(.github/workflows/deploy.yml) gates build-and-push, which gates deploy-production. A secrecy
failure therefore blocks every deploy.

D-14 as amended by the user on 2026-11-08: "protect whether/who, not vocabulary". The protected
property is information, not vocabulary. Generic copy (the My claims link, the privacy policy,
the giftee's own claims on other people's wishes) may use the words claim, taken, purchased and
chip anywhere. So this suite makes four kinds of assertion about the giftee's pages, and has
no page-wide word check and no list of pages excused from one:

- the sentinel proves that no hidden name or note crosses to the giftee (the sentinel user shares
  no event with her, and claimed or chipped in on her wishes, as a later "leave event" feature
  (v2 EVNT-07) will make possible);
- the byte-identical snapshots prove that nothing about her own wishes changes with claims
  (D-13); co-members' claims are covered here too, because she legitimately sees their names;
- the own-wish-region check proves that no claim-state label sits on or next to her own wishes,
  even though a co-member's claimed wish is on the same event page;
- every probe of a claim action gets the same 404 (D-15).

The suite also proves its own sensitivity on every run (test_detectors_catch_injected_owner_leak):
it injects a leak into the owner card through a test-only template override and checks that the
very same detectors report it.
"""

import copy
import re
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import get_resolver, resolve, reverse

import gifter
from gifter import claims
from gifter.models import Claim, Contribution, Wish
from gifter.tests.helpers import claim_state_markers, mask_csrf
from gifter.tests.test_events import join, make_event, make_user
from gifter.tests.test_lockdown import ALLOWED_ACCOUNTS_ROUTES, walk_routes
from gifter.tests.test_wishes import make_wish

SENTINEL = "zqxsentinel"

# One GET path for each admin route except its login (that one has the same string as the
# top-level redirect, which is probed separately). Registering a model in the admin adds routes
# and fails the route guard, so registering one must be a deliberate decision. Claim and
# Contribution are never registered.
ADMIN_PATHS = (
    "/gifter-admin/",
    "/gifter-admin/logout/",
    "/gifter-admin/password_change/",
    "/gifter-admin/password_change/done/",
    "/gifter-admin/autocomplete/",
    "/gifter-admin/jsi18n/",
    "/gifter-admin/r/1/1/",
    "/gifter-admin/auth/group/",
    "/gifter-admin/auth/group/add/",
    "/gifter-admin/auth/group/1/history/",
    "/gifter-admin/auth/group/1/delete/",
    "/gifter-admin/auth/group/1/change/",
    "/gifter-admin/auth/group/1/",
    "/gifter-admin/gifter/user/1/password/",
    "/gifter-admin/gifter/user/",
    "/gifter-admin/gifter/user/add/",
    "/gifter-admin/gifter/user/1/history/",
    "/gifter-admin/gifter/user/1/delete/",
    "/gifter-admin/gifter/user/1/change/",
    "/gifter-admin/gifter/user/1/",
    "/gifter-admin/socialaccount/socialaccount/",
    "/gifter-admin/socialaccount/socialaccount/add/",
    "/gifter-admin/socialaccount/socialaccount/1/history/",
    "/gifter-admin/socialaccount/socialaccount/1/delete/",
    "/gifter-admin/socialaccount/socialaccount/1/change/",
    "/gifter-admin/socialaccount/socialaccount/1/",
    "/gifter-admin/account/emailaddress/",
    "/gifter-admin/account/emailaddress/add/",
    "/gifter-admin/account/emailaddress/1/history/",
    "/gifter-admin/account/emailaddress/1/delete/",
    "/gifter-admin/account/emailaddress/1/change/",
    "/gifter-admin/account/emailaddress/1/",
    "/gifter-admin/gifter/",
    "/gifter-admin/no-such-page/",
)

# walked route string -> (example_path, reason). A route may enter this dict only when another
# pattern answers every path its own pattern matches; the reason names that pattern. A route that
# merely lacks a probe gets a probe, never an entry here. Empty at the time of writing.
UNREACHABLE_ROUTES = {}

TEMPLATES_DIR = Path(gifter.__file__).parent / "templates" / "gifter"


# --------------------------------------------------------------------------------------------
# Fixture
# --------------------------------------------------------------------------------------------


class Fixture:
    """Gita is the giftee. Sam is the sentinel user and shares no event with her."""

    def __init__(self):
        self.gita = make_user("gita", first_name="Gita")
        self.carl = make_user("carl", first_name="Carl")
        self.kim = make_user("kim", first_name="Kim")
        self.sam = make_user("sam", first_name="Zqxsentinel", last_name="Sam")
        self.oscar = make_user("oscar", first_name="Oscar")

        self.e1 = make_event(self.gita, name="Family Christmas")
        join(self.e1, self.carl)
        join(self.e1, self.kim)
        self.e2 = make_event(self.gita, name="Birthday")
        join(self.e2, self.kim)
        self.e9 = make_event(self.oscar, name="Office")
        join(self.e9, self.sam)

        self.w1 = make_wish(self.gita, name="Lego set", events=[self.e1, self.e2])
        self.w2 = make_wish(self.gita, name="Wool socks", events=[self.e1])
        self.w3 = make_wish(self.gita, name="Fountain pen", events=[self.e2])
        self.w4 = make_wish(
            self.gita, name="Old lamp", events=[self.e1], status=Wish.Status.RECEIVED
        )
        self.w5 = make_wish(
            self.gita, name="Cracked mug", events=[self.e1], status=Wish.Status.WITHDRAWN
        )
        self.w6 = make_wish(self.gita, name="Telescope")
        self.wc = make_wish(self.carl, name="Board game", events=[self.e1])
        self.wo = make_wish(self.oscar, name="Red hat", events=[self.e9])
        # Present in both states: Gita is not WC's giftee, so her E1 page always carries a
        # legitimate claim-bearing card next to her own wishes.
        Claim.objects.create(wish=self.wc, claimer=self.kim)


def add_claims(fx):
    """Claims, chip-ins and notes on Gita's wishes, created directly through the ORM."""
    c1 = Claim.objects.create(wish=fx.w1, claimer=fx.carl, status=Claim.Status.PURCHASED)
    Contribution.objects.create(claim=c1, user=fx.kim, note="Kim zqxsentinel <b>poznámka</b> ž")
    Contribution.objects.create(claim=c1, user=fx.sam, note="Zqxsentinel note")
    Claim.objects.create(wish=fx.w2, claimer=fx.sam)
    Claim.objects.create(wish=fx.w4, claimer=fx.kim)
    c5 = Claim.objects.create(wish=fx.w5, claimer=fx.carl)
    Contribution.objects.create(claim=c5, user=fx.sam, note="")
    Claim.objects.create(wish=fx.w6, claimer=fx.sam)
    Claim.objects.create(wish=fx.wo, claimer=fx.sam)


class with_claims:
    """Context manager: claims exist inside the block and are rolled back afterwards."""

    def __init__(self, fx):
        self.fx = fx

    def __enter__(self):
        self.sid = transaction.savepoint()
        add_claims(self.fx)

    def __exit__(self, *exc):
        transaction.savepoint_rollback(self.sid)
        return False


class SecrecyMixin:
    def setUp(self):
        self.fx = Fixture()


# --------------------------------------------------------------------------------------------
# Probes
# --------------------------------------------------------------------------------------------


class Probe(NamedTuple):
    label: str
    method: str
    path: str
    data: dict
    region: str | None  # "main", "event" or None: where Gita's own wishes are shown


def probes(fx):
    """Every route, from Gita's point of view, sorted by (path, method)."""
    found = []

    def add(label, method, path, data=None, region=None):
        found.append(Probe(f"{label} {method}", method, path, data or {}, region))

    w1 = fx.w1
    add("landing", "GET", reverse("landing"))
    add("home", "GET", reverse("home"))
    add("event_create", "GET", reverse("event_create"))
    add("event_create", "POST", reverse("event_create"), {"name": "New event", "description": ""})
    for label, event in (("E1", fx.e1), ("E2", fx.e2)):
        add(f"event_detail {label}", "GET", reverse("event_detail", args=[event.pk]), region="event")
    add("event_share_all", "POST", reverse("event_share_all", args=[fx.e1.pk]))
    add("wishlist", "GET", reverse("wishlist"), region="main")
    add("wish_create", "GET", reverse("wish_create"))
    add(
        "wish_create",
        "POST",
        reverse("wish_create"),
        {"name": "New wish", "description": "", "priority": "2", "events": [fx.e1.pk]},
    )
    add("wish_edit", "GET", reverse("wish_edit", args=[w1.pk]), region="main")
    add(
        "wish_edit",
        "POST",
        reverse("wish_edit", args=[w1.pk]),
        {
            "name": w1.name,
            "description": "",
            "priority": str(w1.priority),
            "links": "",
            "events": [fx.e1.pk, fx.e2.pk],
        },
    )
    add("wish_delete", "GET", reverse("wish_delete", args=[w1.pk]), region="main")
    add("wish_delete", "POST", reverse("wish_delete", args=[w1.pk]))
    add("wish_received", "POST", reverse("wish_received", args=[w1.pk]), region="main")
    add("wish_reopen", "POST", reverse("wish_reopen", args=[fx.w4.pk]), region="main")
    invite_path = reverse("invite", args=[fx.e1.invite_token])
    add("invite", "GET", invite_path)
    add("invite", "POST", invite_path)
    add("privacy", "GET", reverse("privacy"))
    add("my_claims", "GET", reverse("my_claims"))
    for name in ("wish_claim", "wish_chip_in"):
        path = reverse(name, args=[fx.e1.pk, w1.pk])
        add(name, "POST", path)
        add(name, "GET", path)
    for name in ("claim_purchased", "claim_release", "chip_in_leave", "claim_ack"):
        for wish in (w1, fx.w2):
            add(f"{name} W{wish.pk}", "POST", reverse(name, args=[wish.pk]))
    for route in sorted(ALLOWED_ACCOUNTS_ROUTES):
        add(f"accounts {route}", "GET", "/" + route)
    add("admin login redirect", "GET", "/gifter-admin/login/")
    for path in ADMIN_PATHS:
        add(f"admin {path}", "GET", path)
    return sorted(found, key=lambda p: (p.path, p.method))


def normalize_route(route):
    """Drop a ^ that begins a pattern segment: ResolverMatch.route does the same."""
    return re.sub(r"(^|/)\^", r"\1", route)


# --------------------------------------------------------------------------------------------
# Detectors. Module-level so the self-sensitivity test can run the same code on a mutant.
# --------------------------------------------------------------------------------------------


def fresh_client(user):
    client = Client()
    client.force_login(user)
    return client


def perform(user, probe, follow=True):
    """One request by a fresh client; a POST runs in a savepoint that is rolled back."""
    client = fresh_client(user)
    if probe.method == "GET":
        return client.get(probe.path, follow=follow)
    sid = transaction.savepoint()
    try:
        return client.post(probe.path, probe.data, follow=follow)
    finally:
        transaction.savepoint_rollback(sid)


def body_of(response):
    return response.content.decode("utf-8")


def _flashed(response):
    try:
        return [str(message) for message in response.context["messages"]]
    except (KeyError, TypeError):
        return []


def snapshot(fx, probe, claims_present):
    """(redirect chain, final status, flashed messages, masked final body)."""
    outer = transaction.savepoint()
    try:
        if claims_present:
            add_claims(fx)
        response = perform(fx.gita, probe)
        body = mask_csrf(body_of(response))
        if probe.label == "event_create POST":
            # A random invite token is minted for every new event.
            body = re.sub(r"/invite/[A-Za-z0-9_-]+/", "/invite/TOKEN/", body)
        return (response.redirect_chain, response.status_code, _flashed(response), body)
    finally:
        transaction.savepoint_rollback(outer)


def snapshot_findings(fx, selected):
    """Labels whose response differs between without-claims and with-claims."""
    return [
        probe.label
        for probe in selected
        if snapshot(fx, probe, False) != snapshot(fx, probe, True)
    ]


def sentinel_findings(fx, selected):
    """Labels whose final body contains the sentinel while claims by the sentinel user exist."""
    hits = []
    with with_claims(fx):
        for probe in selected:
            response = perform(fx.gita, probe)
            assert response.status_code < 500, (probe.label, response.status_code)
            if SENTINEL in body_of(response).lower():
                hits.append(probe.label)
    return hits


def own_wish_regions(kind, body):
    """The parts of a page that show Gita's own wishes."""
    if kind == "main":
        found = re.search(r"<main\b[^>]*>(.*?)</main>", body, re.S)
        return [found.group(1)] if found else []
    if kind == "event":
        start = body.find("Your wishes shared here")
        if start < 0:
            return []
        end = body.find("<h2", start)
        return [body[start : end if end >= 0 else len(body)]]
    return []


def region_findings(fx, selected):
    """(label, markers) for every own-wish region that carries claim-state copy."""
    found = []
    with with_claims(fx):
        for probe in selected:
            if probe.region is None:
                continue
            body = body_of(perform(fx.gita, probe))
            for region in own_wish_regions(probe.region, body):
                markers = claim_state_markers(region)
                if markers:
                    found.append((probe.label, markers))
    return found


# --------------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------------


class RouteGuardTests(SecrecyMixin, TestCase):
    """No resolvable route may exist outside the sweep (T-03-12)."""

    def test_every_walked_route_has_a_probe(self):
        walked = {normalize_route(r) for r in walk_routes(get_resolver().url_patterns)}
        probed = {resolve(urlsplit(p.path).path).route for p in probes(self.fx)}
        self.assertEqual(
            walked - set(UNREACHABLE_ROUTES),
            probed,
            "walked-only: routes without a probe; probed-only: probes that land on another route",
        )

    def test_admin_paths_are_distinct(self):
        self.assertEqual(len(ADMIN_PATHS), len(set(ADMIN_PATHS)))
        self.assertEqual(len(ADMIN_PATHS), 34)

    def test_unreachable_allowlist_cannot_hide_a_reachable_route(self):
        walked = {normalize_route(r) for r in walk_routes(get_resolver().url_patterns)}
        probed = {resolve(urlsplit(p.path).path).route for p in probes(self.fx)}
        for route, (example_path, _reason) in UNREACHABLE_ROUTES.items():
            with self.subTest(route=route):
                self.assertIn(route, walked, "stale entry")
                self.assertNotIn(route, probed, "a probe reaches this route")
                self.assertNotEqual(
                    resolve(example_path).route, route, "route is not shadowed by another"
                )

    def test_probe_paths_are_unique_per_method(self):
        keys = [(p.method, p.path) for p in probes(self.fx)]
        self.assertEqual(len(keys), len(set(keys)))

    def test_probes_are_sorted(self):
        listed = probes(self.fx)
        self.assertEqual(listed, sorted(listed, key=lambda p: (p.path, p.method)))


class SentinelCrawlTests(SecrecyMixin, TestCase):
    def test_sentinel_never_reaches_the_giftee(self):
        self.assertEqual(sentinel_findings(self.fx, probes(self.fx)), [])

    def test_sentinel_is_ascii_and_czech_html_notes_are_in_the_data(self):
        self.assertTrue(SENTINEL.isascii())
        with with_claims(self.fx):
            notes = set(Contribution.objects.values_list("note", flat=True))
        self.assertIn("Kim zqxsentinel <b>poznámka</b> ž", notes)
        self.assertEqual(self.fx.sam.display_name, "Zqxsentinel")

    def test_sentinel_user_shares_no_event_with_the_giftee(self):
        gita_events = set(self.fx.gita.events.values_list("pk", flat=True))
        sam_events = set(self.fx.sam.events.values_list("pk", flat=True))
        self.assertFalse(gita_events & sam_events)


class OwnWishRegionTests(SecrecyMixin, TestCase):
    def test_no_claim_state_in_the_giftees_own_wish_regions(self):
        selected = [p for p in probes(self.fx) if p.region]
        labels = {p.label for p in selected}
        for expected in (
            "wishlist GET",
            "wish_edit GET",
            "wish_delete GET",
            "event_detail E1 GET",
            "event_detail E2 GET",
            "wish_received POST",
            "wish_reopen POST",
        ):
            self.assertIn(expected, labels)
        self.assertEqual(region_findings(self.fx, selected), [])

    def test_regions_are_really_found(self):
        with with_claims(self.fx):
            for probe in probes(self.fx):
                if probe.region:
                    with self.subTest(probe=probe.label):
                        regions = own_wish_regions(probe.region, body_of(perform(self.fx.gita, probe)))
                        self.assertEqual(len(regions), 1)
                        self.assertTrue(regions[0].strip())

    def test_scoping_is_what_keeps_the_check_green(self):
        """A co-member's claim is on Gita's E1 page, just outside her own-wish region."""
        e1_page = next(p for p in probes(self.fx) if p.label == "event_detail E1 GET")
        with with_claims(self.fx):
            body = body_of(perform(self.fx.gita, e1_page))
        self.assertTrue(claim_state_markers(body))
        self.assertIn("Taken by Kim", body)
        self.assertEqual(claim_state_markers(own_wish_regions("event", body)[0]), [])


class ByteIdenticalTests(SecrecyMixin, TestCase):
    def test_every_probe_is_byte_identical_with_and_without_claims(self):
        self.assertEqual(Claim.objects.filter(wish__owner=self.fx.gita).count(), 0)
        self.assertEqual(Contribution.objects.count(), 0)
        for probe in probes(self.fx):
            with self.subTest(probe=probe.label):
                self.assertEqual(
                    snapshot(self.fx, probe, False), snapshot(self.fx, probe, True)
                )

    def test_without_claims_state_has_only_the_comember_claim(self):
        self.assertEqual(Claim.objects.count(), 1)
        self.assertEqual(Claim.objects.get().wish, self.fx.wc)
        self.assertEqual(Contribution.objects.count(), 0)

    def test_comparison_is_exact_after_masking_only_csrf(self):
        a = '<input type="hidden" name="csrfmiddlewaretoken" value="AAA"> x'
        b = '<input type="hidden" name="csrfmiddlewaretoken" value="BBB"> x'
        self.assertEqual(mask_csrf(a), mask_csrf(b))
        self.assertNotEqual(mask_csrf(a), mask_csrf(b.replace(" x", "  x")))
        self.assertNotEqual(mask_csrf(a), mask_csrf(a.replace("x", "y")))


class UniformNotFoundTests(SecrecyMixin, TestCase):
    def paths(self):
        fx = self.fx
        out = []
        for name in ("wish_claim", "wish_chip_in"):
            for event_pk, wish_pk in (
                (fx.e1.pk, fx.w1.pk),  # own, claimed
                (fx.e2.pk, fx.w3.pk),  # own, unclaimed
                (fx.e1.pk, 999999),  # nonexistent wish
                (999999, fx.w1.pk),  # nonexistent event
                (fx.e9.pk, fx.wo.pk),  # not her event
            ):
                out.append(reverse(name, args=[event_pk, wish_pk]))
        for name in ("claim_purchased", "claim_release", "chip_in_leave", "claim_ack"):
            for wish_pk in (fx.w1.pk, fx.w3.pk, fx.wo.pk, 999999):
                out.append(reverse(name, args=[wish_pk]))
        return out

    def rows(self):
        return (
            list(
                Claim.objects.order_by("pk").values_list(
                    "pk", "wish_id", "claimer_id", "status", "acknowledged_at"
                )
            ),
            list(
                Contribution.objects.order_by("pk").values_list(
                    "pk", "claim_id", "user_id", "note", "acknowledged_at"
                )
            ),
        )

    def test_every_probe_gets_the_same_404_and_changes_nothing(self):
        with with_claims(self.fx):
            before = self.rows()
            reference = fresh_client(self.fx.gita).post("/claims/999999/release/")
            self.assertEqual(reference.status_code, 404)
            for path in self.paths():
                with self.subTest(path=path):
                    response = fresh_client(self.fx.gita).post(path)
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.content, reference.content)
            outsider = fresh_client(self.fx.oscar).post(
                reverse("wish_claim", args=[self.fx.e1.pk, self.fx.w1.pk])
            )
            self.assertEqual(outsider.status_code, 404)
            self.assertEqual(outsider.content, reference.content)
            self.assertEqual(self.rows(), before)

    def test_404_matrix_covers_all_six_action_urls(self):
        names = {resolve(urlsplit(path).path).url_name for path in self.paths()}
        self.assertEqual(
            names,
            {
                "wish_claim",
                "wish_chip_in",
                "claim_purchased",
                "claim_release",
                "chip_in_leave",
                "claim_ack",
            },
        )


class OwnerQueryTests(SecrecyMixin, TestCase):
    LABELS = {
        "wishlist GET",
        "wish_create GET",
        "wish_create POST",
        "wish_edit GET",
        "wish_edit POST",
        "wish_delete GET",
        "wish_delete POST",
        "wish_received POST",
        "wish_reopen POST",
        "home GET",
        "privacy GET",
        "invite GET",
        "event_detail E2 GET",
    }

    def test_owner_views_never_query_the_claim_tables(self):
        selected = [p for p in probes(self.fx) if p.label in self.LABELS]
        self.assertEqual({p.label for p in selected}, self.LABELS)
        with with_claims(self.fx):
            for probe in selected:
                with self.subTest(probe=probe.label):
                    with CaptureQueriesContext(connection) as captured:
                        response = perform(self.fx.gita, probe)
                    self.assertLess(response.status_code, 500)
                    self.assertTrue(captured.captured_queries)
                    for query in captured.captured_queries:
                        sql = query["sql"].lower()
                        self.assertNotIn("gifter_claim", sql)
                        self.assertNotIn("gifter_contribution", sql)


class OwnerTemplateSourceTests(TestCase):
    FILES = (
        "includes/owner_wish.html",
        "wishlist.html",
        "wish_form.html",
        "wish_confirm_delete.html",
    )
    ACTION_URL_NAMES = (
        "wish_claim",
        "wish_chip_in",
        "claim_purchased",
        "claim_release",
        "chip_in_leave",
        "claim_ack",
    )

    def tags(self, name):
        source = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
        source = re.sub(r"\{%\s*comment\b.*?\{%\s*endcomment\s*%\}", "", source, flags=re.S)
        source = re.sub(r"\{#.*?#\}", "", source, flags=re.S)
        return re.findall(r"\{\{.*?\}\}|\{%.*?%\}", source, flags=re.S)

    def test_no_expression_names_claim_data(self):
        for name in self.FILES:
            for tag in self.tags(name):
                with self.subTest(file=name, tag=tag):
                    bare = re.sub(r'"[^"]*"|\'[^\']*\'', "", tag)
                    for identifier in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", bare):
                        lowered = identifier.lower()
                        for word in ("claim", "chip", "contribut"):
                            self.assertNotIn(word, lowered)

    def test_no_tag_targets_a_claim_action_or_participant_template(self):
        forbidden = set(self.ACTION_URL_NAMES) | {"member_wish.html", "my_claims.html"}
        for name in self.FILES:
            for tag in self.tags(name):
                for literal in re.findall(r'"([^"]*)"|\'([^\']*)\'', tag):
                    text = literal[0] or literal[1]
                    with self.subTest(file=name, literal=text):
                        self.assertFalse(
                            text in forbidden or text.endswith(("member_wish.html", "my_claims.html"))
                        )

    def test_the_scan_really_reads_the_files(self):
        for name in self.FILES:
            self.assertTrue(self.tags(name), name)


# --------------------------------------------------------------------------------------------
# Self-sensitivity (T-03-13): inject a leak and require the detectors to report it.
# --------------------------------------------------------------------------------------------


def leaked_claims(request):
    """Test-only context processor: the claim rows of the signed-in user's wishes."""
    if request.user.is_authenticated:
        return {
            "leaked_claims": list(
                Claim.objects.filter(wish__owner=request.user).select_related("claimer")
            )
        }
    return {"leaked_claims": []}


MUTANT_FRAGMENT = (
    "{% for leaked in leaked_claims %}{% if leaked.wish_id == wish.pk %}"
    '<span class="badge text-bg-warning">Taken by {{ leaked.claimer.display_name }}</span>'
    "{% endif %}{% endfor %}"
)


def mutant_templates():
    """The project's TEMPLATES, with owner_wish.html replaced by a leaking copy."""
    real = (TEMPLATES_DIR / "includes" / "owner_wish.html").read_text(encoding="utf-8")
    templates = copy.deepcopy(settings.TEMPLATES)
    entry = templates[0]
    entry["APP_DIRS"] = False
    options = entry.setdefault("OPTIONS", {})
    options["context_processors"] = [
        *options.get("context_processors", []),
        "gifter.tests.test_secrecy.leaked_claims",
    ]
    options["loaders"] = [
        (
            "django.template.loaders.locmem.Loader",
            {"gifter/includes/owner_wish.html": real + MUTANT_FRAGMENT},
        ),
        "django.template.loaders.app_directories.Loader",
    ]
    return templates


class SelfSensitivityTests(SecrecyMixin, TestCase):
    PAGES = ("wishlist GET", "event_detail E1 GET")

    def pages(self):
        selected = [p for p in probes(self.fx) if p.label in self.PAGES]
        self.assertEqual({p.label for p in selected}, set(self.PAGES))
        return selected

    def test_detectors_catch_injected_owner_leak(self):
        selected = self.pages()
        # Without the injected leak the detectors report nothing, so any finding below comes
        # from the override.
        self.assertEqual(snapshot_findings(self.fx, selected), [])
        self.assertEqual(sentinel_findings(self.fx, selected), [])
        self.assertEqual(region_findings(self.fx, selected), [])

        with override_settings(TEMPLATES=mutant_templates()):
            self.assertCountEqual(snapshot_findings(self.fx, selected), self.PAGES)
            self.assertCountEqual(sentinel_findings(self.fx, selected), self.PAGES)
            regions = region_findings(self.fx, selected)
            self.assertCountEqual([label for label, _markers in regions], self.PAGES)
            for _label, markers in regions:
                self.assertIn("Taken", markers)

        self.assertEqual(snapshot_findings(self.fx, selected), [])
        self.assertEqual(sentinel_findings(self.fx, selected), [])
        self.assertEqual(region_findings(self.fx, selected), [])


class ChokepointTests(SecrecyMixin, TestCase):
    def test_claim_views_for_refuses_the_viewers_own_wishes(self):
        with self.assertRaises(claims.SecrecyViolation):
            claims.claim_views_for(self.fx.gita, [self.fx.w1])

    def test_claim_and_contribution_are_not_registered_in_the_admin(self):
        from django.contrib import admin

        self.assertFalse(admin.site.is_registered(Claim))
        self.assertFalse(admin.site.is_registered(Contribution))


class StaffGifteeTests(SecrecyMixin, TestCase):
    """The author is staff and superuser (promote_staff) and also a giftee.

    The suite used to crawl only as a non-staff giftee, which let the admin's user delete page
    through: its deletion summary listed every cascading row, Claim rows included
    (03-VERIFICATION.md, T-03-18). Everything below runs as a staff giftee.
    """

    def setUp(self):
        super().setUp()
        self.fx.gita.is_staff = True
        self.fx.gita.is_superuser = True
        self.fx.gita.save(update_fields=["is_staff", "is_superuser"])

    def test_admin_user_delete_pages_show_no_claim_data(self):
        fx = self.fx
        wish_names = list(Wish.objects.filter(owner=fx.gita).values_list("name", flat=True))
        self.assertEqual(len(wish_names), 6)
        users = (fx.gita, fx.carl, fx.kim, fx.sam, fx.oscar)
        with with_claims(fx):
            client = fresh_client(fx.gita)
            home = client.get("/gifter-admin/", follow=True)
            self.assertEqual(home.status_code, 200)
            self.assertEqual(home.redirect_chain, [])

            bodies = set()
            urls = [f"/gifter-admin/gifter/user/{user.pk}/delete/" for user in users]
            urls.append("/gifter-admin/gifter/user/999999/delete/")
            for url in urls:
                with self.subTest(url=url):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 403)
                    body = body_of(response)
                    for name in wish_names:
                        self.assertNotIn(name, body)
                    bodies.add(body)
            self.assertEqual(len(bodies), 1)

            counts = (
                get_user_model().objects.count(),
                Claim.objects.count(),
                Contribution.objects.count(),
            )
            sam_url = f"/gifter-admin/gifter/user/{fx.sam.pk}/delete/"
            self.assertEqual(client.post(sam_url, {"post": "yes"}).status_code, 403)
            self.assertTrue(get_user_model().objects.filter(pk=fx.sam.pk).exists())
            self.assertEqual(
                counts,
                (
                    get_user_model().objects.count(),
                    Claim.objects.count(),
                    Contribution.objects.count(),
                ),
            )

            bulk = client.post(
                "/gifter-admin/gifter/user/",
                {"action": "delete_selected", "_selected_action": [u.pk for u in users]},
                follow=True,
            )
            self.assertEqual(bulk.status_code, 200)
            bulk_body = body_of(bulk)
            for name in wish_names:
                self.assertNotIn(name, bulk_body)
            self.assertNotIn('value="delete_selected"', bulk_body)
            for user in users:
                self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())

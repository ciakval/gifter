"""
Secret claims, chip-in and My claims (Phase 3, plan 03-01, CLAM-02..CLAM-08, SECR-01).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_claims
"""

import threading
import time

from django.db import OperationalError, connection
from django.test import TestCase, TransactionTestCase

from gifter import claims
from gifter.claims import SecrecyViolation, claim_views_for
from gifter.models import Claim, Contribution, Wish
from gifter.tests.helpers import mask_csrf
from gifter.tests.test_events import join, make_event, make_user
from gifter.tests.test_wishes import make_wish


class ClaimScenario:
    """Anna owns wish W, shared into E1 (Anna, Bob, Carol) and E2 (Anna, Dave).

    Dave shares no event with Bob.
    """

    def build(self):
        self.anna = make_user("anna", first_name="Anna")
        self.bob = make_user("bob", first_name="Bob")
        self.carol = make_user("carol", first_name="Carol")
        self.dave = make_user("dave", first_name="Dave")
        self.e1 = make_event(self.anna, name="Family")
        join(self.e1, self.bob)
        join(self.e1, self.carol)
        self.e2 = make_event(self.anna, name="Friends")
        join(self.e2, self.dave)
        self.wish = make_wish(self.anna, name="Lego set", events=[self.e1, self.e2])

    def claim_url(self, event=None, wish=None, wish_pk=None):
        event = event or self.e1
        wish_pk = wish_pk or (wish or self.wish).pk
        return f"/events/{event.pk}/wishes/{wish_pk}/claim/"

    def event_url(self, event=None):
        return f"/events/{(event or self.e1).pk}/"


class ClaimTracerTests(ClaimScenario, TestCase):
    def setUp(self):
        self.build()

    def test_tracer_bob_claims_and_is_sent_back_to_the_card(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.claim_url())
        self.assertRedirects(
            response,
            f"/events/{self.e1.pk}/#wish-{self.wish.pk}",
            fetch_redirect_response=False,
        )
        claim = Claim.objects.get()
        self.assertEqual(claim.claimer, self.bob)
        followed = self.client.get(response["Location"].split("#")[0])
        self.assertContains(followed, "You are getting this one.")
        self.assertContains(followed, "You are getting this.")
        self.assertContains(followed, f'id="wish-{self.wish.pk}"')

    def test_other_members_see_taken_and_names_follow_shared_events(self):
        Claim.objects.create(wish=self.wish, claimer=self.bob)
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertContains(page, "Taken")
        self.assertContains(page, "Taken by Bob")
        self.client.force_login(self.dave)
        page = self.client.get(self.event_url(self.e2))
        self.assertContains(page, "Taken")
        self.assertContains(page, "Taken by someone")
        self.assertNotContains(page, "Bob")

    def test_one_shared_event_elsewhere_is_enough_to_see_the_name(self):
        Claim.objects.create(wish=self.wish, claimer=self.bob)
        e3 = make_event(self.bob, name="Chess club")
        join(e3, self.dave)
        self.client.force_login(self.dave)
        page = self.client.get(self.event_url(self.e2))
        self.assertContains(page, "Taken by Bob")

    def test_names_are_escaped_and_czech_letters_survive(self):
        zofie = make_user("zofie", first_name="<b>Žofie</b>")
        join(self.e1, zofie)
        Claim.objects.create(wish=self.wish, claimer=zofie)
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertContains(page, "&lt;b&gt;Žofie&lt;/b&gt;")
        self.assertNotContains(page, "<b>Žofie</b>")

    def test_nameless_claimer_is_never_shown_by_username_or_email(self):
        ghost = make_user("ghost.user", email="ghost.user@example.com")
        join(self.e1, ghost)
        Claim.objects.create(wish=self.wish, claimer=ghost)
        self.client.force_login(self.dave)
        page = self.client.get(self.event_url(self.e2))
        self.assertNotContains(page, "ghost")
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertNotContains(page, "ghost")
        self.assertContains(page, "Unnamed member")

    def test_unclaimed_wish_has_no_badge_and_offers_the_button(self):
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertNotContains(page, "Taken")
        self.assertContains(page, "get this")

    def test_claiming_does_not_reorder_cards(self):
        low = make_wish(self.anna, name="Socks", events=[self.e1], priority=Wish.Priority.LOW)
        high = make_wish(self.anna, name="Bike", events=[self.e1], priority=Wish.Priority.HIGH)
        self.client.force_login(self.carol)

        def order():
            html = self.client.get(self.event_url()).content.decode()
            return [
                name
                for _position, name in sorted(
                    (html.index(w.name), w.name) for w in (self.wish, low, high)
                )
            ]

        before = order()
        Claim.objects.create(wish=low, claimer=self.bob)
        Claim.objects.create(wish=high, claimer=self.bob)
        self.assertEqual(order(), before)

    def test_stale_page_loser_sees_someone_just_took_it(self):
        Claim.objects.create(wish=self.wish, claimer=self.bob)
        self.client.force_login(self.carol)
        response = self.client.post(self.claim_url())
        self.assertRedirects(
            response,
            f"/events/{self.e1.pk}/#wish-{self.wish.pk}",
            fetch_redirect_response=False,
        )
        followed = self.client.get(self.event_url())
        self.assertContains(followed, "Someone just took it")
        self.assertContains(followed, "Taken by Bob")
        self.assertEqual(Claim.objects.count(), 1)
        self.assertEqual(Claim.objects.get().claimer, self.bob)

    def test_repeated_claim_by_the_claimer_is_a_silent_no_op(self):
        self.client.force_login(self.bob)
        self.client.post(self.claim_url())
        followed = self.client.post(self.claim_url(), follow=True)
        self.assertNotContains(followed, "Someone just took it")
        self.assertEqual(Claim.objects.count(), 1)

    def test_giftee_pages_are_identical_with_and_without_a_claim(self):
        self.client.force_login(self.anna)
        before = [
            mask_csrf(self.client.get(url).content.decode())
            for url in ("/wishes/", self.event_url())
        ]
        Claim.objects.create(wish=self.wish, claimer=self.bob)
        after = [
            mask_csrf(self.client.get(url).content.decode())
            for url in ("/wishes/", self.event_url())
        ]
        self.assertEqual(before, after)


class UniformNotFoundTests(ClaimScenario, TestCase):
    def setUp(self):
        self.build()
        self.client.force_login(self.bob)
        self.baseline = self.client.post(self.claim_url(wish_pk=999999)).content

    def assert_uniform(self, user, url, *, claim_rows=0):
        self.client.force_login(user)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404, url)
        self.assertEqual(response.content, self.baseline, url)
        self.assertEqual(Claim.objects.count(), claim_rows)

    def test_baseline_is_a_404(self):
        self.assertEqual(self.client.post(self.claim_url(wish_pk=999999)).status_code, 404)

    def test_giftee_without_and_with_a_claim(self):
        self.assert_uniform(self.anna, self.claim_url())
        Claim.objects.create(wish=self.wish, claimer=self.bob)
        self.assert_uniform(self.anna, self.claim_url(), claim_rows=1)

    def test_non_member(self):
        self.assert_uniform(self.dave, self.claim_url())

    def test_missing_event(self):
        self.assert_uniform(self.bob, f"/events/999999/wishes/{self.wish.pk}/claim/")

    def test_wish_shared_only_elsewhere(self):
        only_e2 = make_wish(self.anna, name="Only friends", events=[self.e2])
        join(self.e2, self.bob)
        self.client.force_login(self.bob)
        self.assert_uniform(self.bob, self.claim_url(event=self.e1, wish=only_e2))

    def test_withdrawn_wish(self):
        Wish.objects.filter(pk=self.wish.pk).update(status=Wish.Status.WITHDRAWN)
        self.assert_uniform(self.bob, self.claim_url())


class ClaimMethodTests(ClaimScenario, TestCase):
    def setUp(self):
        self.build()
        self.client.force_login(self.bob)

    def test_get_is_405(self):
        self.assertEqual(self.client.get(self.claim_url()).status_code, 405)

    def test_claiming_leaves_updated_at_alone(self):
        before = Wish.objects.get(pk=self.wish.pk).updated_at
        self.client.post(self.claim_url())
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).updated_at, before)


class ChokepointAndShapeTests(ClaimScenario, TestCase):
    def setUp(self):
        self.build()

    def test_chokepoint_refuses_own_wishes(self):
        with self.assertRaises(SecrecyViolation):
            claim_views_for(self.anna, [self.wish])
        with self.assertRaises(SecrecyViolation):
            claims.claim_wish(self.anna, self.wish)

    def test_empty_list_runs_no_queries(self):
        with self.assertNumQueries(0):
            self.assertEqual(claim_views_for(self.bob, []), {})

    def test_contribution_has_no_money_field(self):
        names = [field.name for field in Contribution._meta.get_fields()]
        self.assertEqual(
            sorted(names),
            sorted(["id", "claim", "user", "note", "created_at", "acknowledged_at"]),
        )


class ClaimRaceTests(ClaimScenario, TransactionTestCase):
    """Two simultaneous claimers: exactly one wins (D-03).

    The shared-cache in-memory test database skips SQLite's busy timeout and raises "table is
    locked" instead of waiting, as the production file database does. The harness retries on that
    error to stand in for the timeout.
    """

    def setUp(self):
        self.build()

    def _try_claim(self, user, barrier, results):
        try:
            barrier.wait()
            for _attempt in range(100):
                try:
                    results[user.pk] = claims.claim_wish(user, self.wish)
                    return
                except OperationalError as error:
                    if "locked" not in str(error):
                        raise
                    time.sleep(0.02)
            results[user.pk] = "gave-up"
        except Exception as error:  # noqa: BLE001 - reported through the results dict
            results[user.pk] = error
        finally:
            connection.close()

    def test_exactly_one_of_two_simultaneous_claims_wins(self):
        for _round in range(10):
            Claim.objects.all().delete()
            barrier = threading.Barrier(2)
            results = {}
            threads = [
                threading.Thread(target=self._try_claim, args=(user, barrier, results))
                for user in (self.bob, self.carol)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            for outcome in results.values():
                self.assertIsInstance(outcome, str, outcome)
            self.assertEqual(sorted(results.values()), ["claimed", "taken"])
            claim = Claim.objects.get()
            winner = next(pk for pk, outcome in results.items() if outcome == "claimed")
            self.assertEqual(claim.claimer_id, winner)
            self.assertNotEqual(claim.claimer_id, claim.wish.owner_id)

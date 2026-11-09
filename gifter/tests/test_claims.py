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
from gifter.tests.helpers import claim_state_markers, mask_csrf
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


class ChipInScenario(ClaimScenario):
    """Adds Kim and Lea (both in E1) and Bob's claim on the wish."""

    def build_chip_in(self):
        self.build()
        self.kim = make_user("kim", first_name="Kim")
        self.lea = make_user("lea", first_name="Lea")
        join(self.e1, self.kim)
        join(self.e1, self.lea)
        self.claim = Claim.objects.create(wish=self.wish, claimer=self.bob)

    def chip_url(self, event=None, wish_pk=None):
        return f"/events/{(event or self.e1).pk}/wishes/{wish_pk or self.wish.pk}/chip-in/"

    def action_url(self, action, wish_pk=None):
        return f"/claims/{wish_pk or self.wish.pk}/{action}/"


class ChipInTests(ChipInScenario, TestCase):
    def setUp(self):
        self.build_chip_in()

    def test_chip_in_with_note_is_visible_to_co_members_only(self):
        self.client.force_login(self.kim)
        response = self.client.post(self.chip_url(), {"note": "I'll add 500 Kč"})
        self.assertRedirects(
            response,
            f"/events/{self.e1.pk}/#wish-{self.wish.pk}",
            fetch_redirect_response=False,
        )
        self.assertEqual(Contribution.objects.get().note, "I'll add 500 Kč")
        own = self.client.get(self.event_url())
        self.assertContains(own, "You are chipping in")
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertContains(page, "Kim is chipping in")
        self.assertContains(page, "add 500 Kč")
        # Dave shares E2 with Anna only, so he shares no event with Kim.
        self.client.force_login(self.dave)
        page = self.client.get(self.event_url(self.e2))
        self.assertContains(page, "Someone is chipping in.")
        self.assertNotContains(page, "add 500")
        self.assertNotContains(page, "Kim")

    def test_contributors_listed_in_chip_in_order(self):
        Contribution.objects.create(claim=self.claim, user=self.lea, note="second")
        Contribution.objects.create(claim=self.claim, user=self.kim, note="third")
        self.client.force_login(self.carol)
        html = self.client.get(self.event_url()).content.decode()
        self.assertLess(html.index("Lea is chipping in"), html.index("Kim is chipping in"))

    def test_claimer_has_no_chip_in_button_and_cannot_chip_in(self):
        self.client.force_login(self.bob)
        page = self.client.get(self.event_url())
        self.assertNotContains(page, "Chip in")
        response = self.client.post(self.chip_url(), {"note": "x"}, follow=True)
        self.assertContains(response, "You are already getting this one.")
        self.assertEqual(Contribution.objects.count(), 0)

    def test_second_chip_in_keeps_one_row_and_replaces_the_note(self):
        self.client.force_login(self.kim)
        self.client.post(self.chip_url(), {"note": "first"})
        self.client.post(self.chip_url(), {"note": "second"})
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(Contribution.objects.get().note, "second")

    def test_empty_and_whitespace_notes_are_stored_empty(self):
        self.client.force_login(self.kim)
        self.client.post(self.chip_url(), {"note": "   "})
        self.assertEqual(Contribution.objects.get().note, "")
        self.client.force_login(self.lea)
        self.client.post(self.chip_url(), {})
        self.assertEqual(Contribution.objects.get(user=self.lea).note, "")

    def test_note_limit_counts_code_points(self):
        self.client.force_login(self.kim)
        self.client.post(self.chip_url(), {"note": "ž" * 200})
        self.assertEqual(Contribution.objects.get().note, "ž" * 200)
        self.client.force_login(self.lea)
        response = self.client.post(self.chip_url(), {"note": "ž" * 201}, follow=True)
        self.assertEqual(Contribution.objects.filter(user=self.lea).count(), 0)
        self.assertContains(response, "alert-danger")

    def test_script_in_note_is_escaped(self):
        self.client.force_login(self.kim)
        self.client.post(self.chip_url(), {"note": "<script>alert(1)</script>"})
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_chip_in_after_release_says_free_again(self):
        self.claim.delete()
        self.client.force_login(self.kim)
        response = self.client.post(self.chip_url(), {"note": "x"}, follow=True)
        self.assertContains(response, "This wish is free again.")
        self.assertEqual(Contribution.objects.count(), 0)

    def test_stop_chipping_in(self):
        Contribution.objects.create(claim=self.claim, user=self.kim)
        self.client.force_login(self.kim)
        response = self.client.post(self.action_url("leave"), {"next": self.event_url()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertEqual(self.client.post(self.action_url("leave")).status_code, 404)


class PurchasedReleaseTests(ChipInScenario, TestCase):
    def setUp(self):
        self.build_chip_in()

    def test_purchased_is_shown_to_others(self):
        self.client.force_login(self.bob)
        response = self.client.post(self.action_url("purchased"))
        self.assertEqual(response.status_code, 302)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, Claim.Status.PURCHASED)
        self.client.force_login(self.carol)
        page = self.client.get(self.event_url())
        self.assertContains(page, "Purchased")
        self.assertContains(page, "Purchased by Bob")
        self.assertNotContains(page, "Taken by Bob")

    def test_release_hands_over_to_earliest_contributor(self):
        Contribution.objects.create(claim=self.claim, user=self.kim, note="early")
        Contribution.objects.create(claim=self.claim, user=self.lea, note="late")
        self.claim.status = Claim.Status.PURCHASED
        self.claim.save()
        self.client.force_login(self.bob)
        self.client.post(self.action_url("release"))
        claim = Claim.objects.get()
        self.assertEqual(claim.claimer, self.kim)
        self.assertEqual(claim.status, Claim.Status.RESERVED)
        self.assertEqual(list(Contribution.objects.values_list("user__username", flat=True)), ["lea"])

    def test_release_without_contributors_frees_the_wish(self):
        self.client.force_login(self.bob)
        self.client.post(self.action_url("release"))
        self.assertEqual(Claim.objects.count(), 0)
        self.client.force_login(self.carol)
        self.assertContains(self.client.get(self.event_url()), "get this")

    def test_uniform_404_for_everyone_else(self):
        self.client.force_login(self.bob)
        baseline = self.client.post(self.action_url("release", wish_pk=999999)).content
        Contribution.objects.create(claim=self.claim, user=self.kim)
        for with_claim in (True, False):
            if not with_claim:
                Contribution.objects.all().delete()
                Claim.objects.all().delete()
            for user in (self.anna, self.carol, self.dave):
                self.client.force_login(user)
                for action in ("purchased", "release", "leave"):
                    response = self.client.post(self.action_url(action))
                    self.assertEqual(response.status_code, 404, (user, action))
                    self.assertEqual(response.content, baseline)
        self.assertEqual(Claim.objects.count(), 0)

    def test_nothing_changes_for_probes_with_a_claim(self):
        Contribution.objects.create(claim=self.claim, user=self.kim)
        for user in (self.anna, self.carol, self.dave):
            self.client.force_login(user)
            for action in ("purchased", "release", "leave"):
                self.client.post(self.action_url(action))
        claim = Claim.objects.get()
        self.assertEqual((claim.claimer, claim.status), (self.bob, Claim.Status.RESERVED))
        self.assertEqual(Contribution.objects.count(), 1)

    def test_updated_at_never_changes(self):
        before = Wish.objects.get(pk=self.wish.pk).updated_at
        self.client.force_login(self.kim)
        self.client.post(self.chip_url(), {"note": "x"})
        self.client.post(self.action_url("leave"))
        self.client.post(self.chip_url(), {"note": "x"})
        self.client.force_login(self.bob)
        self.client.post(self.action_url("purchased"))
        self.client.post(self.action_url("release"))
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).updated_at, before)

    def test_next_is_followed_only_when_same_host(self):
        self.client.force_login(self.bob)
        target = f"/events/{self.e1.pk}/#wish-{self.wish.pk}"
        response = self.client.post(self.action_url("purchased"), {"next": target})
        self.assertEqual(response["Location"], target)
        response = self.client.post(self.action_url("purchased"), {"next": "https://evil.example/x"})
        self.assertNotIn("evil.example", response["Location"])

    def test_chip_in_get_is_405(self):
        self.client.force_login(self.kim)
        for url in (self.chip_url(), self.action_url("purchased"), self.action_url("release"), self.action_url("leave")):
            self.assertEqual(self.client.get(url).status_code, 405, url)

    def test_chip_in_uniform_404(self):
        self.client.force_login(self.kim)
        baseline = self.client.post(self.chip_url(wish_pk=999999)).content
        for user in (self.anna, self.dave):
            self.client.force_login(user)
            response = self.client.post(self.chip_url(), {"note": "x"})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.content, baseline)
        self.assertEqual(Contribution.objects.count(), 0)

    def test_at_most_one_claim_per_wish_and_never_the_owner(self):
        Contribution.objects.create(claim=self.claim, user=self.kim)
        self.client.force_login(self.bob)
        self.client.post(self.action_url("release"))
        for claim in Claim.objects.all():
            self.assertNotEqual(claim.claimer_id, claim.wish.owner_id)
        self.assertEqual(Claim.objects.filter(wish=self.wish).count(), 1)


def edit_payload(wish, events, **changes):
    payload = {
        "name": wish.name,
        "description": wish.description,
        "priority": str(wish.priority),
        "links": wish.links,
        "events": [event.pk for event in events],
    }
    payload.update(changes)
    return payload


class MyClaimsScenario(ChipInScenario):
    """Bob claims Lego set. Bike (Anna, E1) is claimed by Kim, with Bob chipping in.
    Socks (Anna, E1) is claimed by Lea, so Bob is not part of it."""

    def build_my_claims(self):
        self.build_chip_in()
        self.bike = make_wish(self.anna, name="Bike", events=[self.e1], description="Red one")
        self.bike_claim = Claim.objects.create(wish=self.bike, claimer=self.kim)
        Contribution.objects.create(claim=self.bike_claim, user=self.bob, note="from Bob")
        self.socks = make_wish(self.anna, name="Socks", events=[self.e1])
        Claim.objects.create(wish=self.socks, claimer=self.lea)

    def my_claims(self, user=None):
        self.client.force_login(user or self.bob)
        return self.client.get("/claims/")

    def anna_edits(self, wish, events, **changes):
        self.client.force_login(self.anna)
        response = self.client.post(f"/wishes/{wish.pk}/edit/", edit_payload(wish, events, **changes))
        self.assertEqual(response.status_code, 302)


class MyClaimsTests(MyClaimsScenario, TestCase):
    def setUp(self):
        self.build_my_claims()

    def test_lists_claims_and_chip_ins_but_not_other_peoples(self):
        page = self.my_claims()
        self.assertContains(page, "For Anna")
        self.assertContains(page, "Lego set")
        self.assertContains(page, "Bike")
        self.assertContains(page, "Red one")
        self.assertContains(page, "You are getting this.")
        self.assertContains(page, "You are chipping in")
        self.assertContains(page, "Taken by Kim")
        self.assertContains(page, "Release")
        self.assertContains(page, "Mark purchased")
        self.assertContains(page, "Stop chipping in")
        self.assertNotContains(page, "Socks")

    def test_empty_state(self):
        page = self.my_claims(self.dave)
        self.assertContains(page, "You have not claimed or chipped in on anything yet.")

    def test_unshared_wish_stays_listed_and_can_be_released(self):
        self.wish.events.clear()
        self.client.force_login(self.carol)
        self.assertNotContains(self.client.get(self.event_url()), "Lego set")
        response = self.client.post("/claims/%d/release/" % self.wish.pk)
        self.assertEqual(response.status_code, 404)
        self.assertContains(self.my_claims(), "Lego set")
        response = self.client.post("/claims/%d/release/" % self.wish.pk)
        self.assertRedirects(response, "/claims/", fetch_redirect_response=False)
        self.assertFalse(Claim.objects.filter(wish=self.wish).exists())

    def test_withdrawn_wish_shows_notice_and_remove_button(self):
        Wish.objects.filter(pk__in=[self.wish.pk, self.bike.pk]).update(
            status=Wish.Status.WITHDRAWN
        )
        page = self.my_claims()
        self.assertContains(page, "Withdrawn by the owner")
        self.assertContains(page, "Remove from my claims")
        self.assertNotContains(page, "Mark purchased")
        self.client.force_login(self.carol)
        self.assertNotContains(self.client.get(self.event_url()), "Lego set")
        self.client.force_login(self.bob)
        self.client.post(f"/claims/{self.wish.pk}/release/")
        self.client.post(f"/claims/{self.bike.pk}/leave/")
        self.assertFalse(Claim.objects.filter(wish=self.wish).exists())
        self.assertFalse(Contribution.objects.filter(user=self.bob).exists())

    def test_order_is_active_then_withdrawn_then_received(self):
        received = make_wish(self.anna, name="Received thing", events=[self.e1])
        Claim.objects.create(wish=received, claimer=self.bob)
        Wish.objects.filter(pk=received.pk).update(status=Wish.Status.RECEIVED)
        Wish.objects.filter(pk=self.wish.pk).update(status=Wish.Status.WITHDRAWN)
        html = self.my_claims().content.decode()
        self.assertContains(self.my_claims(), "Received")
        self.assertLess(html.index("Bike"), html.index("Lego set"))
        self.assertLess(html.index("Lego set"), html.index("Received thing"))
        received_card = html[html.index("Received thing") :]
        self.assertNotIn("Release", received_card)

    def test_newest_involvement_first_within_a_group(self):
        newer = make_wish(self.anna, name="Newer one", events=[self.e1])
        Claim.objects.create(wish=newer, claimer=self.bob)
        html = self.my_claims().content.decode()
        self.assertLess(html.index("Newer one"), html.index("Lego set"))

    def test_changed_marker_for_claimer_and_contributor_until_got_it(self):
        self.anna_edits(self.wish, [self.e1, self.e2], name="Lego set 2")
        self.anna_edits(self.bike, [self.e1], name="Bike 2")
        page = self.my_claims()
        self.assertContains(page, "Changed since you claimed")
        self.assertContains(page, "Changed since you chipped in")
        self.client.force_login(self.carol)
        self.assertNotContains(self.client.get(self.event_url()), "Changed since you")
        self.client.force_login(self.bob)
        self.assertContains(self.client.get(self.event_url()), "Changed since you claimed")
        response = self.client.post(f"/claims/{self.wish.pk}/got-it/", {"next": self.event_url()})
        self.assertEqual(response["Location"], self.event_url())
        page = self.my_claims()
        self.assertNotContains(page, "Changed since you claimed")
        self.assertContains(page, "Changed since you chipped in")
        self.client.post(f"/claims/{self.bike.pk}/got-it/")
        self.assertNotContains(self.my_claims(), "Changed since you")

    def test_share_only_edit_and_status_only_save_raise_no_marker(self):
        self.anna_edits(self.wish, [self.e1])
        self.assertNotContains(self.my_claims(), "Changed since you")
        wish = Wish.objects.get(pk=self.wish.pk)
        wish.status = Wish.Status.RECEIVED
        wish.save(update_fields=["status"])
        self.assertNotContains(self.my_claims(), "Changed since you")

    def test_marker_carries_over_to_the_new_claimer_after_hand_over(self):
        self.anna_edits(self.bike, [self.e1], name="Bike 2")
        self.client.force_login(self.kim)
        self.client.post(f"/claims/{self.bike.pk}/release/")
        page = self.my_claims(self.bob)
        self.assertContains(page, "You are getting this.")
        self.assertContains(page, "Changed since you claimed")

    def test_got_it_uniform_404(self):
        self.client.force_login(self.bob)
        baseline = self.client.post("/claims/999999/got-it/").content
        for user in (self.anna, self.carol, self.dave):
            self.client.force_login(user)
            response = self.client.post(f"/claims/{self.wish.pk}/got-it/")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.content, baseline)
        self.assertEqual(self.client.get(f"/claims/{self.wish.pk}/got-it/").status_code, 405)

    def test_nav_link_and_login_redirect(self):
        self.client.force_login(self.dave)
        self.assertContains(self.client.get("/events/"), 'href="/claims/"')
        self.client.logout()
        self.assertRedirects(self.client.get("/claims/"), "/?next=/claims/", fetch_redirect_response=False)

    def test_actions_fall_back_to_my_claims(self):
        self.client.force_login(self.bob)
        response = self.client.post(f"/claims/{self.wish.pk}/purchased/", {"next": "https://evil.example/"})
        self.assertEqual(response["Location"], "/claims/")
        response = self.client.post(f"/claims/{self.bike.pk}/leave/")
        self.assertEqual(response["Location"], "/claims/")

    def test_names_on_my_claims_follow_the_visibility_rule(self):
        # Fran lives only in E5 with Anna. Bob lives only in E1. The phone is shared into both.
        fran = make_user("fran", first_name="Fran")
        e5 = make_event(self.anna, name="Work")
        join(e5, fran)
        phone = make_wish(self.anna, name="Phone", events=[self.e1, e5])
        Claim.objects.create(wish=phone, claimer=fran)
        Contribution.objects.create(
            claim=Claim.objects.get(wish=phone), user=self.bob, note="secret note"
        )
        bob_page = self.my_claims(self.bob)
        self.assertContains(bob_page, "Taken by someone")
        self.assertNotContains(bob_page, "Fran")
        fran_page = self.my_claims(fran)
        self.assertContains(fran_page, "Someone is chipping in.")
        self.assertNotContains(fran_page, "secret note")
        self.assertNotContains(fran_page, "Bob")

    def test_claim_state_markers_match_the_rendered_copy(self):
        self.client.force_login(self.carol)
        event_page = self.client.get(self.event_url()).content.decode()
        found = claim_state_markers(event_page)
        self.assertIn("Taken", found)
        self.assertIn("chipping in", found)
        self.assertIn("Release", claim_state_markers(self.my_claims().content.decode()))

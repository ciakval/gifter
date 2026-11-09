"""
Received wishes: mark, collapsed section, reopen (Phase 3, plan 03-02, LIFE-01..LIFE-03).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_received
"""

from django.test import TestCase

from gifter import claims
from gifter.models import Claim, Contribution, Wish
from gifter.tests.helpers import mask_csrf
from gifter.tests.test_events import join, make_event, make_user
from gifter.tests.test_wishes import make_wish


class ReceivedScenario:
    """Anna owns W shared into E1 (Anna, Bob, Carol) and E2 (Anna, Dave).

    Bob claims W and Carol chips in with a note.
    """

    def build(self, with_claims=True):
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
        if with_claims:
            claims.claim_wish(self.bob, self.wish)
            claims.chip_in(self.carol, self.wish, "Happy to help")

    def received_url(self, wish=None):
        return f"/wishes/{(wish or self.wish).pk}/received/"

    def reopen_url(self, wish=None):
        return f"/wishes/{(wish or self.wish).pk}/reopen/"

    def event_page(self, user, event):
        self.client.force_login(user)
        return self.client.get(f"/events/{event.pk}/").content.decode()


class ReceivedTracerTests(ReceivedScenario, TestCase):
    def setUp(self):
        self.build()

    def test_tracer_anna_marks_received_and_it_moves_into_the_collapsed_section(self):
        self.client.force_login(self.anna)
        response = self.client.post(self.received_url())
        self.assertRedirects(response, "/wishes/", fetch_redirect_response=False)
        followed = self.client.get("/wishes/")
        self.assertContains(followed, "Marked as received.")
        html = followed.content.decode()
        summary = html.index("Received (1)")
        details = html.rindex("<details", 0, summary)
        self.assertLess(details, summary)
        self.assertNotIn("open", html[details : html.index(">", details)])
        # The wish name appears only after the summary, inside the details element.
        self.assertEqual(html.count("Lego set"), 1)
        self.assertGreater(html.index("Lego set"), summary)
        self.assertLess(html.index("Lego set"), html.index("</details>"))
        self.assertIn(self.reopen_url(), html)

        self.assertNotIn("Lego set", self.event_page(self.carol, self.e1))
        self.assertNotIn("Lego set", self.event_page(self.dave, self.e2))
        self.assertNotIn("Lego set", self.event_page(self.anna, self.e1))

        self.client.force_login(self.bob)
        mine = self.client.get("/claims/")
        self.assertContains(mine, "Lego set")
        self.assertContains(mine, "Received")
        self.assertNotContains(mine, "Withdrawn by the owner")
        self.assertNotContains(mine, "/release/")
        claim = Claim.objects.get()
        self.assertEqual(claim.claimer, self.bob)
        self.assertEqual(Contribution.objects.get().user, self.carol)

    def test_reopen_brings_it_back_everywhere_without_a_changed_marker(self):
        before = Wish.objects.get(pk=self.wish.pk).updated_at
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        response = self.client.post(self.reopen_url())
        self.assertRedirects(response, "/wishes/", fetch_redirect_response=False)
        page = self.client.get("/wishes/")
        self.assertContains(page, "Wish reopened.")
        self.assertNotIn("<details", page.content.decode())
        self.assertIn("Lego set", self.event_page(self.carol, self.e1))
        self.assertIn("Lego set", self.event_page(self.dave, self.e2))
        bob_page = self.event_page(self.bob, self.e1)
        self.assertIn("Taken", bob_page)
        self.assertNotIn("Changed since", bob_page)
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).updated_at, before)
        self.assertEqual(Claim.objects.count(), 1)
        self.assertEqual(Contribution.objects.count(), 1)


class ReceivedEdgeTests(ReceivedScenario, TestCase):
    def setUp(self):
        self.build()

    def test_received_never_touches_claims_or_updated_at(self):
        wish_before = Wish.objects.get(pk=self.wish.pk).updated_at
        claim = Claim.objects.get()
        contribution = Contribution.objects.get()
        snapshot = (claim.pk, claim.claimer_id, claim.status, claim.acknowledged_at)
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).updated_at, wish_before)
        claim.refresh_from_db()
        contribution.refresh_from_db()
        self.assertEqual(
            snapshot, (claim.pk, claim.claimer_id, claim.status, claim.acknowledged_at)
        )
        self.assertEqual(contribution.note, "Happy to help")

    def test_unclaimed_wish_goes_through_the_same_flow(self):
        plain = make_wish(self.anna, name="Plain socks", events=[self.e1])
        other = make_wish(self.anna, name="Claimed socks", events=[self.e1])
        claims.claim_wish(self.bob, other)
        self.client.force_login(self.anna)
        a = self.client.post(self.received_url(plain), follow=True)
        b = self.client.post(self.received_url(other), follow=True)
        self.assertEqual(a.redirect_chain, b.redirect_chain)
        self.assertContains(a, "Marked as received.")
        self.assertContains(b, "Marked as received.")
        self.assertEqual(Wish.objects.get(pk=plain.pk).status, Wish.Status.RECEIVED)

    def test_received_is_idempotent(self):
        self.client.force_login(self.anna)
        first = self.client.post(self.received_url(), follow=True)
        second = self.client.post(self.received_url(), follow=True)
        self.assertEqual(first.redirect_chain, second.redirect_chain)
        self.assertContains(second, "Marked as received.")
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).status, Wish.Status.RECEIVED)
        self.assertEqual(Claim.objects.count(), 1)

    def test_received_wish_shared_in_two_events_leaves_both_at_once(self):
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        self.assertNotIn("Lego set", self.event_page(self.bob, self.e1))
        self.assertNotIn("Lego set", self.event_page(self.dave, self.e2))

    def test_get_is_405(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.received_url()).status_code, 405)
        self.assertEqual(self.client.get(self.reopen_url()).status_code, 405)

    def test_other_users_and_missing_ids_get_404(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(self.received_url()).status_code, 404)
        self.assertEqual(self.client.post(self.reopen_url()).status_code, 404)
        self.assertEqual(self.client.post("/wishes/999999/received/").status_code, 404)
        self.assertEqual(self.client.post("/wishes/999999/reopen/").status_code, 404)
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).status, Wish.Status.ACTIVE)

    def test_withdrawn_wish_gets_404(self):
        Wish.objects.filter(pk=self.wish.pk).update(status=Wish.Status.WITHDRAWN)
        self.client.force_login(self.anna)
        self.assertEqual(self.client.post(self.received_url()).status_code, 404)
        self.assertEqual(self.client.post(self.reopen_url()).status_code, 404)
        self.assertEqual(Wish.objects.get(pk=self.wish.pk).status, Wish.Status.WITHDRAWN)

    def test_edit_page_of_a_received_wish_is_404(self):
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        self.assertEqual(self.client.get(f"/wishes/{self.wish.pk}/edit/").status_code, 404)

    def test_no_received_wishes_means_no_details_section(self):
        self.client.force_login(self.anna)
        self.assertNotIn("<details", self.client.get("/wishes/").content.decode())

    def test_only_received_wishes_show_the_no_open_wishes_copy(self):
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        page = self.client.get("/wishes/")
        self.assertContains(page, "No open wishes right now.")
        self.assertNotContains(page, "Your wishlist is empty")

    def test_received_section_orders_by_priority_then_newest(self):
        low = make_wish(self.anna, name="Low old", priority=Wish.Priority.LOW)
        high_old = make_wish(self.anna, name="High old", priority=Wish.Priority.HIGH)
        high_new = make_wish(self.anna, name="High new", priority=Wish.Priority.HIGH)
        self.client.force_login(self.anna)
        # Received in an order that differs from the expected display order.
        for wish in (high_new, low, high_old):
            self.client.post(self.received_url(wish))
        html = self.client.get("/wishes/").content.decode()
        section = html[html.index("<details") :]
        self.assertLess(section.index("High new"), section.index("High old"))
        self.assertLess(section.index("High old"), section.index("Low old"))

    def test_every_active_own_wish_has_a_received_button_claimed_or_not(self):
        plain = make_wish(self.anna, name="Plain socks")
        self.client.force_login(self.anna)
        html = self.client.get("/wishes/").content.decode()
        self.assertIn(self.received_url(), html)
        self.assertIn(self.received_url(plain), html)
        # And no Reopen form for an active wish.
        self.assertNotIn("/reopen/", html)

    def test_received_row_is_not_labelled_withdrawn_and_withdrawn_is_not_received(self):
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        self.client.force_login(self.bob)
        received_page = self.client.get("/claims/").content.decode()
        self.assertIn("Received", received_page)
        self.assertNotIn("Withdrawn by the owner", received_page)

        self.client.force_login(self.anna)
        self.client.post(self.reopen_url())
        self.client.post(f"/wishes/{self.wish.pk}/delete/")
        self.client.force_login(self.bob)
        withdrawn_page = self.client.get("/claims/").content.decode()
        self.assertIn("Withdrawn by the owner", withdrawn_page)
        self.assertNotIn(">Received<", withdrawn_page)


class ReceivedSecrecyTests(ReceivedScenario, TestCase):
    def snapshot(self):
        self.client.force_login(self.anna)
        return mask_csrf(self.client.get("/wishes/").content.decode())

    def test_giftee_wishlist_is_identical_with_and_without_claims(self):
        self.build(with_claims=False)
        other = make_wish(self.anna, name="Still active", events=[self.e1])
        self.client.force_login(self.anna)
        self.client.post(self.received_url())
        self.client.get("/wishes/")  # shows and consumes the flash message
        without = self.snapshot()
        claims.claim_wish(self.bob, self.wish)
        claims.chip_in(self.carol, self.wish, "Happy to help")
        claims.claim_wish(self.bob, other)
        with_claims = self.snapshot()
        self.assertEqual(without, with_claims)

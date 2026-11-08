"""
Wishlists, sharing into events and browsing (Phase 2, plan 02-02, WISH-01..04, CLAM-01).

Run with DEBUG=1 (otherwise the production SSL redirect and fail-closed secrets apply):
    DEBUG=1 uv run python manage.py test gifter.tests.test_wishes
"""

import datetime

from django.test import TestCase

from gifter.models import Wish
from gifter.tests.test_events import join, make_event, make_user


def make_wish(owner, name="Lego set", events=(), **fields):
    wish = Wish.objects.create(owner=owner, name=name, **fields)
    if events:
        wish.events.add(*events)
    return wish


class TracerTests(TestCase):
    def setUp(self):
        self.anna = make_user("anna", first_name="Anna")
        self.bob = make_user("bob", first_name="Bob")
        self.event = make_event(self.anna, name="Family Christmas")
        join(self.event, self.bob)

    def add(self, **data):
        payload = {"name": "Lego set", "description": "", "priority": "2"}
        payload.update(data)
        return self.client.post("/wishes/new/", payload)

    def test_tracer_anna_adds_wish_and_bob_sees_it_in_her_card(self):
        self.client.force_login(self.anna)
        response = self.add(events=[self.event.pk])
        self.assertRedirects(response, "/wishes/")
        wish = Wish.objects.get()
        self.assertEqual(wish.owner, self.anna)
        self.assertContains(self.client.get("/wishes/"), "Lego set")
        own_page = self.client.get(f"/events/{self.event.pk}/")
        self.assertNotContains(own_page, '<div class="card-header fw-semibold">Anna</div>')

        self.client.force_login(self.bob)
        page = self.client.get(f"/events/{self.event.pk}/")
        card = page.content.decode().split('<div class="card-header fw-semibold">Anna</div>')[1]
        self.assertIn("Lego set", card)

    def test_unshared_wish_is_invisible_to_other_members(self):
        self.client.force_login(self.anna)
        self.add(name="Secret telescope")
        self.assertEqual(Wish.objects.get().events.count(), 0)
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(f"/events/{self.event.pk}/"), "Secret telescope")

    def test_wish_shared_elsewhere_is_not_in_this_event(self):
        other = make_event(self.anna, name="Wedding")
        make_wish(self.anna, "Wedding gift", events=[other])
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(f"/events/{self.event.pk}/"), "Wedding gift")

    def test_member_without_wishes_still_gets_a_card(self):
        self.client.force_login(self.bob)
        page = self.client.get(f"/events/{self.event.pk}/")
        self.assertContains(page, "No wishes shared here yet.")

    def test_forged_event_id_is_rejected(self):
        carol = make_user("carol", first_name="Carol")
        foreign = make_event(carol, name="Carol party")
        self.client.force_login(self.anna)
        response = self.add(events=[foreign.pk])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["events"])
        self.assertEqual(Wish.objects.count(), 0)
        self.assertEqual(Wish.events.through.objects.count(), 0)

    def test_user_without_events_can_add_a_wish(self):
        loner = make_user("loner", first_name="Loner")
        self.client.force_login(loner)
        form_page = self.client.get("/wishes/new/")
        self.assertContains(form_page, "not in any events yet")
        response = self.add()
        self.assertRedirects(response, "/wishes/")
        self.assertEqual(Wish.objects.get().owner, loner)

    def test_event_checkboxes_follow_my_events_order(self):
        undated = make_event(self.anna, name="Zeta undated")
        late = make_event(self.anna, name="Late", date=datetime.date(2026, 12, 30))
        early = make_event(self.anna, name="Early", date=datetime.date(2026, 12, 1))
        self.client.force_login(self.anna)
        form = self.client.get("/wishes/new/").context["form"]
        pks = [choice.data["value"].value for choice in form["events"]]
        self.assertEqual(
            pks, [early.pk, late.pk, self.event.pk, undated.pk]
        )

    def test_same_name_events_show_dates_in_labels(self):
        make_event(self.anna, name="Party", date=datetime.date(2026, 12, 1))
        make_event(self.anna, name="Party", date=datetime.date(2026, 12, 2))
        self.client.force_login(self.anna)
        form = self.client.get("/wishes/new/").context["form"]
        labels = [str(choice.choice_label) for choice in form["events"] if "Party" in str(choice.choice_label)]
        self.assertEqual(len(labels), 2)
        self.assertEqual(len(set(labels)), 2)
        for label in labels:
            self.assertIn("(", label)

    def test_new_wish_form_preselects_all_events(self):
        other = make_event(self.anna, name="Wedding")
        self.client.force_login(self.anna)
        form = self.client.get("/wishes/new/").context["form"]
        self.assertCountEqual(form.initial["events"], [self.event.pk, other.pk])
        page = self.client.get("/wishes/new/")
        self.assertContains(page, '<option value="2" selected>Normal</option>', html=False)
        html = page.content.decode()
        self.assertEqual(html.count(" checked"), 2)

    def test_non_member_gets_404_with_no_wish_names(self):
        make_wish(self.anna, "Hidden gem", events=[self.event])
        carol = make_user("carol", first_name="Carol")
        self.client.force_login(carol)
        response = self.client.get(f"/events/{self.event.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Hidden gem", status_code=404)

    def test_anonymous_wishlist_redirects_to_landing(self):
        response = self.client.get("/wishes/")
        self.assertRedirects(response, "/?next=/wishes/", fetch_redirect_response=False)

    def test_navbar_has_my_wishlist_link(self):
        self.client.force_login(self.anna)
        self.assertContains(self.client.get("/wishes/"), 'href="/wishes/"')

    def test_wish_has_no_claim_fields(self):
        for field in Wish._meta.get_fields():
            self.assertNotIn("claim", field.name.lower())

    def test_owner_pages_render_no_claim_data(self):
        self.client.force_login(self.anna)
        for url in ("/wishes/", "/wishes/new/"):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode().lower()
                self.assertNotIn("claim", html)
